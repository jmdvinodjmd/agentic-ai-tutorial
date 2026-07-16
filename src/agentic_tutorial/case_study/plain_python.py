"""Transparent framework-independent orchestration for the common case study."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from pydantic import JsonValue, TypeAdapter

from agentic_tutorial.case_study.offline import (
    CaseStudyModelFactory,
    build_offline_case_study_model,
)
from agentic_tutorial.case_study.results import finalise_case_study_state
from agentic_tutorial.case_study.specification import (
    CASE_STUDY_PLAN,
    CaseStudyDefinition,
    CaseStudyVariant,
    TaskVariant,
    build_case_study_registry,
    case_study_hash,
    load_definition,
)
from agentic_tutorial.checkpoints import JsonCheckpointStore
from agentic_tutorial.execution import PlainPythonAgent
from agentic_tutorial.models.interface import ModelClient
from agentic_tutorial.safety import PolicyToolExecutor, SafetyEngine
from agentic_tutorial.schemas import (
    AgentState,
    Budget,
    EvaluationRecord,
    Message,
    MessageRole,
    Termination,
    TerminationReason,
    TerminationStatus,
)
from agentic_tutorial.tracing import (
    TraceEventType,
    TraceWriter,
    build_run_manifest,
    write_manifest,
)


class PlainPythonCaseStudy:
    """Compose the shared loop and controls into the reference case study."""

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
        """Execute one deterministic variant and write its reproducibility artefacts."""
        variant = self.definition.variant(variant_name)
        configured_budget = budget or self.definition.budget
        run_directory = self.output_root / run_id
        trace_path = run_directory / "trace.jsonl"
        if not resume:
            trace_path.unlink(missing_ok=True)
        trace = TraceWriter(trace_path, run_id=run_id)
        store = JsonCheckpointStore(run_directory / "checkpoints")
        provider = "deterministic-mock"
        model_name = "case-study-script-v1"
        model_metadata: dict[str, JsonValue] | None = None

        if variant_name is CaseStudyVariant.CLARIFICATION_REQUIRED:
            state = await self._clarification_state(
                variant, run_id, configured_budget, store, trace
            )
        else:
            loaded = await store.load(run_id) if resume else None
            offset = len(loaded.steps) if loaded is not None else 0
            initial_state = None
            if loaded is None:
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
                                    CASE_STUDY_PLAN,
                                )
                            ),
                        ),
                        Message(role=MessageRole.USER, content=variant.question),
                    ),
                    budget=configured_budget,
                )
            model_client = self._model(variant_name, offset=offset)
            provider = model_client.provider
            model_name = model_client.model
            candidate_metadata = getattr(model_client, "manifest_metadata", None)
            if candidate_metadata is not None:
                model_metadata = TypeAdapter(dict[str, JsonValue]).validate_python(
                    candidate_metadata
                )
            agent = PlainPythonAgent(
                model_client,
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
                state = finalise_case_study_state(state, variant)
                await store.save(state)

        self._write_outputs(
            run_directory,
            state,
            variant,
            run_id,
            provider=provider,
            model_name=model_name,
            model_metadata=model_metadata,
        )
        return state

    def _model(self, variant: CaseStudyVariant, *, offset: int) -> ModelClient:
        if self.model_factory is not None:
            return self.model_factory(variant, offset)
        return build_offline_case_study_model(variant, offset)

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

    def _write_outputs(
        self,
        directory: Path,
        state: AgentState,
        variant: TaskVariant,
        run_id: str,
        *,
        provider: str,
        model_name: str,
        model_metadata: dict[str, JsonValue] | None,
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
            provider=provider,
            model=model_name,
            configuration={
                "variant": variant.name.value,
                "task_specification_hash": specification_hash,
                "budget": state.budget.model_dump(mode="json"),
                "safety_policy_version": self.definition.safety.policy_version,
            },
            task_specification_hash=specification_hash,
            safety_policy_version=self.definition.safety.policy_version,
            model_metadata=model_metadata,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        write_manifest(directory / "manifest.json", manifest)


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
