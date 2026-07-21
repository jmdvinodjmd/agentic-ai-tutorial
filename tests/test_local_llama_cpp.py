"""Tests for the optional local provider without installing or running llama.cpp."""

from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, JsonValue, TypeAdapter

from agentic_tutorial.models import (
    InvalidModelResponseError,
    ModelClient,
    ModelConfig,
    ModelTimeoutError,
    ProviderRegistry,
    UnsupportedCapabilityError,
    create_model_client,
)
from agentic_tutorial.models.providers.local_llama_cpp import (
    FakeLlamaCppRuntime,
    LocalLlamaCppClient,
    LocalLlamaCppConfig,
    LocalModelMetadata,
    RuntimeCompletion,
    RuntimeToolCall,
    _parse_runtime_completion,
    register_local_llama_cpp_provider,
    run_fake_runtime_smoke,
)
from agentic_tutorial.schemas import Message, MessageRole, ModelResponse, ToolDefinition
from agentic_tutorial.tracing import build_run_manifest


class StructuredAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str


def _client(
    tmp_path: Path,
    runtime: FakeLlamaCppRuntime,
    *,
    structured_output: bool = True,
    tool_calling: bool = True,
    timeout_seconds: float = 1.0,
) -> LocalLlamaCppClient:
    content = b"fake-gguf"
    model_path = tmp_path / "fake.gguf"
    model_path.write_bytes(content)
    metadata = LocalModelMetadata(
        repository="test/fake",
        filename=model_path.name,
        quantisation="test",
        sha256=hashlib.sha256(content).hexdigest(),
        licence="Apache-2.0",
        source_revision="test",
    )
    return LocalLlamaCppClient(
        LocalLlamaCppConfig(
            model_path=model_path,
            model="fake-local",
            metadata=metadata,
            native_structured_output=structured_output,
            native_tool_calling=tool_calling,
            timeout_seconds=timeout_seconds,
        ),
        runtime,
    )


def test_fake_runtime_construction_generation_and_message_conversion(tmp_path: Path) -> None:
    runtime = FakeLlamaCppRuntime(
        [RuntimeCompletion(response_id="local-1", content="hello", input_tokens=2)]
    )
    client = _client(tmp_path, runtime)

    response = asyncio.run(
        client.generate(
            [
                Message(role=MessageRole.SYSTEM, content="system"),
                Message(role=MessageRole.USER, content="hello"),
            ]
        )
    )

    assert isinstance(client, ModelClient)
    assert isinstance(response, ModelResponse)
    assert response.provider == "local-llama-cpp"
    assert response.usage.input_tokens == 2
    assert runtime.requests[0].messages == (
        {"role": "system", "content": "system"},
        {"role": "user", "content": "hello"},
    )


def test_tool_and_response_schema_conversion(tmp_path: Path) -> None:
    runtime = FakeLlamaCppRuntime(
        [RuntimeCompletion(response_id="local-2", content='{"answer":"ready"}')]
    )
    client = _client(tmp_path, runtime)
    tool = ToolDefinition(
        name="lookup",
        description="Look up local data.",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}},
    )

    response = asyncio.run(
        client.generate(
            [Message(role=MessageRole.USER, content="answer")],
            tools=[tool],
            response_schema=StructuredAnswer,
        )
    )

    request = runtime.requests[0]
    function = TypeAdapter(dict[str, JsonValue]).validate_python(request.tools[0]["function"])
    assert function["name"] == "lookup"
    assert request.messages[0]["role"] == "system"
    assert "concise, complete JSON" in str(request.messages[0]["content"])
    assert request.response_format is not None
    assert response.structured_output == {"answer": "ready"}


