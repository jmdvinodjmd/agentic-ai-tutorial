"""LangGraph-only orchestration over canonical shared project contracts."""

from __future__ import annotations

import json
from collections.abc import Hashable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import JsonValue, TypeAdapter, ValidationError

from agentic_tutorial.budgets import BudgetManager
from agentic_tutorial.case_study import (
    CASE_STUDY_PLAN,
    CaseStudyDefinition,
    CaseStudyModelFactory,
    CaseStudyVariant,
    build_case_study_registry,
    build_offline_case_study_model,
    case_study_hash,
    load_definition,
)
from agentic_tutorial.case_study.results import finalise_case_study_state
from agentic_tutorial.checkpoints import JsonCheckpointStore
from agentic_tutorial.execution import AgentDecision
from agentic_tutorial.models import ModelClient, ModelProviderError
from agentic_tutorial.safety import PolicyToolExecutor, SafetyEngine
from agentic_tutorial.schemas import (
    AgentError,
    AgentState,
    AgentStep,
    Budget,
    ErrorClass,
    FinalAnswer,
    FinishAction,
    Message,
    MessageRole,
    ModelResponse,
    StepStatus,
    Termination,
    TerminationReason,
    TerminationStatus,
    ToolAction,
    ToolResultStatus,
)
from agentic_tutorial.tracing import (
    TraceEventType,
    TraceWriter,
    build_run_manifest,
    write_manifest,
)

NodeName = Literal[
    "planning",
    "search",
    "evidence_extraction",
    "synthesis",
    "critique",
    "termination",
    "end",
]


class GraphState(TypedDict):
    """JSON-compatible graph state; framework objects stay in the adapter context."""

    canonical_state: dict[str, Any]
    next_node: NodeName
    interrupt_after_steps: int | None


