"""Configuration factory for the deterministic mock client."""

from __future__ import annotations

from pathlib import Path

from agentic_tutorial.models.config import ModelConfig
from agentic_tutorial.models.providers.mock import DeterministicMockClient
from agentic_tutorial.models.registry import ProviderRegistry


def register_offline_providers(registry: ProviderRegistry) -> None:
    """Register the deterministic mock factory once."""
    registry.register("deterministic-mock", _create_mock)


def _create_mock(config: ModelConfig) -> DeterministicMockClient:
    fixture_path = _required_path(config, "fixture_path")
    scenario_value = config.options.get("scenario")
    if scenario_value is not None and not isinstance(scenario_value, str):
        raise ValueError("model option 'scenario' must be a string")
    client = DeterministicMockClient.from_file(fixture_path, scenario=scenario_value)
    _validate_config_identity(config, client.provider, client.model)
    return client


def _required_path(config: ModelConfig, option: str) -> Path:
    value = config.options.get(option)
    if not isinstance(value, str) or not value:
        raise ValueError(f"model option {option!r} must be a non-empty path string")
    return Path(value)


def _validate_config_identity(config: ModelConfig, provider: str, model: str) -> None:
    if provider != "deterministic-mock" or model != config.model:
        raise ValueError(
            "configured provider/model identity does not match the selected offline fixture"
        )