def test_native_tool_call_becomes_canonical(tmp_path: Path) -> None:
    runtime = FakeLlamaCppRuntime(
        [
            RuntimeCompletion(
                response_id="local-tool",
                tool_calls=(
                    RuntimeToolCall(call_id="call-1", name="lookup", arguments={"query": "x"}),
                ),
            )
        ]
    )
    client = _client(tmp_path, runtime)

    response = asyncio.run(
        client.generate(
            [Message(role=MessageRole.USER, content="lookup")],
            tools=[ToolDefinition(name="lookup", description="Lookup", parameters={})],
        )
    )

    assert response.tool_calls[0].name == "lookup"
    assert response.model_dump(mode="json")["provider"] == "local-llama-cpp"
    assert "runtime" not in response.model_dump(mode="json")


def test_malformed_structured_output_is_canonical_error(tmp_path: Path) -> None:
    runtime = FakeLlamaCppRuntime([RuntimeCompletion(response_id="bad", content='{"wrong":true}')])
    client = _client(tmp_path, runtime)

    with pytest.raises(InvalidModelResponseError, match="requested schema"):
        asyncio.run(
            client.generate(
                [Message(role=MessageRole.USER, content="answer")],
                response_schema=StructuredAnswer,
            )
        )


@pytest.mark.parametrize(
    "content",
    [
        '<think>Check the requested fields.</think>\n{"answer":"ready"}',
        '```json\n{"answer":"ready"}\n```',
    ],
)
def test_structured_output_tolerates_local_model_wrappers(tmp_path: Path, content: str) -> None:
    client = _client(
        tmp_path,
        FakeLlamaCppRuntime([RuntimeCompletion(response_id="wrapped", content=content)]),
    )

    response = asyncio.run(
        client.generate(
            [Message(role=MessageRole.USER, content="answer")],
            response_schema=StructuredAnswer,
        )
    )

    assert response.structured_output == {"answer": "ready"}


def test_incomplete_structured_output_gets_one_bounded_retry(tmp_path: Path) -> None:
    runtime = FakeLlamaCppRuntime(
        [
            RuntimeCompletion(response_id="incomplete", content='{"answer":"'),
            RuntimeCompletion(response_id="repaired", content='{"answer":"ready"}'),
        ]
    )
    client = _client(tmp_path, runtime)

    response = asyncio.run(
        client.generate(
            [Message(role=MessageRole.USER, content="answer")],
            response_schema=StructuredAnswer,
        )
    )

    assert response.response_id == "repaired"
    assert response.structured_output == {"answer": "ready"}
    assert len(runtime.requests) == 2
    assert "previous response was incomplete" in str(runtime.requests[1].messages[-1]["content"])


def test_malformed_tool_arguments_are_canonical_error() -> None:
    with pytest.raises(InvalidModelResponseError, match="invalid completion payload"):
        _parse_runtime_completion(
            {
                "id": "bad-tool",
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "function": {"name": "lookup", "arguments": "{"},
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
            },
            latency_seconds=0.0,
            peak_memory_mb=None,
        )


def test_missing_model_and_bad_checksum_fail_before_runtime(tmp_path: Path) -> None:
    metadata = LocalModelMetadata(
        repository="test/fake",
        filename="missing.gguf",
        quantisation="test",
        sha256="0" * 64,
        licence="Apache-2.0",
        source_revision="test",
    )
    with pytest.raises(ValueError, match="does not exist"):
        LocalLlamaCppClient(
            LocalLlamaCppConfig(
                model_path=tmp_path / "missing.gguf", model="fake", metadata=metadata
            ),
            FakeLlamaCppRuntime([]),
        )

    path = tmp_path / "bad.gguf"
    path.write_bytes(b"bad")
    with pytest.raises(ValueError, match="checksum"):
        LocalLlamaCppClient(
            LocalLlamaCppConfig(model_path=path, model="fake", metadata=metadata),
            FakeLlamaCppRuntime([]),
        )


