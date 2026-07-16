"""Tests for T09 canonical traces and run manifests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from agentic_tutorial.checkpoints import JsonCheckpointStore
from agentic_tutorial.execution import PlainPythonAgent, minimal_research_task
from agentic_tutorial.schemas import Budget
from agentic_tutorial.tools import ToolExecutor, build_tutorial_registry
from agentic_tutorial.tracing import (
    TraceEvent,
    TraceEventType,
    TraceReader,
    TraceWriter,
    build_run_manifest,
    normalise_events,
    write_manifest,
)
from tests.test_agent_loop import ScriptClient, _finish, _search


def test_trace_ordering_and_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    writer = TraceWriter(path, run_id="run-1")
    writer.emit(TraceEventType.RUN_START, {"value": 1})
    writer.emit(TraceEventType.TERMINATION, {"reason": "completed"})
    events = TraceReader(path).read()
    assert [event.sequence for event in events] == [1, 2]
    assert [event.event_type for event in events] == [
        TraceEventType.RUN_START,
        TraceEventType.TERMINATION,
    ]


def test_sanitisation_removes_keys_and_values(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    writer = TraceWriter(path, run_id="safe", redact_values=("credential-value",))
    writer.emit(
        TraceEventType.MODEL_REQUEST,
        {"api_key": "credential-value", "content": "contains credential-value"},
    )
    raw = path.read_text(encoding="utf-8")
    assert "credential-value" not in raw
    assert raw.count("<redacted>") == 2


def test_manifest_is_complete_and_hash_is_deterministic(tmp_path: Path) -> None:
    created = datetime(2026, 1, 1, tzinfo=UTC)
    first = build_run_manifest(
        run_id="manifest-run",
        code_version="revision-1",
        provider="mock",
        model="fixture",
        configuration=Budget(),
        created_at=created,
    )
    second = build_run_manifest(
        run_id="manifest-run",
        code_version="revision-1",
        provider="mock",
        model="fixture",
        configuration=Budget(),
        created_at=created,
    )
    assert first.configuration_hash == second.configuration_hash
    assert first.python_version and first.dependencies and first.environment
    path = tmp_path / "manifest.json"
    write_manifest(path, first)
    assert path.exists()


def test_generated_fields_normalise_deterministically() -> None:
    first = TraceEvent(
        run_id="one",
        sequence=1,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        event_type=TraceEventType.BUDGET,
        payload={"run_id": "one", "elapsed_seconds": 1.2},
    )
    second = first.model_copy(
        update={
            "run_id": "two",
            "timestamp": first.timestamp + timedelta(days=1),
            "payload": {"run_id": "two", "elapsed_seconds": 8.4},
        }
    )
    assert normalise_events([first]) == normalise_events([second])


def test_agent_trace_covers_operational_boundaries(tmp_path: Path) -> None:
    trace_path = tmp_path / "outputs" / "runs" / "traced" / "trace.jsonl"
    agent = PlainPythonAgent(
        ScriptClient([_search(), _finish()]),
        ToolExecutor(build_tutorial_registry()),
        allowed_tools=("catalogue_search",),
        checkpoint_store=JsonCheckpointStore(tmp_path / "checkpoints"),
        trace_writer=TraceWriter(trace_path, run_id="traced"),
    )
    asyncio.run(agent.run(minimal_research_task(), run_id="traced"))
    types = {event.event_type for event in TraceReader(trace_path).read()}
    assert {
        TraceEventType.RUN_START,
        TraceEventType.MODEL_REQUEST,
        TraceEventType.MODEL_RESPONSE,
        TraceEventType.DECISION,
        TraceEventType.TOOL_REQUEST,
        TraceEventType.TOOL_RESULT,
        TraceEventType.STATE_TRANSITION,
        TraceEventType.BUDGET,
        TraceEventType.CHECKPOINT,
        TraceEventType.TERMINATION,
    } <= types


def test_committed_example_trace_is_readable() -> None:
    path = Path(__file__).parent / "fixtures" / "tracing" / "example_trace_v1.jsonl"
    assert len(TraceReader(path).read()) == 2
