"""Focused tests for the six execution-pattern groups."""

from pathlib import Path

from agentic_tutorial.education import PATTERN_NAMES, run_pattern
from agentic_tutorial.tracing import TraceEventType, TraceReader


def test_every_pattern_is_deterministic_and_documents_limitation() -> None:
    for name in PATTERN_NAMES:
        first = run_pattern(name)
        assert first == run_pattern(name)
        assert first["limitation"]


def test_parallel_results_have_stable_order() -> None:
    result = run_pattern("routing-parallelisation")
    assert result["ordered_results"] == ["evidence", "claims:complete", "metadata:complete"]


def test_multi_agent_workers_have_functional_separation() -> None:
    result = run_pattern("orchestrator-worker")
    assert result["separate_permissions"] is True
    assert result["researcher_output"] != result["analyst_output"]


def test_pattern_uses_canonical_trace_events() -> None:
    run_pattern("prompt-chaining")
    events = TraceReader(Path("outputs/runs/pattern-prompt-chaining/trace.jsonl")).read()
    assert [event.event_type for event in events] == [
        TraceEventType.RUN_START,
        TraceEventType.DECISION,
        TraceEventType.TERMINATION,
    ]
