"""CrewAI Flow orchestration over canonical shared project contracts."""
# ruff: noqa: E402

from __future__ import annotations

import os
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, JsonValue, TypeAdapter

# CrewAI computes an application-data directory while importing. Contain that
# framework-owned cache in a temporary location rather than the user's profile.
_STORAGE_ROOT = str(Path(tempfile.gettempdir()) / "agentic-ai-tutorial-crewai")
_FRAMEWORK_ENV = {
    "HOME": _STORAGE_ROOT,
    "XDG_DATA_HOME": _STORAGE_ROOT,
    "APPDATA": _STORAGE_ROOT,
    "LOCALAPPDATA": _STORAGE_ROOT,
    "CREWAI_DISABLE_TRACKING": "true",
    "CREWAI_TRACING_ENABLED": "false",
    "OTEL_SDK_DISABLED": "true",
}


def _set_framework_environment() -> dict[str, str | None]:
    original = {name: os.environ.get(name) for name in _FRAMEWORK_ENV}
    os.environ.update(_FRAMEWORK_ENV)
    return original


def _restore_environment(original: dict[str, str | None]) -> None:
    for name, value in original.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


_ORIGINAL_ENV = _set_framework_environment()
try:
    from crewai.agent.core import Agent
    from crewai.agents.agent_builder.base_agent import BaseAgent
    from crewai.flow.flow import Flow, listen, start
    from crewai.llms.base_llm import BaseLLM
    from crewai.task import Task
    from crewai.utilities.types import LLMMessage
finally:
    _restore_environment(_ORIGINAL_ENV)

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
    ToolResult,
    ToolResultStatus,
)
from agentic_tutorial.tracing import (
    TraceEventType,
    TraceWriter,
    build_run_manifest,
    write_manifest,
)


