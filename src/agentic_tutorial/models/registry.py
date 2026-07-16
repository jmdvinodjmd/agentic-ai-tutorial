"""Configuration-driven construction without tutorial-level provider imports."""

from __future__ import annotations

from collections.abc import Callable

from agentic_tutorial.models.config import ModelConfig
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
