"""End-to-end tests for the framework-independent research assistant."""

from __future__ import annotations

import asyncio
from pathlib import Path

from agentic_tutorial.case_study import (
    CaseStudyVariant,
    build_case_study_registry,
    case_study_hash,
    load_definition,
)
from agentic_tutorial.case_study.plain_python import PlainPythonCaseStudy
from agentic_tutorial.schemas import (
    Budget,
    FinalAnswer,
    TerminationReason,
    TerminationStatus,
    ToolCall,
    ToolResultStatus,
)
from agentic_tutorial.tools import ToolExecutor
from agentic_tutorial.tracing import RunManifest, TraceEventType, TraceReader, normalise_events


def _runner(tmp_path: Path) -> PlainPythonCaseStudy:
    return PlainPythonCaseStudy(output_root=tmp_path / "outputs")


def test_standard_success_has_valid_provenance_and_outputs(tmp_path: Path) -> None:
    state = asyncio.run(_runner(tmp_path).run(CaseStudyVariant.STANDARD, run_id="standard"))
    assert state.termination is not None and state.termination.status is TerminationStatus.SUCCESS
    assert state.final_answer is not None
    assert {item.source_id for item in state.final_answer.evidence} == {
        "source-001",
        "source-002",
    }
    FinalAnswer.model_validate_json(state.final_answer.model_dump_json())
    for name in ("trace.jsonl", "manifest.json", "evaluation.json", "final_answer.json"):
        assert (tmp_path / "outputs" / "standard" / name).exists()
    manifest = RunManifest.model_validate_json(
        (tmp_path / "outputs" / "standard" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest.task_specification_hash == case_study_hash()
    event_types = {
        event.event_type
        for event in TraceReader(tmp_path / "outputs" / "standard" / "trace.jsonl").read()
    }
    assert {
        TraceEventType.MODEL_REQUEST,
        TraceEventType.TOOL_REQUEST,
        TraceEventType.STATE_TRANSITION,
        TraceEventType.BUDGET,
        TraceEventType.CHECKPOINT,
        TraceEventType.TERMINATION,
    } <= event_types


def test_insufficient_evidence_is_explicit(tmp_path: Path) -> None:
    state = asyncio.run(
        _runner(tmp_path).run(CaseStudyVariant.INSUFFICIENT_EVIDENCE, run_id="insufficient")
    )
    assert state.final_answer is not None
    assert not state.final_answer.evidence
    assert "insufficient" in state.final_answer.answer.casefold()


def test_ambiguous_question_interrupts_without_tool_execution(tmp_path: Path) -> None:
    state = asyncio.run(
        _runner(tmp_path).run(CaseStudyVariant.CLARIFICATION_REQUIRED, run_id="clarify")
    )
    assert state.termination is not None
    assert state.termination.status is TerminationStatus.INTERRUPTED
    assert state.usage.tool_calls == 0 and not state.steps


def test_controlled_tool_failure_recovers_once(tmp_path: Path) -> None:
    state = asyncio.run(_runner(tmp_path).run(CaseStudyVariant.TOOL_FAILURE, run_id="recovery"))
    assert state.termination is not None and state.termination.status is TerminationStatus.SUCCESS
    assert state.usage.failures == 1
    assert state.final_answer is not None
    assert {item.source_id for item in state.final_answer.evidence} == {"source-002"}


def test_budget_termination_is_explicit(tmp_path: Path) -> None:
    state = asyncio.run(
        _runner(tmp_path).run(
            CaseStudyVariant.STANDARD,
            run_id="bounded",
            budget=Budget(max_steps=1),
        )
    )
    assert state.termination is not None
    assert state.termination.reason is TerminationReason.MAX_STEPS
    assert state.final_answer is None


def test_normalised_repeated_runs_are_deterministic(tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    first = asyncio.run(runner.run(CaseStudyVariant.STANDARD, run_id="repeat-a"))
    second = asyncio.run(runner.run(CaseStudyVariant.STANDARD, run_id="repeat-b"))
    assert first.final_answer == second.final_answer
    first_events = TraceReader(tmp_path / "outputs" / "repeat-a" / "trace.jsonl").read()
    second_events = TraceReader(tmp_path / "outputs" / "repeat-b" / "trace.jsonl").read()
    assert normalise_events(first_events) == normalise_events(second_events)


def test_checkpoint_resume_preserves_work_and_budget(tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    interrupted = asyncio.run(
        runner.run(
            CaseStudyVariant.STANDARD,
            run_id="resume",
            interrupt_after_steps=2,
        )
    )
    resumed = asyncio.run(runner.run(CaseStudyVariant.STANDARD, run_id="resume", resume=True))
    assert interrupted.termination is not None
    assert interrupted.termination.status is TerminationStatus.INTERRUPTED
    assert (
        resumed.termination is not None and resumed.termination.status is TerminationStatus.SUCCESS
    )
    assert len(resumed.steps) == 4
    assert resumed.usage.model_calls == 4
    assert resumed.budget == load_definition().budget


def test_unauthorised_tool_execution_is_denied() -> None:
    definition = load_definition()
    assert "filesystem_write" not in definition.safety.allowed_tools
    assert definition.safety.side_effects_permitted is False
    result = asyncio.run(
        ToolExecutor(build_case_study_registry()).execute(
            ToolCall(
                call_id="denied",
                name="search_catalogue",
                arguments={"query": "agent evaluation"},
            ),
            allowed_tools=(),
        )
    )
    assert result.status is ToolResultStatus.DENIED
    assert result.error is not None and result.error.code == "unauthorised_tool"
