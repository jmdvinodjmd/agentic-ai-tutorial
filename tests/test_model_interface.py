"""Tests for T02 provider-independent model interfaces."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from pydantic import BaseModel

from agentic_tutorial.models import (
    GenerationSettings,
    ModelCapabilities,
    ModelClient,
    ModelConfig,
    ProviderRegistry,
    RateLimitError,
    UnsupportedCapabilityError,
    create_model_client,
    normalise_provider_exception,
    validate_capabilities,
)
from agentic_tutorial.schemas import (
    FinishReason,
    Message,
    MessageRole,
    ModelResponse,
    ToolDefinition,
    Usage,
)

CAPABILITIES_FIXTURE = Path(__file__).parent / "fixtures" / "models" / "capability_matrix_v1.json"


class FakeVendorRateLimit(Exception):
    """Stand-in for an exception owned by a vendor SDK."""


class FakeClient:
    """Protocol-conforming client with no vendor dependency."""

    def __init__(self, config: ModelConfig) -> None:
        self.provider = config.provider
        self.model = config.model
        self.capabilities = ModelCapabilities()

    async def generate(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolDefinition] = (),
        response_schema: type[BaseModel] | None = None,
        settings: GenerationSettings | None = None,
    ) -> ModelResponse:
        del messages, tools, response_schema, settings
        return ModelResponse(
            response_id="fake-1",
            provider=self.provider,
            model=self.model,
            message=Message(role=MessageRole.ASSISTANT, content="fixture response"),
            usage=Usage(),
            finish_reason=FinishReason.STOP,
        )


def test_fake_client_conforms_to_protocol_without_vendor_sdk() -> None:
    client = FakeClient(ModelConfig(provider="fake", model="fixture"))

    assert isinstance(client, ModelClient)
    response = asyncio.run(client.generate([Message(role=MessageRole.USER, content="hello")]))
    assert response.provider == "fake"
    assert response.model == "fixture"


def test_registry_switches_provider_through_configuration() -> None:
    registry = ProviderRegistry()
    registry.register("first", FakeClient)
    registry.register("second", FakeClient)

    first = create_model_client(ModelConfig(provider="first", model="same"), registry=registry)
    second = create_model_client(ModelConfig(provider="second", model="same"), registry=registry)

    assert first.provider == "first"
    assert second.provider == "second"
    assert registry.registered_providers() == ("first", "second")


def test_unknown_and_duplicate_providers_fail_clearly() -> None:
    registry = ProviderRegistry()
    registry.register("fake", FakeClient)

    with pytest.raises(ValueError, match="already registered"):
        registry.register("fake", FakeClient)
    with pytest.raises(ValueError, match="unknown provider"):
        registry.create(ModelConfig(provider="missing", model="fixture"))


def test_unsupported_features_raise_capability_errors() -> None:
    client = FakeClient(ModelConfig(provider="fake", model="fixture"))
    tool = ToolDefinition(
        name="search",
        description="Search fixed local evidence.",
        parameters={"type": "object"},
    )

    with pytest.raises(UnsupportedCapabilityError, match="tool calling"):
        validate_capabilities(client, tools=[tool])
    with pytest.raises(UnsupportedCapabilityError, match="streaming"):
        validate_capabilities(client, settings=GenerationSettings(stream=True))


def test_fake_adapter_normalises_provider_exception() -> None:
    vendor_error = FakeVendorRateLimit("quota temporarily exceeded")
    error = normalise_provider_exception(
        vendor_error,
        provider="fake",
        mappings={FakeVendorRateLimit: RateLimitError},
    )

    assert isinstance(error, RateLimitError)
    assert error.cause is vendor_error
    assert error.as_agent_error().error_class == "retryable"
    assert error.as_agent_error().source == "fake"


def test_capability_matrix_fixture_is_typed_and_versioned() -> None:
    payload = json.loads(CAPABILITIES_FIXTURE.read_text(encoding="utf-8"))

    assert payload["fixture_version"] == "1"
    capabilities = {
        name: ModelCapabilities.model_validate(values)
        for name, values in payload["clients"].items()
    }
    assert capabilities["offline-scripted"].native_tool_calling
    assert not capabilities["minimal"].usage_reporting
