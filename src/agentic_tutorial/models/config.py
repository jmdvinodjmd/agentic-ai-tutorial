"""Typed configuration for provider-independent model construction."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class ModelConfigBase(BaseModel):
    """Strict immutable base for model configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ModelCapabilities(ModelConfigBase):
    """Common model features that callers may test before generation."""

    structured_output: bool = False
    native_tool_calling: bool = False
    streaming: bool = False
    usage_reporting: bool = False


class GenerationSettings(ModelConfigBase):
    """Small common generation settings, avoiding provider-only controls."""

    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=1_024, gt=0)
    seed: int | None = None
    stream: bool = False


class ModelConfig(ModelConfigBase):
    """Configuration used by the registry to select and build a client."""

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    settings: GenerationSettings = Field(default_factory=GenerationSettings)
    options: dict[str, JsonValue] = Field(default_factory=dict)
    execution_mode: Literal["mock", "replay", "live"] = "mock"