class _RunContext:
    def __init__(
        self,
        *,
        definition: CaseStudyDefinition,
        variant: CaseStudyVariant,
        model: ModelClient,
        store: JsonCheckpointStore,
        trace: TraceWriter,
    ) -> None:
        self.definition = definition
        self.variant_name = variant
        self.variant = definition.variant(variant)
        self.model = model
        self.store = store
        self.trace = trace
        self.tools = PolicyToolExecutor(
            build_case_study_registry(
                fail_searches=self.variant.inject_search_failures,
            ),
            SafetyEngine(definition.safety, trace_writer=trace),
        )

    def state(self, graph_state: GraphState) -> AgentState:
        return AgentState.model_validate(graph_state["canonical_state"])

    async def save(
        self,
        state: AgentState,
        next_node: NodeName,
        interrupt_after_steps: int | None,
    ) -> GraphState:
        await self.store.save(state)
        self.trace.emit(
            TraceEventType.CHECKPOINT,
            {
                "run_id": state.run_id,
                "step_number": len(state.steps),
                "framework_checkpoint": "langgraph-in-memory-plus-canonical-json",
                "next_node": next_node,
            },
        )
        return {
            "canonical_state": state.model_dump(mode="json"),
            "next_node": next_node,
            "interrupt_after_steps": interrupt_after_steps,
        }

    def manager(self, state: AgentState) -> BudgetManager:
        return BudgetManager(
            state.budget,
            initial_usage=state.usage,
            initial_actions=tuple(step.action for step in state.steps if step.action is not None),
        )

    def emit_budget(self, manager: BudgetManager, steps: int) -> None:
        snapshot = manager.snapshot(steps=steps)
        self.trace.emit(
            TraceEventType.BUDGET,
            {
                "configured": snapshot.budget.model_dump(mode="json"),
                "consumed": snapshot.consumed.model_dump(mode="json"),
                "remaining": {
                    "model_calls": snapshot.remaining_model_calls,
                    "steps": snapshot.remaining_steps,
                    "tool_calls": snapshot.remaining_tool_calls,
                    "tokens": snapshot.remaining_tokens,
                    "seconds": snapshot.remaining_seconds,
                    "failures": snapshot.remaining_failures,
                    "cost_usd": snapshot.remaining_cost_usd,
                },
            },
        )

    async def planning(self, graph_state: GraphState) -> GraphState:
        state = self.state(graph_state)
        self.trace.emit(
            TraceEventType.DECISION,
            {"route": "planning_to_search", "framework_node": "planning"},
        )
        if self.variant_name is CaseStudyVariant.CLARIFICATION_REQUIRED:
            termination = Termination(
                status=TerminationStatus.INTERRUPTED,
                reason=TerminationReason.HUMAN_INTERRUPTION,
                message="A comparison target and criterion are required before searching.",
                step_number=0,
            )
            state = state.model_copy(update={"termination": termination})
            self.trace.emit(
                TraceEventType.HUMAN_DECISION,
                {"decision": "request_information", "tool_execution_permitted": False},
            )
            self.trace.emit(
                TraceEventType.TERMINATION,
                {"termination": termination.model_dump(mode="json")},
            )
            return await self.save(state, "end", graph_state["interrupt_after_steps"])
        return await self.save(state, "search", graph_state["interrupt_after_steps"])

    async def search(self, graph_state: GraphState) -> GraphState:
        updated, result_name = await self.tool_decision(graph_state, "search_catalogue")
        state = self.state(updated)
        if state.termination is not None:
            return updated
        last = state.steps[-1].tool_result
        if last is not None and last.status is not ToolResultStatus.SUCCESS:
            next_node: NodeName = "search"
        elif self.variant_name is CaseStudyVariant.INSUFFICIENT_EVIDENCE:
            next_node = "synthesis"
        else:
            next_node = "evidence_extraction"
        return await self.route_after_step(updated, next_node, result_name)

    async def evidence_extraction(self, graph_state: GraphState) -> GraphState:
        updated, result_name = await self.tool_decision(graph_state, "extract_evidence")
        return await self.route_after_step(updated, "synthesis", result_name)

    async def synthesis(self, graph_state: GraphState) -> GraphState:
        state = self.state(graph_state)
        self.trace.emit(
            TraceEventType.DECISION,
            {
                "route": "synthesis_to_critique",
                "framework_node": "synthesis",
                "model_call_added": False,
            },
        )
        return await self.save(state, "critique", graph_state["interrupt_after_steps"])

    async def critique(self, graph_state: GraphState) -> GraphState:
        updated, result_name = await self.tool_decision(graph_state, "critique_draft")
        state = self.state(updated)
        next_node: NodeName = (
            "synthesis"
            if state.steps[-1].tool_result is not None
            and state.steps[-1].tool_result.status is not ToolResultStatus.SUCCESS
            else "termination"
        )
        return await self.route_after_step(updated, next_node, result_name)

    async def termination(self, graph_state: GraphState) -> GraphState:
        state = self.state(graph_state)
        manager = self.manager(state)
        reason = manager.check(steps=len(state.steps))
        self.emit_budget(manager, len(state.steps))
        if reason is not None:
            return await self.fail(state, reason, manager, graph_state)
        response = await self.model_call(state, manager)
        if isinstance(response, AgentError):
            return await self.error(state, response, manager, graph_state)
        try:
            decision = AgentDecision.model_validate(response.structured_output)
        except ValidationError:
            error = AgentError(
                error_class=ErrorClass.RECOVERABLE,
                code="malformed_action",
                message="model response action failed canonical validation",
                source=response.provider,
            )
            return await self.error(state, error, manager, graph_state, response=response)
        self.trace.emit(
            TraceEventType.DECISION,
            {"action": decision.action.model_dump(mode="json"), "framework_node": "termination"},
        )
        repeated = manager.observe_action(decision.action)
        if repeated is not None:
            return await self.fail(state, repeated, manager, graph_state)
        if not isinstance(decision.action, FinishAction):
            error = AgentError(
                error_class=ErrorClass.RECOVERABLE,
                code="unexpected_graph_action",
                message="termination node requires a finish action",
                source="langgraph",
            )
            return await self.error(state, error, manager, graph_state, response=response)
        step_number = len(state.steps) + 1
        termination = Termination(
            status=TerminationStatus.SUCCESS,
            reason=TerminationReason.COMPLETED,
            message="The model returned a valid finish action.",
            step_number=step_number,
        )
        state = state.model_copy(
            update={
                "steps": (
                    *state.steps,
                    AgentStep(
                        step_number=step_number,
                        status=StepStatus.COMPLETED,
                        action=decision.action,
                        model_response=response,
                        cumulative_usage=manager.usage,
                    ),
                ),
                "usage": manager.usage,
                "termination": termination,
                "final_answer": FinalAnswer(
                    task_id=state.task.task_id,
                    answer=decision.action.answer,
                ),
            }
        )
        state = finalise_case_study_state(state, self.variant)
        self.trace.emit(
            TraceEventType.STATE_TRANSITION,
            {
                "step": state.steps[-1].model_dump(mode="json"),
                "usage": state.usage.model_dump(mode="json"),
            },
        )
        self.trace.emit(
            TraceEventType.TERMINATION,
            {"termination": termination.model_dump(mode="json")},
        )
        return await self.save(state, "end", graph_state["interrupt_after_steps"])

    async def tool_decision(
        self, graph_state: GraphState, expected_tool: str
    ) -> tuple[GraphState, str]:
        state = self.state(graph_state)
        manager = self.manager(state)
        reason = manager.check(steps=len(state.steps))
        self.emit_budget(manager, len(state.steps))
        if reason is not None:
            return await self.fail(state, reason, manager, graph_state), expected_tool
        response = await self.model_call(state, manager)
        if isinstance(response, AgentError):
            return await self.error(state, response, manager, graph_state), expected_tool
        try:
            decision = AgentDecision.model_validate(response.structured_output)
        except ValidationError:
            error = AgentError(
                error_class=ErrorClass.RECOVERABLE,
                code="malformed_action",
                message="model response action failed canonical validation",
                source=response.provider,
            )
            return (
                await self.error(state, error, manager, graph_state, response=response),
                expected_tool,
            )
        self.trace.emit(
            TraceEventType.DECISION,
            {
                "action": decision.action.model_dump(mode="json"),
                "framework_node": expected_tool,
            },
        )
        repeated = manager.observe_action(decision.action)
        if repeated is not None:
            return await self.fail(state, repeated, manager, graph_state), expected_tool
        if (
            not isinstance(decision.action, ToolAction)
            or decision.action.tool_call.name != expected_tool
        ):
            error = AgentError(
                error_class=ErrorClass.RECOVERABLE,
                code="unexpected_graph_action",
                message=f"graph node requires tool {expected_tool!r}",
                source="langgraph",
            )
            return (
                await self.error(state, error, manager, graph_state, response=response),
                expected_tool,
            )
        reason = manager.check_before_tool()
        if reason is not None:
            return await self.fail(state, reason, manager, graph_state), expected_tool
        action = decision.action
        self.trace.emit(
            TraceEventType.TOOL_REQUEST,
            {"tool_call": action.tool_call.model_dump(mode="json")},
        )
        result = await self.tools.execute(
            action.tool_call,
            allowed_tools=self.definition.safety.allowed_tools,
        )
        self.trace.emit(
            TraceEventType.TOOL_RESULT,
            {"tool_result": result.model_dump(mode="json")},
        )
        manager.record_tool_result(result)
        errors = (result.error,) if result.error else ()
        if result.error is not None:
            self.trace.emit(TraceEventType.ERROR, {"error": result.error.model_dump(mode="json")})
        step = AgentStep(
            step_number=len(state.steps) + 1,
            status=(
                StepStatus.COMPLETED
                if result.status is ToolResultStatus.SUCCESS
                else StepStatus.FAILED
            ),
            action=action,
            model_response=response,
            tool_result=result,
            errors=errors,
            cumulative_usage=manager.usage,
        )
        tool_message = Message(
            role=MessageRole.TOOL,
            content=json.dumps(result.model_dump(mode="json"), sort_keys=True),
            name=result.name,
            tool_call_id=result.call_id,
        )
        state = state.model_copy(
            update={
                "messages": (*state.messages, tool_message),
                "steps": (*state.steps, step),
                "usage": manager.usage,
                "errors": (*state.errors, *errors),
            }
        )
        self.trace.emit(
            TraceEventType.STATE_TRANSITION,
            {"step": step.model_dump(mode="json"), "usage": state.usage.model_dump(mode="json")},
        )
        self.emit_budget(manager, len(state.steps))
        return (
            await self.save(
                state,
                expected_tool_to_node(expected_tool),
                graph_state["interrupt_after_steps"],
            ),
            expected_tool,
        )

    async def model_call(
        self, state: AgentState, manager: BudgetManager
    ) -> ModelResponse | AgentError:
        definitions = tuple(
            definition
            for definition in self.tools.registry.definitions()
            if definition.name in self.definition.safety.allowed_tools
        )
        self.trace.emit(
            TraceEventType.MODEL_REQUEST,
            {
                "messages": [message.model_dump(mode="json") for message in state.messages],
                "tools": [tool.model_dump(mode="json") for tool in definitions],
                "response_schema": AgentDecision.schema_id,
                "settings": {
                    "temperature": 0.0,
                    "max_output_tokens": 1024,
                    "seed": None,
                    "stream": False,
                },
            },
        )
        try:
            response = await self.model.generate(
                state.messages,
                tools=definitions,
                response_schema=AgentDecision,
            )
        except ModelProviderError as error:
            manager.record_model_failure()
            canonical = error.as_agent_error()
            self.trace.emit(TraceEventType.ERROR, {"error": canonical.model_dump(mode="json")})
            return canonical
        manager.record_model_response(response)
        self.trace.emit(
            TraceEventType.MODEL_RESPONSE,
            {"response": response.model_dump(mode="json")},
        )
        self.emit_budget(manager, len(state.steps))
        return response

    async def route_after_step(
        self, graph_state: GraphState, next_node: NodeName, result_name: str
    ) -> GraphState:
        state = self.state(graph_state)
        if state.termination is not None:
            return graph_state
        interrupt_after = graph_state["interrupt_after_steps"]
        if interrupt_after is not None and len(state.steps) >= interrupt_after:
            termination = Termination(
                status=TerminationStatus.INTERRUPTED,
                reason=TerminationReason.HUMAN_INTERRUPTION,
                message="Execution deliberately interrupted after a completed graph step.",
                step_number=len(state.steps),
            )
            state = state.model_copy(update={"termination": termination})
            self.trace.emit(
                TraceEventType.HUMAN_DECISION,
                {
                    "decision": "interrupt",
                    "tool_execution_permitted": False,
                    "completed_tool": result_name,
                },
            )
            self.trace.emit(
                TraceEventType.TERMINATION,
                {"termination": termination.model_dump(mode="json")},
            )
            return await self.save(state, "end", interrupt_after)
        self.trace.emit(
            TraceEventType.DECISION,
            {"route": f"{result_name}_to_{next_node}", "framework_node": result_name},
        )
        return await self.save(state, next_node, interrupt_after)

    async def error(
        self,
        state: AgentState,
        error: AgentError,
        manager: BudgetManager,
        graph_state: GraphState,
        *,
        response: ModelResponse | None = None,
    ) -> GraphState:
        errors = (*state.errors, error)
        steps = state.steps
        if response is not None:
            steps = (
                *steps,
                AgentStep(
                    step_number=len(steps) + 1,
                    status=StepStatus.FAILED,
                    model_response=response,
                    errors=(error,),
                    cumulative_usage=manager.usage,
                ),
            )
        state = state.model_copy(update={"errors": errors, "steps": steps})
        return await self.fail(state, TerminationReason.ERROR, manager, graph_state)

    async def fail(
        self,
        state: AgentState,
        reason: TerminationReason,
        manager: BudgetManager,
        graph_state: GraphState,
    ) -> GraphState:
        termination = Termination(
            status=TerminationStatus.FAILURE,
            reason=reason,
            message=f"Execution stopped: {reason.value}.",
            step_number=len(state.steps),
        )
        state = state.model_copy(update={"usage": manager.usage, "termination": termination})
        self.trace.emit(
            TraceEventType.TERMINATION,
            {"termination": termination.model_dump(mode="json")},
        )
        return await self.save(state, "end", graph_state["interrupt_after_steps"])


