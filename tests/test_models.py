"""Provider selection and thin-adapter contract tests."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from agentic_tutorial.models import (
    AuthenticationError,
    GeminiClient,
    LocalLlamaCppClient,
    ModelProvider,
    create_model,
    model_config_from_environment,
)
from agentic_tutorial.schemas import Message, MessageRole, RouteDecision


def test_public_provider_names_are_exactly_the_documented_choices() -> None:
    assert tuple(provider.value for provider in ModelProvider) == ("mock", "local", "api")


@pytest.mark.parametrize(
    ("provider", "internal_provider", "mode"),
    [
        ("mock", "deterministic-mock", "mock"),
        ("local", "local-llama-cpp", "local"),
        ("api", "gemini", "live"),
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


def test_create_model_constructs_mock_local_and_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock = create_model(
        provider="mock",
        mock_fixture_path="tests/fixtures/models/qualification/mock_v1.json",
        model="qualification-mock-v1",
    )
    assert mock.provider == "deterministic-mock"

    model_bytes = b"provider-construction-test"
    model_path = tmp_path / "Qwen3-0.6B-Q8_0.gguf"
    model_path.write_bytes(model_bytes)
    metadata_path = tmp_path / "model_metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "metadata_version": "1",
                "repository": "test/Qwen3-0.6B-GGUF",
                "filename": model_path.name,
                "quantisation": "Q8_0",
                "sha256": hashlib.sha256(model_bytes).hexdigest(),
                "licence": "Apache-2.0",
                "source_revision": "test",
            }
        ),
        encoding="utf-8",
    )
    from agentic_tutorial.models.providers.local_llama_cpp import (
        FakeLlamaCppRuntime,
        register_local_llama_cpp_provider,
    )
    from agentic_tutorial.models.registry import ProviderRegistry

    local_registry = ProviderRegistry()
    register_local_llama_cpp_provider(
        local_registry,
        runtime_factory=lambda _config: FakeLlamaCppRuntime([]),
    )
    local = create_model(
        provider="local",
        model="Qwen3-0.6B-Q8_0",
        model_path=model_path,
        metadata_path=metadata_path,
        registry=local_registry,
    )
    assert isinstance(local, LocalLlamaCppClient)

    monkeypatch.setenv("GEMINI_API_KEY", "construction-test-key")
    api = create_model(provider="api", model="gemini-3.1-flash-lite")
    assert isinstance(api, GeminiClient)
