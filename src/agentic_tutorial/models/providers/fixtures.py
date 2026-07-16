"""Strict schemas for versioned offline model fixtures."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentic_tutorial.models.config import GenerationSettings
from agentic_tutorial.schemas import Message, ModelResponse, ToolDefinition


class FixtureModel(BaseModel):
    """Strict immutable fixture base."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class FixtureProvenance(FixtureModel):
    """Human-readable origin information for committed fixtures."""

    source: str = Field(min_length=1)
    description: str = Field(min_length=1)
    recorded_by: str = Field(min_length=1)


class ScriptedScenarioFixture(FixtureModel):
    """A deterministic sequence of canonical model responses."""

    fixture_version: Literal["1"]
    scenario: str = Field(min_length=1)
    provenance: FixtureProvenance
    responses: tuple[ModelResponse, ...] = Field(min_length=1)


class CanonicalRequest(FixtureModel):
    """Request information required to detect replay divergence."""

    messages: tuple[Message, ...]
    tools: tuple[ToolDefinition, ...] = ()
    response_schema: str | None = None
    settings: GenerationSettings = Field(default_factory=GenerationSettings)


class ReplayHeader(FixtureModel):
    """The mandatory first line of a replay JSONL fixture."""

    record_type: Literal["header"]
    fixture_version: Literal["1"]
    scenario: str = Field(min_length=1)
    provenance: FixtureProvenance


class ReplayRecord(FixtureModel):
    """One canonical request-response pair in a replay fixture."""

    record_type: Literal["response"]
    step: int = Field(gt=0)
    request: CanonicalRequest
    response: ModelResponse


class ReplayFixture(FixtureModel):
    """Validated in-memory representation of a JSONL replay."""

    header: ReplayHeader
    records: tuple[ReplayRecord, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_steps(self) -> ReplayFixture:
        actual = [record.step for record in self.records]
        expected = list(range(1, len(self.records) + 1))
        if actual != expected:
            raise ValueError("replay steps must be unique and consecutive from one")
        return self
