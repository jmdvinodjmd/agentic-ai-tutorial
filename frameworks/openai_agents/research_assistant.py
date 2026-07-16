"""OpenAI Agents SDK orchestration over canonical shared project contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agents import (
    Agent,
    FunctionTool,
    GuardrailFunctionOutput,
    Handoff,
    RunContextWrapper,
    Usage,
    handoff,
    input_guardrail,
    output_guardrail,
)
from openai.types.responses.response_usage import InputTokensDetails
from pydantic import JsonValue, TypeAdapter

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
from agentic_tutorial.case_study.execution import CaseStudyExecution
from agentic_tutorial.case_study.results import finalise_case_study_state
from agentic_tutorial.checkpoints import JsonCheckpointStore
from agentic_tutorial.models import ModelClient
from agentic_tutorial.safety import PolicyToolExecutor, SafetyEngine
from agentic_tutorial.schemas import (
    AgentState,
    Budget,
    FinalAnswer,
    Message,
    MessageRole,
    TerminationStatus,
    ToolCall,
    ToolResultStatus,
)
from agentic_tutorial.tools import ToolRegistry
from agentic_tutorial.tracing import (
    TraceEventType,
    TraceWriter,
    build_run_manifest,
    write_manifest,
)


@dataclass
class SDKRunContext:
    """Ephemeral SDK context; it is never placed in canonical state."""

    trace: TraceWriter
    tools: PolicyToolExecutor
    allowed_tools: tuple[str, ...]
    current_agent: str = "coordinator"


@input_guardrail(name="focused_research_question", run_in_parallel=False)
def _focused_question_guardrail(
    context: RunContextWrapper[Any],
    agent: Agent[Any],
    question: Any,
) -> GuardrailFunctionOutput:
    del context, agent
    valid = isinstance(question, str) and bool(question.strip())
    return GuardrailFunctionOutput(
        output_info={"canonical_input_valid": valid},
        tripwire_triggered=not valid,
    )


@output_guardrail(name="canonical_final_answer")
def _final_answer_guardrail(
    context: RunContextWrapper[SDKRunContext],
    agent: Agent[SDKRunContext],
    answer: FinalAnswer,
) -> GuardrailFunctionOutput:
    del context, agent
    valid = isinstance(answer, FinalAnswer)
    return GuardrailFunctionOutput(
        output_info={"canonical_output_valid": valid},
        tripwire_triggered=not valid,
    )


def _sdk_tool(
    registry: ToolRegistry,
    executor: PolicyToolExecutor,
    name: str,
    allowed_tools: tuple[str, ...],
) -> FunctionTool:
    """Adapt one canonical tool definition to an SDK function tool."""
    registered = registry.get(name)
    if registered is None:
        raise ValueError(f"canonical tool is not registered: {name}")

    async def invoke(_context: Any, raw_arguments: str) -> str:
        arguments = registered.arguments_model.model_validate_json(raw_arguments)
        result = await executor.execute(
            ToolCall(
                call_id=f"sdk-{name}",
                name=name,
                arguments=arguments.model_dump(mode="json"),
            ),
            allowed_tools=allowed_tools,
        )
        return result.model_dump_json()

    definition = registered.definition
    return FunctionTool(
        name=definition.name,
        description=definition.description,
        params_json_schema=definition.parameters,
        on_invoke_tool=invoke,
        strict_json_schema=True,
    )


class OpenAIAgentsStructure:
    """SDK-native specialists, tools, handoffs and guardrails."""

    def __init__(
        self,
        *,
        model_name: str,
        registry: ToolRegistry,
        executor: PolicyToolExecutor,
        allowed_tools: tuple[str, ...],
    ) -> None:
        search_tool = _sdk_tool(registry, executor, "search_catalogue", ("search_catalogue",))
        evidence_tool = _sdk_tool(registry, executor, "extract_evidence", ("extract_evidence",))
        critique_tool = _sdk_tool(registry, executor, "critique_draft", ("critique_draft",))
        common: dict[str, Any] = {"model": model_name}
        self.searcher = Agent[SDKRunContext](
            name="Catalogue search specialist",
            handoff_description="Select sources using catalogue search only.",
            instructions="Use only the shared catalogue-search artefact.",
            tools=[search_tool],
            output_type=str,
            **common,
        )
        self.extractor = Agent[SDKRunContext](
            name="Evidence extraction specialist",
            handoff_description="Extract attributable evidence from selected source IDs.",
            instructions="Use only the shared evidence-extraction artefact.",
            tools=[evidence_tool],
            output_type=str,
            **common,
        )
        self.synthesiser = Agent[SDKRunContext](
            name="Synthesis specialist",
            handoff_description="Synthesise evidence into the canonical answer shape.",
            instructions="Use shared structured evidence; do not call tools.",
            tools=[],
            output_type=FinalAnswer,
            **common,
        )
        self.critic = Agent[SDKRunContext](
            name="Evidence critic",
            handoff_description="Validate claims and source provenance.",
            instructions="Use only the shared critique artefact.",
            tools=[critique_tool],
            output_type=str,
            **common,
        )
        self.coordinator = Agent[SDKRunContext](
            name="Research coordinator",
            instructions="Delegate the fixed bounded stages and terminate explicitly.",
            tools=[],
            handoffs=[
                handoff(self.searcher, tool_name_override="delegate_search"),
                handoff(self.synthesiser, tool_name_override="delegate_synthesis"),
            ],
            input_guardrails=[_focused_question_guardrail],
            output_guardrails=[_final_answer_guardrail],
            output_type=FinalAnswer,
            **common,
        )
        self.handoffs: dict[tuple[str, str], Handoff[SDKRunContext, Agent[SDKRunContext]]] = {
            ("coordinator", "search"): handoff(self.searcher, tool_name_override="delegate_search"),
            ("search", "evidence"): handoff(self.extractor, tool_name_override="delegate_evidence"),
            ("evidence", "synthesis"): handoff(
                self.synthesiser, tool_name_override="delegate_synthesis"
            ),
            ("synthesis", "critique"): handoff(self.critic, tool_name_override="delegate_critique"),
            ("critique", "coordinator"): handoff(
                self.coordinator, tool_name_override="return_to_coordinator"
            ),
        }
        self.permissions = {
            "coordinator": (),
            "search": ("search_catalogue",),
            "evidence": ("extract_evidence",),
            "synthesis": (),
            "critique": ("critique_draft",),
        }
        self.allowed_tools = allowed_tools


class OpenAIAgentsCaseStudy:
    """Matched case study coordinated by bounded SDK handoffs."""

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
        self.last_structure: OpenAIAgentsStructure | None = None

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
            trace.emit(
                TraceEventType.RUN_START,
                {
                    "task": variant.task.model_dump(mode="json"),
                    "budget": configured_budget.model_dump(mode="json"),
                    "orchestrator": "openai-agents-sdk-handoffs",
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
            model = build_offline_case_study_model(fixture_variant, state.usage.model_calls)
        registry = build_case_study_registry(
            fail_searches=(0 if resume else variant.inject_search_failures)
        )
        policy_executor = PolicyToolExecutor(
            registry,
            SafetyEngine(self.definition.safety, trace_writer=trace),
        )
        execution = CaseStudyExecution(
            model,
            policy_executor,
            allowed_tools=self.definition.safety.allowed_tools,
            checkpoint_store=store,
            trace_writer=trace,
        )
        self.last_structure = OpenAIAgentsStructure(
            model_name=model.model,
            registry=registry,
            executor=policy_executor,
            allowed_tools=self.definition.safety.allowed_tools,
        )
        sdk_context = SDKRunContext(
            trace=trace,
            tools=policy_executor,
            allowed_tools=self.definition.safety.allowed_tools,
        )
        # The SDK's default Usage factory in 0.17.8 omits a field required by
        # openai 2.45; providing the complete value keeps the workaround local.
        wrapper = RunContextWrapper(
            sdk_context,
            usage=Usage(
                input_tokens_details=InputTokensDetails(cached_tokens=0, cache_write_tokens=0)
            ),
        )
        input_result = await _maybe_await(
            _focused_question_guardrail.guardrail_function(
                wrapper, self.last_structure.coordinator, variant.question
            )
        )
        trace.emit(
            TraceEventType.POLICY_DECISION,
            {
                "sdk_guardrail": _guardrail_payload(input_result),
                "guardrail": _focused_question_guardrail.name,
            },
        )
        if variant_name is CaseStudyVariant.CLARIFICATION_REQUIRED:
            state = await execution.interrupt(
                state,
                "A comparison target and criterion are required before searching.",
            )
        else:
            state = await self._execute_handoffs(
                state,
                wrapper,
                execution,
                variant_name,
                interrupt_after_steps,
            )
        if state.final_answer is not None:
            output_result = await _maybe_await(
                _final_answer_guardrail.guardrail_function(
                    wrapper, self.last_structure.coordinator, state.final_answer
                )
            )
            trace.emit(
                TraceEventType.POLICY_DECISION,
                {
                    "sdk_guardrail": _guardrail_payload(output_result),
                    "guardrail": _final_answer_guardrail.name,
                },
            )
        self._write_outputs(directory, state, variant_name, model)
        return state

    async def _execute_handoffs(
        self,
        state: AgentState,
        wrapper: RunContextWrapper[SDKRunContext],
        execution: CaseStudyExecution,
        variant: CaseStudyVariant,
        interrupt_after_steps: int | None,
    ) -> AgentState:
        stages = (
            ("coordinator", "search", "search_catalogue"),
            ("search", "evidence", "extract_evidence"),
            ("evidence", "synthesis", None),
            ("synthesis", "critique", "critique_draft"),
            ("critique", "coordinator", "finish"),
        )
        for source, target, action in stages:
            if state.termination is not None:
                break
            if action == "extract_evidence" and variant is CaseStudyVariant.INSUFFICIENT_EVIDENCE:
                continue
            if action is not None and action != "finish" and _completed(state, action):
                continue
            await self._handoff(wrapper, source, target)
            if action is None:
                continue
            if action == "finish":
                state = await execution.finish_step(state)
                if (
                    state.termination is not None
                    and state.termination.status is TerminationStatus.SUCCESS
                ):
                    state = finalise_case_study_state(state, self.definition.variant(variant))
                    state = await execution.save(state)
                continue
            attempts = state.budget.max_failures + 1 if action == "search_catalogue" else 1
            for _ in range(attempts):
                state = await execution.tool_step(state, action)
                if (
                    interrupt_after_steps is not None
                    and len(state.steps) >= interrupt_after_steps
                    and state.termination is None
                ):
                    state = await execution.interrupt(
                        state,
                        "Execution deliberately interrupted after a completed SDK specialist task.",
                    )
                if state.termination is not None:
                    break
                result = state.steps[-1].tool_result
                if result is not None and result.status is ToolResultStatus.SUCCESS:
                    break
                wrapper.context.trace.emit(
                    TraceEventType.DECISION,
                    {
                        "framework": "openai-agents-sdk",
                        "recovery": action,
                        "hidden_model_call": False,
                    },
                )
        return state

    async def _handoff(
        self,
        wrapper: RunContextWrapper[SDKRunContext],
        source: str,
        target: str,
    ) -> None:
        if self.last_structure is None:
            raise RuntimeError("SDK structure is unavailable")
        transfer = self.last_structure.handoffs[(source, target)]
        agent = await transfer.on_invoke_handoff(wrapper, "{}")
        wrapper.context.current_agent = target
        wrapper.context.trace.emit(
            TraceEventType.DECISION,
            {
                "framework": "openai-agents-sdk",
                "handoff": {
                    "source": source,
                    "target": target,
                    "sdk_tool": transfer.tool_name,
                    "agent": agent.name,
                },
                "hidden_model_call": False,
            },
        )

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
                "orchestrator": "openai-agents-sdk-explicit-handoffs",
                "automatic_features": {
                    "runner_model_loop": False,
                    "sdk_tracing_export": "not invoked without Runner",
                    "sdk_retries": False,
                    "sdk_sessions": False,
                    "canonical_checkpoints": True,
                },
                "semantic_differences": [
                    "SDK Agent, FunctionTool, Handoff, RunContextWrapper and guardrail objects "
                    "express specialist orchestration.",
                    "The SDK Runner is not used because it would own message shaping, retries and "
                    "model turns outside the canonical ModelClient contract.",
                    "Canonical JSON checkpoints provide durable interruption and resumption.",
                ],
            },
            task_specification_hash=specification_hash,
            safety_policy_version=self.definition.safety.policy_version,
            model_metadata=model_metadata,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            dependencies=("agentic-ai-tutorial", "pydantic", "openai-agents"),
        )
        write_manifest(directory / "manifest.json", manifest)


def _completed(state: AgentState, tool: str) -> bool:
    return any(
        step.tool_result is not None
        and step.tool_result.name == tool
        and step.tool_result.status is ToolResultStatus.SUCCESS
        for step in state.steps
    )


async def _maybe_await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value


def _guardrail_payload(result: GuardrailFunctionOutput) -> dict[str, Any]:
    return {
        "output_info": result.output_info,
        "tripwire_triggered": result.tripwire_triggered,
    }
