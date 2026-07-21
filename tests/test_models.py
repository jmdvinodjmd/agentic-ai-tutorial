"""Provider selection and thin-adapter contract tests."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from agentic_tutorial.models import (
    AuthenticationError,
    GeminiClient,
    ModelProvider,
    model_config_from_environment,
)
from agentic_tutorial.schemas import Message, MessageRole, RouteDecision


def test_public_provider_names_are_exactly_the_documented_choices() -> None:
    assert tuple(provider.value for provider in ModelProvider) == ("local", "gemini", "mock")


@pytest.mark.parametrize(
    ("provider", "internal_provider", "mode"),
    [
        ("mock", "deterministic-mock", "mock"),
        ("local", "local-llama-cpp", "local"),
        ("gemini", "gemini", "live"),
    ],
)
def test_model_provider_environment_selection(
    provider: str, internal_provider: str, mode: str
) -> None:
    config = model_config_from_environment(
        {"MODEL_PROVIDER": provider},
        mock_fixture_path="tests/fixtures/models/qualification/mock_v1.json",
    )

    assert config.provider == internal_provider
    assert config.execution_mode == mode
    assert "api_key" not in config.model_dump_json().casefold()


def test_invalid_public_provider_fails_before_construction() -> None:
    with pytest.raises(ValueError, match="MODEL_PROVIDER must be one of"):
        model_config_from_environment(
            {"MODEL_PROVIDER": "unknown"},
            mock_fixture_path="unused.json",
        )


def test_gemini_adapter_uses_header_credential_and_canonical_response() -> None:
    observed: dict[str, Any] = {}

    def transport(
        url: str,
        api_key: str,
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        observed.update(
            url=url,
            api_key=api_key,
            payload=payload,
            timeout_seconds=timeout_seconds,
        )
        return {
            "responseId": "gemini-test-1",
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": '{"route":"research","reason":"Evidence task"}'}]
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 4,
                "candidatesTokenCount": 3,
                "totalTokenCount": 7,
            },
        }

    client = GeminiClient(model="gemini-test", api_key="test-secret", transport=transport)
    response = asyncio.run(
        client.generate(
            [
                Message(role=MessageRole.SYSTEM, content="Return a valid route."),
                Message(role=MessageRole.USER, content="Route this evidence request."),
            ],
            response_schema=RouteDecision,
        )
    )

    assert response.provider == "gemini"
    assert response.structured_output is not None
    assert response.structured_output["route"] == "research"
    assert observed["api_key"] == "test-secret"
    assert "test-secret" not in str(observed["payload"])
    assert "test-secret" not in str(observed["url"])


def test_gemini_requires_environment_or_explicit_credential() -> None:
    with pytest.raises(AuthenticationError, match="GEMINI_API_KEY"):
        GeminiClient(model="gemini-test", api_key="")
