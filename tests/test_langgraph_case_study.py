"""Matched integration tests for the LangGraph case-study orchestration."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from agentic_tutorial.case_study import CaseStudyVariant, case_study_hash, load_definition
from agentic_tutorial.evaluation import ExperimentConfig, ExperimentRunner
from agentic_tutorial.schemas import (
    AgentState,
    Budget,
    FinalAnswer,
    TerminationReason,
    TerminationStatus,
)
from agentic_tutorial.tracing import TraceEventType, TraceReader, normalise_events
from frameworks.langgraph import LangGraphCaseStudy


@pytest.mark.parametrize(
    ("variant", "expected_steps", "expected_sources"),
    [
        (CaseStudyVariant.STANDARD, 4, {"source-001", "source-002"}),
        (CaseStudyVariant.INSUFFICIENT_EVIDENCE, 3, set()),
        (CaseStudyVariant.TOOL_FAILURE, 5, {"source-002"}),
    ],
)
def test_matched_variants_produce_canonical_answers_and_traces(
    tmp_path: Path,
    variant: CaseStudyVariant,
    expected_steps: int,
    expected_sources: set[str],
) -> None:
    run_id = f"graph-{variant.value}"
    state = asyncio.run(LangGraphCaseStudy(output_root=tmp_path).run(variant, run_id=run_id))

    assert state.termination is not None
    assert state.termination.status is TerminationStatus.SUCCESS
    assert len(state.steps) == expected_steps
    assert state.final_answer is not None
    assert (
        FinalAnswer.model_validate_json(
            (tmp_path / run_id / "final_answer.json").read_text(encoding="utf-8")
        )
        == state.final_answer
    )
    assert {item.source_id for item in state.final_answer.evidence} == expected_sources
    assert all(type(item).__module__.startswith("agentic_tutorial") for item in state.steps)

    events = TraceReader(tmp_path / run_id / "trace.jsonl").read()
    event_types = {event.event_type for event in events}
    assert {
        TraceEventType.MODEL_REQUEST,
        TraceEventType.MODEL_RESPONSE,
        TraceEventType.TOOL_REQUEST,
        TraceEventType.TOOL_RESULT,
        TraceEventType.POLICY_DECISION,
        TraceEventType.BUDGET,
        TraceEventType.CHECKPOINT,
        TraceEventType.TERMINATION,
    } <= event_types


def test_clarification_interrupts_without_model_or_tool_call(tmp_path: Path) -> None:
    state = asyncio.run(
        LangGraphCaseStudy(output_root=tmp_path).run(
            CaseStudyVariant.CLARIFICATION_REQUIRED,
            run_id="graph-clarification",
        )
    )

    assert state.termination is not None
    assert state.termination.status is TerminationStatus.INTERRUPTED
    assert state.usage.model_calls == 0
    assert state.usage.tool_calls == 0
    events = TraceReader(tmp_path / "graph-clarification" / "trace.jsonl").read()
    assert any(event.event_type is TraceEventType.HUMAN_DECISION for event in events)


def test_interruption_and_cross_process_style_resume_preserve_work(tmp_path: Path) -> None:
    first = asyncio.run(
        LangGraphCaseStudy(output_root=tmp_path).run(
            CaseStudyVariant.STANDARD,
            run_id="graph-resume",
            interrupt_after_steps=2,
        )
    )
    resumed = asyncio.run(
        LangGraphCaseStudy(output_root=tmp_path).run(
            CaseStudyVariant.STANDARD,
            run_id="graph-resume",
            resume=True,
        )
    )

    assert first.termination is not None
    assert first.termination.status is TerminationStatus.INTERRUPTED
    assert len(first.steps) == 2
    assert resumed.termination is not None
    assert resumed.termination.status is TerminationStatus.SUCCESS
    assert len(resumed.steps) == 4
    assert resumed.steps[:2] == first.steps
    assert resumed.usage.model_calls == 4
    checkpoint = tmp_path / "graph-resume" / "checkpoints" / "graph-resume.json"
    assert AgentState.model_validate_json(checkpoint.read_text(encoding="utf-8")) == resumed


def test_budget_termination_is_explicit_and_safe(tmp_path: Path) -> None:
    state = asyncio.run(
        LangGraphCaseStudy(output_root=tmp_path).run(
            CaseStudyVariant.STANDARD,
            run_id="graph-budget",
            budget=Budget(max_steps=1),
        )
    )

    assert state.termination is not None
    assert state.termination.status is TerminationStatus.FAILURE
    assert state.termination.reason is TerminationReason.MAX_STEPS
    assert state.usage.tool_calls == 1


def test_repeated_runs_are_deterministic_after_trace_normalisation(tmp_path: Path) -> None:
    implementation = LangGraphCaseStudy(output_root=tmp_path)
    left = asyncio.run(implementation.run(CaseStudyVariant.STANDARD, run_id="graph-repeat-a"))
    right = asyncio.run(implementation.run(CaseStudyVariant.STANDARD, run_id="graph-repeat-b"))

    left_payload = _normalise_state(left)
    right_payload = _normalise_state(right)
    assert left_payload == right_payload
    assert normalise_events(
        TraceReader(tmp_path / "graph-repeat-a" / "trace.jsonl").read()
    ) == normalise_events(TraceReader(tmp_path / "graph-repeat-b" / "trace.jsonl").read())


def test_shared_evaluation_harness_accepts_langgraph(tmp_path: Path) -> None:
    implementation = LangGraphCaseStudy(output_root=tmp_path / "runs")

    async def run(variant: CaseStudyVariant, run_id: str) -> AgentState:
        return await implementation.run(variant, run_id=run_id)

    result = asyncio.run(
        ExperimentRunner(
            run,
            run_root=tmp_path / "runs",
            result_root=tmp_path / "evaluations",
        ).run(
            ExperimentConfig(
                experiment_id="graph-evaluation",
                implementation="langgraph",
                variants=tuple(CaseStudyVariant),
                task_specification_hash=case_study_hash(),
            )
        )
    )

    assert len(result.runs) == 4
    assert result.aggregate.task_completion_rate == 1.0
    assert result.aggregate.final_answer_valid_rate == 1.0
    assert all(run.metrics.trajectory_valid for run in result.runs)


def test_manifest_records_framework_semantics_without_framework_state(tmp_path: Path) -> None:
    state = asyncio.run(
        LangGraphCaseStudy(output_root=tmp_path).run(
            CaseStudyVariant.STANDARD,
            run_id="graph-manifest",
        )
    )
    manifest = json.loads(
        (tmp_path / "graph-manifest" / "manifest.json").read_text(encoding="utf-8")
    )
    definition = load_definition()

    assert manifest["dependencies"]["langgraph"]
    assert manifest["task_specification_hash"] == case_study_hash(definition)
    assert "langgraph" not in state.model_dump_json().casefold()


def _normalise_state(state: AgentState) -> object:
    def visit(value: object) -> object:
        if isinstance(value, dict):
            return {
                key: 0 if key in {"elapsed_ms", "elapsed_seconds"} else visit(item)
                for key, item in value.items()
                if key != "run_id"
            }
        if isinstance(value, list):
            return [visit(item) for item in value]
        if isinstance(value, str) and value.startswith(("{", "[")):
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                return value
            return json.dumps(visit(decoded), sort_keys=True, separators=(",", ":"))
        return value

    return visit(state.model_dump(mode="json"))