class _NoHiddenCallsLLM(BaseLLM):
    """Sentinel proving CrewAI does not perform unaccounted model calls."""

    calls: int = 0

    def call(
        self,
        messages: str | list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        callbacks: list[Any] | None = None,
        available_functions: dict[str, Any] | None = None,
        from_task: Task | None = None,
        from_agent: BaseAgent | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> str:
        del messages, tools, callbacks, available_functions, from_task, from_agent
        del response_model
        self.calls += 1
        raise RuntimeError("CrewAI attempted an unaccounted model call")


class CrewFlowState(BaseModel):
    """JSON-compatible state exchanged between CrewAI Flow specialists."""

    model_config = ConfigDict(extra="forbid")
    canonical_state: dict[str, Any]
    interrupt_after_steps: int | None = None


class CrewStructure:
    """Real CrewAI agents and tasks used as bounded specialist assignments."""

    def __init__(self, model_name: str) -> None:
        self.sentinel = _NoHiddenCallsLLM(
            model=model_name,
            provider="canonical-model-client",
            temperature=0.0,
            max_tokens=1024,
        )
        common = {
            "llm": self.sentinel,
            "cache": False,
            "memory": False,
            "allow_delegation": False,
            "max_iter": 1,
            "max_retry_limit": 0,
            "planning": False,
            "reasoning": False,
            "allow_code_execution": False,
            "verbose": False,
        }
        self.coordinator = Agent(
            role="Research coordinator",
            goal="Delegate the fixed bounded research stages without adding model calls.",
            backstory="Coordinates only the centrally specified research task.",
            **common,
        )
        self.searcher = Agent(
            role="Catalogue search specialist",
            goal="Select sources using only the canonical catalogue-search tool.",
            backstory="Receives the focused question and search-only permission.",
            **common,
        )
        self.extractor = Agent(
            role="Evidence extraction specialist",
            goal="Extract attributable evidence from selected source identifiers.",
            backstory="Receives selected identifiers and extraction-only permission.",
            **common,
        )
        self.synthesiser = Agent(
            role="Synthesis specialist",
            goal="Prepare the concise evidence-grounded answer artefact.",
            backstory="Receives canonical evidence and has no tool permission.",
            **common,
        )
        self.critic = Agent(
            role="Evidence critic",
            goal="Validate claims and provenance with the canonical critique tool.",
            backstory="Receives the draft and critique-only permission.",
            **common,
        )
        self.tasks = (
            Task(
                name="coordinate",
                description="Decompose the central task into its fixed bounded stages.",
                expected_output="A deterministic delegation route.",
                agent=self.coordinator,
                config={"allowed_tools": []},
            ),
            Task(
                name="search",
                description="Search and select sources for the focused question.",
                expected_output="One canonical search ToolResult.",
                output_pydantic=ToolResult,
                agent=self.searcher,
                config={"allowed_tools": ["search_catalogue"]},
            ),
            Task(
                name="extract",
                description="Extract canonical evidence from selected sources.",
                expected_output="One canonical evidence ToolResult.",
                output_pydantic=ToolResult,
                agent=self.extractor,
                config={"allowed_tools": ["extract_evidence"]},
            ),
            Task(
                name="synthesise",
                description="Exchange canonical evidence as a bounded draft artefact.",
                expected_output="A canonical FinalAnswer draft.",
                output_pydantic=FinalAnswer,
                agent=self.synthesiser,
                config={"allowed_tools": []},
            ),
            Task(
                name="critique",
                description="Validate draft claims and evidence provenance.",
                expected_output="One canonical critique ToolResult.",
                output_pydantic=ToolResult,
                agent=self.critic,
                config={"allowed_tools": ["critique_draft"]},
            ),
        )
        self.task_permissions = (
            (),
            ("search_catalogue",),
            ("extract_evidence",),
            (),
            ("critique_draft",),
        )


class _MatchedResearchFlow(Flow[CrewFlowState]):
    """CrewAI-native sequential Flow with explicit specialist boundaries."""

    _skip_auto_memory: ClassVar[bool] = True

    @property
    def context(self) -> _CrewRunContext:
        value = self.execution_context
        if not isinstance(value, _CrewRunContext):
            raise RuntimeError("CrewAI flow execution context is unavailable")
        return value

    def canonical(self) -> AgentState:
        return AgentState.model_validate(self.state.canonical_state)

    def update(self, state: AgentState) -> AgentState:
        self.state.canonical_state = state.model_dump(mode="json")
        return state

    @start()
    async def coordinate(self) -> AgentState:
        state = self.canonical()
        self.context.delegate("coordinate", "search")
        if self.context.variant_name is CaseStudyVariant.CLARIFICATION_REQUIRED:
            state = await self.context.execution.interrupt(
                state,
                "A comparison target and criterion are required before searching.",
            )
        return self.update(state)

    @listen(coordinate)
    async def search(self, _previous: AgentState) -> AgentState:
        state = self.canonical()
        if self.context.stopped(state) or self.context.completed(state, "search_catalogue"):
            return state
        self.context.delegate("search", "search_catalogue")
        attempts = state.budget.max_failures + 1
        for _ in range(attempts):
            state = await self.context.execution.tool_step(state, "search_catalogue")
            self.update(state)
            state = await self.context.maybe_interrupt(state)
            self.update(state)
            if self.context.stopped(state):
                break
            result = state.steps[-1].tool_result
            if result is not None and result.status is ToolResultStatus.SUCCESS:
                break
            self.context.delegate("search_recovery", "search_catalogue")
        return state

    @listen(search)
    async def extract(self, _previous: AgentState) -> AgentState:
        state = self.canonical()
        if (
            self.context.stopped(state)
            or self.context.variant_name is CaseStudyVariant.INSUFFICIENT_EVIDENCE
            or self.context.completed(state, "extract_evidence")
        ):
            return state
        self.context.delegate("extract", "extract_evidence")
        state = await self.context.execution.tool_step(state, "extract_evidence")
        state = await self.context.maybe_interrupt(state)
        return self.update(state)

    @listen(extract)
    async def synthesise(self, _previous: AgentState) -> AgentState:
        state = self.canonical()
        if self.context.stopped(state):
            return state
        self.context.delegate("synthesise", "critique")
        return state

    @listen(synthesise)
    async def critique(self, _previous: AgentState) -> AgentState:
        state = self.canonical()
        if self.context.stopped(state) or self.context.completed(state, "critique_draft"):
            return state
        self.context.delegate("critique", "critique_draft")
        state = await self.context.execution.tool_step(state, "critique_draft")
        state = await self.context.maybe_interrupt(state)
        return self.update(state)

    @listen(critique)
    async def terminate(self, _previous: AgentState) -> AgentState:
        state = self.canonical()
        if self.context.stopped(state):
            return state
        self.context.delegate("terminate", "canonical_finish")
        state = await self.context.execution.finish_step(state)
        if state.termination is not None and state.termination.status is TerminationStatus.SUCCESS:
            state = finalise_case_study_state(state, self.context.variant)
            state = await self.context.execution.save(state)
        return self.update(state)


class _CrewRunContext:
    def __init__(
        self,
        *,
        definition: CaseStudyDefinition,
        variant_name: CaseStudyVariant,
        execution: CaseStudyExecution,
        trace: TraceWriter,
    ) -> None:
        self.definition = definition
        self.variant_name = variant_name
        self.variant = definition.variant(variant_name)
        self.execution = execution
        self.trace = trace

    def delegate(self, task: str, target: str) -> None:
        self.trace.emit(
            TraceEventType.DECISION,
            {
                "delegation": {"task": task, "target": target},
                "framework": "crewai",
                "hidden_model_call": False,
            },
        )

    def stopped(self, state: AgentState) -> bool:
        return state.termination is not None

    def completed(self, state: AgentState, tool: str) -> bool:
        return any(
            step.tool_result is not None
            and step.tool_result.name == tool
            and step.tool_result.status is ToolResultStatus.SUCCESS
            for step in state.steps
        )

    async def maybe_interrupt(self, state: AgentState) -> AgentState:
        limit = self.interrupt_after_steps
        if limit is not None and len(state.steps) >= limit and state.termination is None:
            return await self.execution.interrupt(
                state,
                "Execution deliberately interrupted after a completed specialist task.",
            )
        return state

    interrupt_after_steps: int | None = None


class CrewAICaseStudy:
    """Matched case study coordinated by a bounded CrewAI Flow."""

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
        self.last_structure: CrewStructure | None = None

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
                    "orchestrator": "crewai-flow",
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
        execution = CaseStudyExecution(
            model,
            PolicyToolExecutor(
                build_case_study_registry(
                    fail_searches=(0 if resume else variant.inject_search_failures),
                ),
                SafetyEngine(self.definition.safety, trace_writer=trace),
            ),
            allowed_tools=self.definition.safety.allowed_tools,
            checkpoint_store=store,
            trace_writer=trace,
        )
        context = _CrewRunContext(
            definition=self.definition,
            variant_name=variant_name,
            execution=execution,
            trace=trace,
        )
        context.interrupt_after_steps = interrupt_after_steps
        self.last_structure = CrewStructure(model.model)
        original_environment = _set_framework_environment()
        try:
            flow = _MatchedResearchFlow(
                initial_state=CrewFlowState(
                    canonical_state=state.model_dump(mode="json"),
                    interrupt_after_steps=interrupt_after_steps,
                ),
                execution_context=context,
                tracing=False,
                memory=None,
                max_method_calls=8,
                suppress_flow_events=True,
            )
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                await flow.kickoff_async()
        finally:
            _restore_environment(original_environment)
        final_state = AgentState.model_validate(flow.state.canonical_state)
        if self.last_structure.sentinel.calls:
            raise RuntimeError("CrewAI made an unaccounted model call")
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
                "orchestrator": "crewai-flow-sequential",
                "automatic_features": {
                    "cache": False,
                    "delegation": False,
                    "manager_calls": False,
                    "memory": False,
                    "planning": False,
                    "retries": False,
                    "telemetry": False,
                },
                "semantic_differences": [
                    "CrewAI agents and tasks define specialist ownership.",
                    "CrewAI autonomous calls are disabled; canonical ModelClient "
                    "calls are explicit.",
                    "Canonical JSON checkpoints provide interruption and resumption.",
                ],
            },
            task_specification_hash=specification_hash,
            safety_policy_version=self.definition.safety.policy_version,
            model_metadata=model_metadata,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            dependencies=("agentic-ai-tutorial", "pydantic", "crewai"),
        )
        write_manifest(directory / "manifest.json", manifest)
