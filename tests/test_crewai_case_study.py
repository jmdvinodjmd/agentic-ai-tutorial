"""Matched integration tests for the CrewAI case-study orchestration."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from agentic_tutorial.case_study import CaseStudyVariant, case_study_hash
from agentic_tutorial.evaluation import ExperimentConfig, ExperimentRunner
from agentic_tutorial.schemas import (
    AgentState,
    Budget,
    FinalAnswer,
    TerminationReason,
    TerminationStatus,
)
from agentic_tutorial.tracing import TraceEventType, TraceReader, normalise_events
from frameworks.crewai import CrewAICaseStudy


@pytest.mark.parametrize(
    ("variant", "model_calls", "tool_calls", "expected_sources"),
    [
        (CaseStudyVariant.STANDARD, 4, 3, {"source-001", "source-002"}),
        (CaseStudyVariant.INSUFFICIENT_EVIDENCE, 3, 2, set()),
        (CaseStudyVariant.TOOL_FAILURE, 5, 4, {"source-002"}),
    ],
)
def test_matched_variants_and_complete_call_accounting(
    tmp_path: Path,
    variant: CaseStudyVariant,
    model_calls: int,
    tool_calls: int,
    expected_sources: set[str],
) -> None:
    run_id = f"crew-{variant.value}"
    implementation = CrewAICaseStudy(output_root=tmp_path)
    state = asyncio.run(implementation.run(variant, run_id=run_id))

    assert state.termination is not None
    assert state.termination.status is TerminationStatus.SUCCESS
    assert state.usage.model_calls == model_calls
    assert state.usage.tool_calls == tool_calls
    assert state.final_answer is not None
    assert (
        FinalAnswer.model_validate_json(
            (tmp_path / run_id / "final_answer.json").read_text(encoding="utf-8")
        )
        == state.final_answer
    )
    assert {item.source_id for item in state.final_answer.evidence} == expected_sources
    assert implementation.last_structure is not None
    assert implementation.last_structure.sentinel.calls == 0

    events = TraceReader(tmp_path / run_id / "trace.jsonl").read()
    assert sum(event.event_type is TraceEventType.MODEL_RESPONSE for event in events) == model_calls
    assert sum(event.event_type is TraceEventType.TOOL_RESULT for event in events) == tool_calls
    event_types = {event.event_type for event in events}
    assert {
        TraceEventType.POLICY_DECISION,
        TraceEventType.BUDGET,
        TraceEventType.CHECKPOINT,
        TraceEventType.TERMINATION,
    } <= event_types


def test_specialists_have_distinct_tasks_permissions_and_outputs(tmp_path: Path) -> None:
    implementation = CrewAICaseStudy(output_root=tmp_path)
    asyncio.run(implementation.run(CaseStudyVariant.STANDARD, run_id="crew-specialists"))
    structure = implementation.last_structure
    assert structure is not None

    assert (
        len(
            {
                agent.role
                for agent in (
                    structure.coordinator,
                    structure.searcher,
                    structure.extractor,
                    structure.synthesiser,
                    structure.critic,
                )
            }
        )
        == 5
    )
    assert structure.task_permissions == (
        (),
        ("search_catalogue",),
        ("extract_evidence",),
        (),
        ("critique_draft",),
    )
    assert len({task.description for task in structure.tasks}) == 5
    assert len({task.expected_output for task in structure.tasks}) == 5


def test_clarification_interrupts_without_specialist_calls(tmp_path: Path) -> None:
    state = asyncio.run(
        CrewAICaseStudy(output_root=tmp_path).run(
            CaseStudyVariant.CLARIFICATION_REQUIRED,
            run_id="crew-clarification",
        )
    )

    assert state.termination is not None
    assert state.termination.status is TerminationStatus.INTERRUPTED
    assert state.usage.model_calls == 0
    assert state.usage.tool_calls == 0


def test_interruption_and_resume_do_not_repeat_successful_tasks(tmp_path: Path) -> None:
    first = asyncio.run(
        CrewAICaseStudy(output_root=tmp_path).run(
            CaseStudyVariant.STANDARD,
            run_id="crew-resume",
            interrupt_after_steps=2,
        )
    )
    resumed = asyncio.run(
        CrewAICaseStudy(output_root=tmp_path).run(
            CaseStudyVariant.STANDARD,
            run_id="crew-resume",
            resume=True,
        )
    )

    assert first.termination is not None
    assert first.termination.status is TerminationStatus.INTERRUPTED
    assert len(first.steps) == 2
    assert resumed.termination is not None
    assert resumed.termination.status is TerminationStatus.SUCCESS
    assert resumed.steps[:2] == first.steps
    assert resumed.usage.model_calls == 4
    assert resumed.usage.tool_calls == 3


def test_budget_termination_stops_delegation_safely(tmp_path: Path) -> None:
    state = asyncio.run(
        CrewAICaseStudy(output_root=tmp_path).run(
            CaseStudyVariant.STANDARD,
            run_id="crew-budget",
            budget=Budget(max_steps=1),
        )
    )

    assert state.termination is not None
    assert state.termination.status is TerminationStatus.FAILURE
    assert state.termination.reason is TerminationReason.MAX_STEPS
    assert state.usage.model_calls == 1
    assert state.usage.tool_calls == 1


def test_repeated_runs_are_deterministic_after_normalisation(tmp_path: Path) -> None:
    implementation = CrewAICaseStudy(output_root=tmp_path)
    left = asyncio.run(implementation.run(CaseStudyVariant.STANDARD, run_id="crew-repeat-a"))
    right = asyncio.run(implementation.run(CaseStudyVariant.STANDARD, run_id="crew-repeat-b"))

    assert _normalise_state(left) == _normalise_state(right)
    assert normalise_events(
        TraceReader(tmp_path / "crew-repeat-a" / "trace.jsonl").read()
    ) == normalise_events(TraceReader(tmp_path / "crew-repeat-b" / "trace.jsonl").read())


def test_shared_evaluation_harness_accepts_crewai(tmp_path: Path) -> None:
    implementation = CrewAICaseStudy(output_root=tmp_path / "runs")

    async def run(variant: CaseStudyVariant, run_id: str) -> AgentState:
        return await implementation.run(variant, run_id=run_id)

    result = asyncio.run(
        ExperimentRunner(
            run,
            run_root=tmp_path / "runs",
            result_root=tmp_path / "evaluations",
        ).run(
            ExperimentConfig(
                experiment_id="crew-evaluation",
                implementation="crewai-flow",
                variants=tuple(CaseStudyVariant),
                task_specification_hash=case_study_hash(),
            )
        )
    )

    assert len(result.runs) == 4
    assert result.aggregate.task_completion_rate == 1.0
    assert result.aggregate.final_answer_valid_rate == 1.0
    assert result.aggregate.mean_model_calls == 3.0
    assert result.aggregate.mean_tool_calls == 2.25
    assert all(run.metrics.trajectory_valid for run in result.runs)


def test_manifest_and_state_contain_no_crewai_objects(tmp_path: Path) -> None:
    state = asyncio.run(
        CrewAICaseStudy(output_root=tmp_path).run(
            CaseStudyVariant.STANDARD,
            run_id="crew-manifest",
        )
    )
    manifest = json.loads(
        (tmp_path / "crew-manifest" / "manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["dependencies"]["crewai"] == "1.15.2"
    assert manifest["task_specification_hash"] == case_study_hash()
    assert "crewai" not in state.model_dump_json().casefold()
    assert all(type(step).__module__.startswith("agentic_tutorial") for step in state.steps)


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
