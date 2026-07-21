"""Typed configuration for provider-independent model construction."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class ModelConfigBase(BaseModel):
    """Strict immutable base for model configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ModelProvider(StrEnum):
    """Public provider names accepted through ``MODEL_PROVIDER``."""

    MOCK = "mock"
    LOCAL = "local"
    API = "api"


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
    execution_mode: Literal["mock", "local", "live"] = "mock"


def model_config_from_environment(
    environment: Mapping[str, str],
    *,
    mock_fixture_path: str | None = None,
) -> ModelConfig:
    """Build the selected model configuration without reading credentials.

    Adapters read their own credentials only when they are constructed. Keeping
    secrets out of this serialisable object prevents them reaching traces or
    notebook displays by accident.
    """

    raw_provider = environment.get("MODEL_PROVIDER", ModelProvider.MOCK.value)
    try:
        provider = ModelProvider(raw_provider)
    except ValueError as error:
        choices = ", ".join(item.value for item in ModelProvider)
        raise ValueError(f"MODEL_PROVIDER must be one of: {choices}") from error

    if provider is ModelProvider.MOCK:
        if not mock_fixture_path:
            raise ValueError("mock_fixture_path is required for MODEL_PROVIDER=mock")
        return ModelConfig(
            provider="deterministic-mock",
            model=environment.get("MODEL_NAME", "qualification-mock-v1"),
            execution_mode="mock",
            options={"fixture_path": mock_fixture_path},
        )
    if provider is ModelProvider.LOCAL:
        options: dict[str, JsonValue] = {
            "metadata_path": environment.get(
                "MODEL_METADATA_PATH", "models/local/model_metadata.json"
            )
        }
        model_path = environment.get("AGENTIC_TUTORIAL_LOCAL_MODEL_PATH")
        if model_path:
            options["model_path"] = model_path
        return ModelConfig(
            provider="local-llama-cpp",
            model=environment.get("MODEL_NAME", "Qwen3-0.6B-Q8_0"),
            execution_mode="local",
            options=options,
        )
    return ModelConfig(
        provider="gemini",
        model=environment.get("MODEL_NAME", "gemini-3.1-flash-lite"),
        execution_mode="live",
    )