def expected_tool_to_node(tool: str) -> NodeName:
    value = {
        "search_catalogue": "search",
        "extract_evidence": "evidence_extraction",
        "critique_draft": "critique",
    }[tool]
    return cast(NodeName, value)


def _route(state: GraphState) -> NodeName:
    return state["next_node"]


class LangGraphCaseStudy:
    """Matched case study whose control flow is expressed as a LangGraph graph."""

    def __init__(
        self,
        *,
        output_root: str | Path = "outputs/runs",
        definition: CaseStudyDefinition | None = None,
        model_factory: CaseStudyModelFactory | None = None,
    ) -> None:
        self.output_root = Path(output_root)
        self.definition = definition or load_definition()
        self.model_factory = model_factory

    async def run(
        self,
        variant_name: CaseStudyVariant,
        *,
        run_id: str,
        resume: bool = False,
        interrupt_after_steps: int | None = None,
        budget: Budget | None = None,
    ) -> AgentState:
        variant = self.definition.variant(variant_name)
        configured_budget = budget or self.definition.budget
        directory = self.output_root / run_id
        trace_path = directory / "trace.jsonl"
        if not resume:
            trace_path.unlink(missing_ok=True)
        trace = TraceWriter(trace_path, run_id=run_id)
        store = JsonCheckpointStore(directory / "checkpoints")
        loaded = await store.load(run_id) if resume else None
        if resume and loaded is None:
            raise ValueError("no canonical checkpoint exists for this run")
        if loaded is not None:
            if (
                loaded.termination is None
                or loaded.termination.status is not TerminationStatus.INTERRUPTED
            ):
                raise ValueError("only interrupted checkpoints may be resumed")
            state = loaded.model_copy(update={"termination": None})
            next_node = _resume_node(state, variant_name)
        else:
            state = AgentState(
                run_id=run_id,
                task=variant.task,
                messages=(
                    Message(
                        role=MessageRole.SYSTEM,
                        content=" ".join(
                            (
                                self.definition.system_prompt,
                                self.definition.planning_prompt,
                                self.definition.synthesis_prompt,
                                self.definition.critique_prompt,
                                CASE_STUDY_PLAN,
                            )
                        ),
                    ),
                    Message(role=MessageRole.USER, content=variant.question),
                ),
                budget=configured_budget,
            )
            next_node = "planning"
            trace.emit(
                TraceEventType.RUN_START,
                {
                    "task": variant.task.model_dump(mode="json"),
                    "budget": configured_budget.model_dump(mode="json"),
                    "orchestrator": "langgraph",
                },
            )
        if self.model_factory is not None:
            model = self.model_factory(variant_name, state.usage.model_calls)
        else:
            fixture_variant = (
                CaseStudyVariant.STANDARD
                if variant_name is CaseStudyVariant.CLARIFICATION_REQUIRED
                else variant_name
            )
            model = build_offline_case_study_model(
                fixture_variant,
                state.usage.model_calls,
            )
        context = _RunContext(
            definition=self.definition,
            variant=variant_name,
            model=model,
            store=store,
            trace=trace,
        )
        graph = _build_graph(context)
        result = await graph.ainvoke(
            {
                "canonical_state": state.model_dump(mode="json"),
                "next_node": next_node,
                "interrupt_after_steps": interrupt_after_steps,
            },
            config={
                "configurable": {"thread_id": run_id},
                "recursion_limit": configured_budget.max_steps * 3 + 8,
            },
        )
        final_state = AgentState.model_validate(result["canonical_state"])
        self._write_outputs(directory, final_state, variant_name, model)
        return final_state

    def _write_outputs(
        self,
        directory: Path,
        state: AgentState,
        variant: CaseStudyVariant,
        model: ModelClient,
    ) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "state.json").write_text(
            state.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        if state.final_answer is not None:
            (directory / "final_answer.json").write_text(
                state.final_answer.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
        candidate_metadata = getattr(model, "manifest_metadata", None)
        model_metadata = (
            TypeAdapter(dict[str, JsonValue]).validate_python(candidate_metadata)
            if candidate_metadata is not None
            else None
        )
        specification_hash = case_study_hash(self.definition)
        manifest = build_run_manifest(
            run_id=state.run_id,
            code_version="working-tree",
            provider=model.provider,
            model=model.model,
            configuration={
                "variant": variant.value,
                "task_specification_hash": specification_hash,
                "budget": state.budget.model_dump(mode="json"),
                "safety_policy_version": self.definition.safety.policy_version,
                "orchestrator": "langgraph",
                "semantic_differences": [
                    "Named graph nodes make routing explicit without adding model calls.",
                    "LangGraph checkpoints are supplemented by canonical JSON "
                    "for cross-process resume.",
                ],
            },
            task_specification_hash=specification_hash,
            safety_policy_version=self.definition.safety.policy_version,
            model_metadata=model_metadata,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            dependencies=("agentic-ai-tutorial", "pydantic", "langgraph"),
        )
        write_manifest(directory / "manifest.json", manifest)


def _build_graph(context: _RunContext) -> Any:
    builder = StateGraph(GraphState)
    # LangGraph's node overloads do not currently accept bound async methods in mypy,
    # although they are supported at runtime. Keep that typing gap inside this adapter.
    builder.add_node("planning", cast(Any, context.planning))
    builder.add_node("search", cast(Any, context.search))
    builder.add_node("evidence_extraction", cast(Any, context.evidence_extraction))
    builder.add_node("synthesis", cast(Any, context.synthesis))
    builder.add_node("critique", cast(Any, context.critique))
    builder.add_node("termination", cast(Any, context.termination))
    routes: dict[Hashable, str] = {
        "planning": "planning",
        "search": "search",
        "evidence_extraction": "evidence_extraction",
        "synthesis": "synthesis",
        "critique": "critique",
        "termination": "termination",
        "end": END,
    }
    builder.add_conditional_edges(START, _route, routes)
    for node in (
        "planning",
        "search",
        "evidence_extraction",
        "synthesis",
        "critique",
        "termination",
    ):
        builder.add_conditional_edges(node, _route, routes)
    return builder.compile(checkpointer=InMemorySaver())


def _resume_node(state: AgentState, variant: CaseStudyVariant) -> NodeName:
    if not state.steps:
        return "planning"
    last = state.steps[-1]
    if last.tool_result is None:
        return "termination"
    if last.tool_result.name == "search_catalogue":
        if last.tool_result.status is not ToolResultStatus.SUCCESS:
            return "search"
        return (
            "synthesis"
            if variant is CaseStudyVariant.INSUFFICIENT_EVIDENCE
            else "evidence_extraction"
        )
    if last.tool_result.name == "extract_evidence":
        return "synthesis"
    return "termination"
