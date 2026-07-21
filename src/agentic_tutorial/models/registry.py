"""Configuration-driven construction without tutorial-level provider imports."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

from pydantic import JsonValue

from agentic_tutorial.models.config import (
    GenerationSettings,
    ModelConfig,
    model_config_from_environment,
)
from agentic_tutorial.models.interface import ModelClient

ModelClientFactory = Callable[[ModelConfig], ModelClient]


class ProviderRegistry:
    """Registry of provider factories keyed by stable configuration names."""

    def __init__(self) -> None:
        self._factories: dict[str, ModelClientFactory] = {}

    def register(
        self, provider: str, factory: ModelClientFactory, *, replace: bool = False
    ) -> None:
        """Register a factory, rejecting accidental replacement by default."""
        if not provider:
            raise ValueError("provider name cannot be empty")
        if provider in self._factories and not replace:
            raise ValueError(f"provider already registered: {provider}")
        self._factories[provider] = factory

    def create(self, config: ModelConfig) -> ModelClient:
        """Construct the client selected entirely by typed configuration."""
        try:
            factory = self._factories[config.provider]
        except KeyError as error:
            available = ", ".join(sorted(self._factories)) or "none"
            raise ValueError(
                f"unknown provider {config.provider!r}; registered providers: {available}"
            ) from error
        return factory(config)

    def registered_providers(self) -> tuple[str, ...]:
        """Return deterministic registry contents for diagnostics."""
        return tuple(sorted(self._factories))


provider_registry = ProviderRegistry()


def create_model_client(
    config: ModelConfig,
    *,
    registry: ProviderRegistry | None = None,
) -> ModelClient:
    """Build a configured client from the supplied or package registry."""
    return (registry or provider_registry).create(config)


def create_model(
    *,
    provider: str,
    mock_fixture_path: str | None = None,
    model: str | None = None,
    model_path: str | Path | None = None,
    metadata_path: str | Path | None = None,
    settings: GenerationSettings | None = None,
    options: Mapping[str, JsonValue] | None = None,
    registry: ProviderRegistry | None = None,
) -> ModelClient:
    """Construct a public provider choice through the existing typed registry.

    ``api`` maps to the registered Gemini adapter. Gemini credentials remain in
    ``GEMINI_API_KEY`` and are deliberately excluded from serialisable config.
    """
    environment = {"MODEL_PROVIDER": provider}
    if model is not None:
        environment["MODEL_NAME"] = model
    if model_path is not None:
        environment["AGENTIC_TUTORIAL_LOCAL_MODEL_PATH"] = str(model_path)
    if metadata_path is not None:
        environment["MODEL_METADATA_PATH"] = str(metadata_path)
    config = model_config_from_environment(
        environment,
        mock_fixture_path=mock_fixture_path,
    )
    merged_options = {**config.options, **dict(options or {})}
    configured = config.model_copy(
        update={
            "options": merged_options,
            "settings": settings or config.settings,
        }
    )
    return create_model_client(configured, registry=registry)
