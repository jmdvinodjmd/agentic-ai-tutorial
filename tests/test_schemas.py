"""Tests for canonical schemas and state invariants."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from agentic_tutorial.schemas import (
    AgentState,
    Budget,
    Message,
    MessageRole,
    ModelResponse,
    TaskSpec,
    ToolResult,
    Usage,
)

FIXTURE = Path(__file__).parent / "fixtures" / "schemas" / "v1" / "complete_trajectory.json"


def test_representative_schemas_validate() -> None:
    task = TaskSpec(task_id="task-1", objective="Answer from fixed evidence.")
    message = Message(role=MessageRole.USER, content="What does the evidence show?")

    assert task.schema_version == "1"
    assert message.role is MessageRole.USER
    assert Budget().max_steps == 10


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (TaskSpec, {"task_id": "", "objective": "valid"}),
        (Message, {"role": "tool", "content": "result"}),
        (Usage, {"input_tokens": 2, "output_tokens": 3, "total_tokens": 4}),
        (
            ToolResult,
            {"call_id": "call", "name": "search", "status": "error", "error": None},
        ),
        (
            ModelResponse,
            {
                "response_id": "r1",
                "provider": "mock",
                "model": "fixture",
                "finish_reason": "stop",
            },
        ),
    ],
)
def test_malformed_schemas_are_rejected(model: type[Any], payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_complete_v1_trajectory_round_trips_without_loss() -> None:
    fixture_text = FIXTURE.read_text(encoding="utf-8")
    state = AgentState.model_validate_json(fixture_text)
    restored = AgentState.model_validate_json(state.model_dump_json())

    assert restored == state
    assert restored.model_dump(mode="json") == json.loads(fixture_text)
    assert all(step.schema_version == "1" for step in state.steps)


def test_state_rejects_non_consecutive_steps() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["steps"][1]["step_number"] = 3

    with pytest.raises(ValidationError, match="unique and consecutive"):
        AgentState.model_validate(payload)


def test_state_rejects_decreasing_cumulative_usage() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["steps"][1]["cumulative_usage"] = payload["steps"][0]["cumulative_usage"] | {
        "input_tokens": 9,
        "output_tokens": 5,
        "total_tokens": 14,
    }
    payload["usage"] = payload["steps"][1]["cumulative_usage"]

    with pytest.raises(ValidationError, match="monotonic"):
        AgentState.model_validate(payload)


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        TaskSpec(task_id="task-1", objective="valid", vendor_object={})  # type: ignore[call-arg]
