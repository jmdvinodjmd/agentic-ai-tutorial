"""Canonical operational trace tests."""

from datetime import UTC, datetime
from pathlib import Path

from agentic_tutorial.tracing import TraceEventType, TraceReader, TraceWriter, normalise_events


def test_trace_round_trip_is_ordered_and_normalisable(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    writer = TraceWriter(path, run_id="run-1")
    writer.emit(
        TraceEventType.RUN_START,
        {"task_id": "food-waste-pattern"},
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )
    writer.emit(
        TraceEventType.TERMINATION,
        {"reason": "criteria_met"},
        timestamp=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
    )

    events = TraceReader(path).read()

    assert [event.sequence for event in events] == [1, 2]
    assert [event.event_type for event in events] == [
        TraceEventType.RUN_START,
        TraceEventType.TERMINATION,
    ]
    assert b'"run_id":"<run_id>"' in normalise_events(events)