def test_unsupported_capabilities_fail_explicitly(tmp_path: Path) -> None:
    client = _client(
        tmp_path,
        FakeLlamaCppRuntime([]),
        structured_output=False,
        tool_calling=False,
    )

    with pytest.raises(UnsupportedCapabilityError, match="structured output"):
        asyncio.run(
            client.generate(
                [Message(role=MessageRole.USER, content="answer")],
                response_schema=StructuredAnswer,
            )
        )
    with pytest.raises(UnsupportedCapabilityError, match="tool calling"):
        asyncio.run(
            client.generate(
                [Message(role=MessageRole.USER, content="answer")],
                tools=[ToolDefinition(name="lookup", description="Lookup", parameters={})],
            )
        )


def test_timeout_and_runtime_failure_are_normalised(tmp_path: Path) -> None:
    timeout_client = _client(
        tmp_path,
        FakeLlamaCppRuntime(
            [RuntimeCompletion(response_id="late", content="late")], delay_seconds=0.02
        ),
        timeout_seconds=0.001,
    )
    with pytest.raises(ModelTimeoutError):
        asyncio.run(timeout_client.generate([Message(role=MessageRole.USER, content="answer")]))

    failure_client = _client(
        tmp_path,
        FakeLlamaCppRuntime([], error=RuntimeError("runtime failed")),
    )
    with pytest.raises(InvalidModelResponseError, match="runtime failed"):
        asyncio.run(failure_client.generate([Message(role=MessageRole.USER, content="answer")]))


def test_provider_registry_constructs_with_replaceable_runtime(tmp_path: Path) -> None:
    content = b"registry-model"
    model_path = tmp_path / "registry.gguf"
    model_path.write_bytes(content)
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        LocalModelMetadata(
            repository="test/fake",
            filename=model_path.name,
            quantisation="test",
            sha256=hashlib.sha256(content).hexdigest(),
            licence="Apache-2.0",
            source_revision="test",
        ).model_dump_json(),
        encoding="utf-8",
    )
    registry = ProviderRegistry()
    runtime = FakeLlamaCppRuntime([RuntimeCompletion(response_id="registry", content="ok")])
    register_local_llama_cpp_provider(registry, runtime_factory=lambda _config: runtime)

    client = create_model_client(
        ModelConfig.model_validate(
            {
                "provider": "local-llama-cpp",
                "model": "registry",
                "execution_mode": "local",
                "options": {
                    "model_path": str(model_path),
                    "metadata_path": str(metadata_path),
                },
            }
        ),
        registry=registry,
    )

    assert isinstance(client, LocalLlamaCppClient)
    assert registry.registered_providers() == ("local-llama-cpp",)


def test_manifest_metadata_and_fake_smoke(tmp_path: Path) -> None:
    client = _client(
        tmp_path,
        FakeLlamaCppRuntime([RuntimeCompletion(response_id="manifest", content="ok")]),
    )
    manifest = build_run_manifest(
        run_id="local-test",
        code_version="test",
        provider=client.provider,
        model=client.model,
        configuration={},
        model_metadata=client.manifest_metadata,
    )

    assert manifest.model_metadata is not None
    assert manifest.model_metadata["runtime"] == "fake-llama-cpp"
    assert run_fake_runtime_smoke() == {
        "mode": "fake-runtime",
        "provider": "local-llama-cpp",
        "status": "ok",
    }


@pytest.mark.slow
def test_optional_real_model_generation() -> None:
    model_path = os.getenv("AGENTIC_TUTORIAL_LOCAL_MODEL_PATH")
    if not model_path or not Path(model_path).is_file():
        pytest.skip("verified local GGUF model is unavailable")
    pytest.importorskip("llama_cpp")
    client = create_model_client(
        ModelConfig.model_validate(
            {
                "provider": "local-llama-cpp",
                "model": Path(model_path).stem,
                "execution_mode": "local",
                "settings": {"max_output_tokens": 16, "temperature": 0.0, "seed": 0},
                "options": {"model_path": model_path},
            }
        )
    )
    response = asyncio.run(
        client.generate([Message(role=MessageRole.USER, content="Reply with: ready")])
    )
    assert response.message is not None
