"""Provider- and framework-independent operational trace events."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class TraceEventType(StrEnum):
    RUN_START = "run_start"
    MODEL_REQUEST = "model_request"
    MODEL_RESPONSE = "model_response"
    DECISION = "decision"
    TOOL_REQUEST = "tool_request"
    TOOL_RESULT = "tool_result"
    STATE_TRANSITION = "state_transition"
    BUDGET = "budget"
    CHECKPOINT = "checkpoint"
    HUMAN_DECISION = "human_decision"
    ERROR = "error"
    TERMINATION = "termination"


class TraceEvent(BaseModel):
    """One append-only event with a monotonic per-run sequence number."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    trace_schema_version: Literal["1"] = "1"
    run_id: str = Field(min_length=1)
    sequence: int = Field(gt=0)
    timestamp: datetime
    event_type: TraceEventType
    payload: dict[str, JsonValue] = Field(default_factory=dict)
