"""Strict schemas for versioned offline model fixtures."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agentic_tutorial.schemas import ModelResponse


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
