"""Transparent framework-independent orchestration for the common case study."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter

from agentic_tutorial.case_study.specification import (
    FIXTURE_ROOT,
    CaseStudyDefinition,
    CaseStudyVariant,
    TaskVariant,
    build_case_study_registry,
    case_study_hash,
    load_definition,
)
from agentic_tutorial.checkpoints import JsonCheckpointStore
from agentic_tutorial.execution import PlainPythonAgent
from agentic_tutorial.models.providers import DeterministicMockClient
from agentic_tutorial.models.providers.fixtures import FixtureProvenance, ScriptedScenarioFixture
from agentic_tutorial.safety import PolicyToolExecutor, SafetyEngine
from agentic_tutorial.schemas import (
    AgentState,
    Budget,
    EvaluationRecord,
    EvidenceItem,
    FinalAnswer,
    FinishReason,
    Message,
    MessageRole,
    ModelResponse,
    Termination,
    TerminationReason,
    TerminationStatus,
    ToolCall,
    Usage,
)
from agentic_tutorial.tracing import (
    TraceEventType,
    TraceWriter,
    build_run_manifest,
    write_manifest,
)


class ScriptedToolAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    action_type: Literal["tool"]
    call_id: str
    name: str
    arguments: dict[str, JsonValue]


class ScriptedFinishAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    action_type: Literal["finish"]
    answer: str


ScriptedAction = Annotated[
    ScriptedToolAction | ScriptedFinishAction, Field(discriminator="action_type")
]


class ModelScripts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    fixture_version: Literal["1"]
    standard: tuple[ScriptedAction, ...]
    insufficient_evidence: tuple[ScriptedAction, ...] = Field(alias="insufficient-evidence")
    clarification_required: tuple[ScriptedAction, ...] = Field(alias="clarification-required")
    tool_failure: tuple[ScriptedAction, ...] = Field(alias="tool-failure")

    def for_variant(self, variant: CaseStudyVariant) -> tuple[ScriptedAction, ...]:
        return {
            CaseStudyVariant.STANDARD: self.standard,
            CaseStudyVariant.INSUFFICIENT_EVIDENCE: self.insufficient_evidence,
            CaseStudyVariant.CLARIFICATION_REQUIRED: self.clarification_required,
            CaseStudyVariant.TOOL_FAILURE: self.tool_failure,
        }[variant]


class PlainPythonCaseStudy:
    """Compose the shared loop and controls into the reference case study."""

    def __init__(
        self,
        *,
        output_root: str | Path = "outputs/runs",
        definition: CaseStudyDefinition | None = None,
    ) -> None:
        self.output_root = Path(output_root)
        self.definition = definition or load_definition()
        self.scripts = ModelScripts.model_validate_json(
            (FIXTURE_ROOT / "model_scripts.json").read_text(encoding="utf-8")
        )

    async def run(
        self,
        variant_name: CaseStudyVariant,
        *,
        run_id: str,
        resume: bool = False,
        interrupt_after_steps: int | None = None,
        budget: Budget | None = None,
    ) -> AgentState:
        """Execute one deterministic variant and write its reproducibility artefacts."""
        variant = self.definition.variant(variant_name)
        configured_budget = budget or self.definition.budget
        run_directory = self.output_root / run_id
        trace_path = run_directory / "trace.jsonl"
        if not resume:
            trace_path.unlink(missing_ok=True)
        trace = TraceWriter(trace_path, run_id=run_id)
        store = JsonCheckpointStore(run_directory / "checkpoints")

        if variant_name is CaseStudyVariant.CLARIFICATION_REQUIRED:
            state = await self._clarification_state(
                variant, run_id, configured_budget, store, trace
            )
        else:
            loaded = await store.load(run_id) if resume else None
            offset = len(loaded.steps) if loaded is not None else 0
            initial_state = None
            if loaded is None:
                plan = "Plan: search, select, extract, synthesise, critique, then terminate."
                initial_state = AgentState(
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
                                    plan,
                                )
                            ),
                        ),
                        Message(role=MessageRole.USER, content=variant.question),
                    ),
                    budget=configured_budget,
                )
            agent = PlainPythonAgent(
                self._model(variant_name, offset=offset),
                PolicyToolExecutor(
                    build_case_study_registry(fail_searches=variant.inject_search_failures),
                    SafetyEngine(self.definition.safety, trace_writer=trace),
                ),
                budget=configured_budget,
                allowed_tools=self.definition.safety.allowed_tools,
                checkpoint_store=store,
                trace_writer=trace,
            )
            state = await agent.run(
                variant.task,
                run_id=run_id,
                initial_state=initial_state,
                resume=resume,
                interrupt_after_steps=interrupt_after_steps,
            )
            if (
                state.termination is not None
                and state.termination.status is TerminationStatus.SUCCESS
            ):
                state = self._attach_final_answer(state, variant)
                await store.save(state)

        self._write_outputs(run_directory, state, variant, run_id)
        return state

    def _model(self, variant: CaseStudyVariant, *, offset: int) -> DeterministicMockClient:
        actions = self.scripts.for_variant(variant)[offset:]
        responses = tuple(
            _response(variant, index + offset + 1, action) for index, action in enumerate(actions)
        )
        fixture = ScriptedScenarioFixture(
            fixture_version="1",
            scenario=f"case-study-{variant.value}-v1",
            provenance=FixtureProvenance(
                source="case_study/fixtures/v1/model_scripts.json",
                description="Deterministic actions for the common case study.",
                recorded_by="repository maintainers",
            ),
            responses=responses,
        )
        return DeterministicMockClient(fixture)

    async def _clarification_state(
        self,
        variant: TaskVariant,
        run_id: str,
        budget: Budget,
        store: JsonCheckpointStore,
        trace: TraceWriter,
    ) -> AgentState:
        state = AgentState(
            run_id=run_id,
            task=variant.task,
            messages=(Message(role=MessageRole.USER, content=variant.question),),
            budget=budget,
            termination=Termination(
                status=TerminationStatus.INTERRUPTED,
                reason=TerminationReason.HUMAN_INTERRUPTION,
                message="A comparison target and criterion are required before searching.",
                step_number=0,
            ),
        )
        trace.emit(
            TraceEventType.RUN_START,
            {
                "task": variant.task.model_dump(mode="json"),
                "budget": budget.model_dump(mode="json"),
            },
        )
        trace.emit(
            TraceEventType.HUMAN_DECISION,
            {"decision": "request_information", "tool_execution_permitted": False},
        )
        await store.save(state)
        trace.emit(TraceEventType.CHECKPOINT, {"run_id": run_id, "step_number": 0})
        trace.emit(
            TraceEventType.TERMINATION,
            {"termination": state.termination.model_dump(mode="json") if state.termination else {}},
        )
        return state

    def _attach_final_answer(self, state: AgentState, variant: TaskVariant) -> AgentState:
        evidence: list[EvidenceItem] = []
        for step in state.steps:
            if step.tool_result is None or step.tool_result.name != "extract_evidence":
                continue
            records = TypeAdapter(list[dict[str, str]]).validate_python(step.tool_result.content)
            evidence.extend(EvidenceItem.model_validate(record) for record in records)
        answer = FinalAnswer(
            task_id=variant.task.task_id,
            answer=variant.expected_answer or "No final answer is available.",
            evidence=tuple(evidence),
            limitations=variant.expected_limitations,
        )
        return AgentState.model_validate(
            {**state.model_dump(mode="json"), "final_answer": answer.model_dump(mode="json")}
        )

    def _write_outputs(
        self,
        directory: Path,
        state: AgentState,
        variant: TaskVariant,
        run_id: str,
    ) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        if state.final_answer is not None:
            (directory / "final_answer.json").write_text(
                state.final_answer.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
        evidence_ids = (
            {item.source_id for item in state.final_answer.evidence}
            if state.final_answer
            else set()
        )
        expected = set(variant.annotation.expected_source_ids)
        evaluation = EvaluationRecord(
            run_id=run_id,
            task_id=variant.task.task_id,
            implementation="plain-python",
            metrics={
                "task_success": state.termination is not None
                and state.termination.status
                in {TerminationStatus.SUCCESS, TerminationStatus.INTERRUPTED},
                "evidence_precision": len(evidence_ids & expected) / len(evidence_ids)
                if evidence_ids
                else (1.0 if not expected else 0.0),
                "evidence_recall": len(evidence_ids & expected) / len(expected)
                if expected
                else 1.0,
                "tool_calls": state.usage.tool_calls,
                "model_calls": state.usage.model_calls,
            },
        )
        (directory / "evaluation.json").write_text(
            evaluation.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        specification_hash = case_study_hash(self.definition)
        manifest = build_run_manifest(
            run_id=run_id,
            code_version="working-tree",
            provider="deterministic-mock",
            model="case-study-script-v1",
            configuration={
                "variant": variant.name.value,
                "task_specification_hash": specification_hash,
                "budget": state.budget.model_dump(mode="json"),
                "safety_policy_version": self.definition.safety.policy_version,
            },
            task_specification_hash=specification_hash,
            safety_policy_version=self.definition.safety.policy_version,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        write_manifest(directory / "manifest.json", manifest)


def _response(variant: CaseStudyVariant, step: int, action: ScriptedAction) -> ModelResponse:
    calls: tuple[ToolCall, ...]
    if isinstance(action, ScriptedToolAction):
        call = ToolCall(call_id=action.call_id, name=action.name, arguments=action.arguments)
        structured = TypeAdapter(dict[str, JsonValue]).validate_python(
            {"action": {"action_type": "tool", "tool_call": call.model_dump(mode="json")}}
        )
        calls = (call,)
        finish_reason = FinishReason.TOOL_CALLS
    else:
        structured = TypeAdapter(dict[str, JsonValue]).validate_python(
            {"action": {"action_type": "finish", "answer": action.answer}}
        )
        calls = ()
        finish_reason = FinishReason.STOP
    return ModelResponse(
        response_id=f"{variant.value}-response-{step}",
        provider="deterministic-mock",
        model="case-study-script-v1",
        message=Message(role=MessageRole.ASSISTANT, content=f"Completed decision {step}."),
        tool_calls=calls,
        structured_output=structured,
        usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15),
        finish_reason=finish_reason,
    )


def run_case_study(
    variant: CaseStudyVariant,
    *,
    run_id: str,
    resume: bool = False,
    interrupt_after_steps: int | None = None,
    budget: Budget | None = None,
) -> AgentState:
    """Synchronous convenience entry point for the command-line example."""
    return asyncio.run(
        PlainPythonCaseStudy().run(
            variant,
            run_id=run_id,
            resume=resume,
            interrupt_after_steps=interrupt_after_steps,
            budget=budget,
        )
    )
