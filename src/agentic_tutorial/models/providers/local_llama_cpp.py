"""Optional local llama.cpp adapter isolated behind the canonical model interface."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import os
import platform
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from time import monotonic
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from agentic_tutorial.models.config import GenerationSettings, ModelCapabilities, ModelConfig
from agentic_tutorial.models.errors import (
    InvalidModelResponseError,
    ModelProviderError,
    ModelTimeoutError,
)
from agentic_tutorial.models.interface import validate_capabilities
from agentic_tutorial.models.registry import ProviderRegistry
from agentic_tutorial.schemas import (
    FinishReason,
    Message,
    MessageRole,
    ModelResponse,
    ToolCall,
    ToolDefinition,
    Usage,
)

PROVIDER_ID = "local-llama-cpp"
DEFAULT_METADATA_PATH = Path("models/local/model_metadata.json")


class LocalProviderModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LocalModelMetadata(LocalProviderModel):
    metadata_version: str = Field(default="1", min_length=1)
    repository: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    quantisation: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    licence: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)


class LocalLlamaCppConfig(LocalProviderModel):
    model_path: Path
    model: str = Field(min_length=1)
    context_size: int = Field(default=4096, gt=0)
    max_output_tokens: int = Field(default=512, gt=0)
    thread_count: int = Field(default=max(1, os.cpu_count() or 1), gt=0)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    seed: int = 0
    timeout_seconds: float = Field(default=120.0, gt=0)
    chat_format: str | None = None
    native_structured_output: bool = True
    native_tool_calling: bool = True
    metadata: LocalModelMetadata
    verify_checksum: bool = True


class RuntimeToolCall(LocalProviderModel):
    call_id: str
    name: str
    arguments: dict[str, JsonValue]


class RuntimeRequest(LocalProviderModel):
    messages: tuple[dict[str, JsonValue], ...]
    tools: tuple[dict[str, JsonValue], ...]
    response_format: dict[str, JsonValue] | None = None
    max_output_tokens: int
    temperature: float
    seed: int


class RuntimeCompletion(LocalProviderModel):
    response_id: str
    content: str | None = None
    tool_calls: tuple[RuntimeToolCall, ...] = ()
    finish_reason: str = "stop"
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    latency_seconds: float | None = Field(default=None, ge=0)
    peak_memory_mb: float | None = Field(default=None, ge=0)


@runtime_checkable
class LlamaCppRuntime(Protocol):
    """Replaceable boundary implemented by the optional runtime and test fake."""

    @property
    def runtime_name(self) -> str: ...

    @property
    def runtime_version(self) -> str: ...

    async def generate(self, request: RuntimeRequest) -> RuntimeCompletion: ...


class FakeLlamaCppRuntime:
    """Finite deterministic runtime used by core tests without llama.cpp."""

    def __init__(
        self,
        completions: Sequence[RuntimeCompletion],
        *,
        error: BaseException | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self.completions = tuple(completions)
        self.error = error
        self.delay_seconds = delay_seconds
        self.requests: list[RuntimeRequest] = []

    @property
    def runtime_name(self) -> str:
        return "fake-llama-cpp"

    @property
    def runtime_version(self) -> str:
        return "1"

    async def generate(self, request: RuntimeRequest) -> RuntimeCompletion:
        self.requests.append(request)
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        if self.error is not None:
            raise self.error
        if not self.completions:
            raise RuntimeError("fake runtime is exhausted")
        return self.completions[len(self.requests) - 1]


class LlamaCppPythonRuntime:
    """Lazy optional integration; llama.cpp objects never cross this module."""

    def __init__(self, config: LocalLlamaCppConfig) -> None:
        try:
            module = importlib.import_module("llama_cpp")
        except ImportError as error:
            raise ModelProviderError(
                "optional llama-cpp-python dependency is not installed",
                provider=PROVIDER_ID,
                cause=error,
            ) from error
        self._module: Any = module
        self._llm: Any = module.Llama(
            model_path=str(config.model_path),
            n_ctx=config.context_size,
            n_threads=config.thread_count,
            seed=config.seed,
            n_gpu_layers=0,
            chat_format=config.chat_format,
            verbose=False,
        )

    @property
    def runtime_name(self) -> str:
        return "llama-cpp-python"

    @property
    def runtime_version(self) -> str:
        value = getattr(self._module, "__version__", "unknown")
        return str(value)

    async def generate(self, request: RuntimeRequest) -> RuntimeCompletion:
        return await asyncio.to_thread(self._generate_sync, request)

    def _generate_sync(self, request: RuntimeRequest) -> RuntimeCompletion:
        started = monotonic()
        kwargs: dict[str, object] = {
            "messages": list(request.messages),
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
            "seed": request.seed,
        }
        if request.tools:
            kwargs["tools"] = list(request.tools)
        if request.response_format is not None:
            kwargs["response_format"] = request.response_format
        raw: Any = self._llm.create_chat_completion(**kwargs)
        return _parse_runtime_completion(
            raw,
            latency_seconds=monotonic() - started,
            peak_memory_mb=_peak_memory_mb(),
        )


class LocalLlamaCppClient:
    """Canonical client over a replaceable local llama.cpp-compatible runtime."""

    def __init__(self, config: LocalLlamaCppConfig, runtime: LlamaCppRuntime) -> None:
        _validate_model_file(config)
        self.config = config
        self.runtime = runtime
        self.last_completion: RuntimeCompletion | None = None

    @property
    def provider(self) -> str:
        return PROVIDER_ID

    @property
    def model(self) -> str:
        return self.config.model

    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            structured_output=self.config.native_structured_output,
            native_tool_calling=self.config.native_tool_calling,
            streaming=False,
            usage_reporting=True,
        )

    @property
    def manifest_metadata(self) -> dict[str, JsonValue]:
        return {
            **self.config.metadata.model_dump(mode="json"),
            "provider": self.provider,
            "runtime": self.runtime.runtime_name,
            "runtime_version": self.runtime.runtime_version,
            "context_size": self.config.context_size,
            "max_output_tokens": self.config.max_output_tokens,
            "thread_count": self.config.thread_count,
            "temperature": self.config.temperature,
            "seed": self.config.seed,
            "model_path_filename": self.config.model_path.name,
        }

    async def generate(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolDefinition] = (),
        response_schema: type[BaseModel] | None = None,
        settings: GenerationSettings | None = None,
    ) -> ModelResponse:
        effective = settings or GenerationSettings(
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_output_tokens,
            seed=self.config.seed,
        )
        validate_capabilities(
            self,
            tools=tools,
            response_schema=response_schema,
            settings=effective,
        )
        request = RuntimeRequest(
            messages=_request_messages(messages, response_schema),
            tools=tuple(_tool_payload(tool) for tool in tools),
            response_format=_response_format(response_schema),
            max_output_tokens=effective.max_output_tokens,
            temperature=effective.temperature,
            seed=effective.seed if effective.seed is not None else self.config.seed,
        )
        completion = await self._complete(request)
        self.last_completion = completion
        try:
            return _canonical_response(completion, self, response_schema)
        except InvalidModelResponseError as first_error:
            if response_schema is None:
                raise

            retry_request = request.model_copy(
                update={
                    "messages": (
                        *request.messages,
                        {
                            "role": "user",
                            "content": (
                                "The previous response was incomplete or invalid. Return a "
                                "shorter, complete JSON object only."
                            ),
                        },
                    )
                }
            )
            try:
                completion = await self._complete(retry_request)
                self.last_completion = completion
                return _canonical_response(completion, self, response_schema)
            except (InvalidModelResponseError, ModelTimeoutError):
                raise first_error from first_error.cause

    async def _complete(self, request: RuntimeRequest) -> RuntimeCompletion:
        try:
            return await asyncio.wait_for(
                self.runtime.generate(request), timeout=self.config.timeout_seconds
            )
        except TimeoutError as error:
            raise ModelTimeoutError(
                "local llama.cpp generation timed out", provider=self.provider, cause=error
            ) from error
        except ModelProviderError:
            raise
        except Exception as error:
            raise InvalidModelResponseError(
                "local llama.cpp runtime failed", provider=self.provider, cause=error
            ) from error


RuntimeFactory = Callable[[LocalLlamaCppConfig], LlamaCppRuntime]


def register_local_llama_cpp_provider(
    registry: ProviderRegistry,
    *,
    runtime_factory: RuntimeFactory | None = None,
) -> None:
    """Register local construction without importing the optional runtime package."""
    factory = runtime_factory or LlamaCppPythonRuntime

    def create(config: ModelConfig) -> LocalLlamaCppClient:
        local_config = local_config_from_model_config(config)
        _validate_model_file(local_config)
        return LocalLlamaCppClient(local_config, factory(local_config))

    registry.register(PROVIDER_ID, create)


def local_config_from_model_config(config: ModelConfig) -> LocalLlamaCppConfig:
    if config.provider != PROVIDER_ID or config.execution_mode != "local":
        raise ValueError("local-llama-cpp requires provider and local execution mode")
    metadata_path = Path(_string_option(config, "metadata_path", str(DEFAULT_METADATA_PATH)))
    metadata = load_model_metadata(metadata_path)
    model_path_value = config.options.get("model_path") or os.getenv(
        "AGENTIC_TUTORIAL_LOCAL_MODEL_PATH"
    )
    if not isinstance(model_path_value, str) or not model_path_value:
        raise ValueError(
            "local model path must be configured through model_path or "
            "AGENTIC_TUTORIAL_LOCAL_MODEL_PATH"
        )
    return LocalLlamaCppConfig(
        model_path=Path(model_path_value),
        model=config.model,
        context_size=_int_option(config, "context_size", 4096),
        max_output_tokens=config.settings.max_output_tokens,
        thread_count=_int_option(config, "thread_count", max(1, os.cpu_count() or 1)),
        temperature=config.settings.temperature,
        seed=config.settings.seed or 0,
        timeout_seconds=_float_option(config, "timeout_seconds", 120.0),
        chat_format=_optional_string(config, "chat_format"),
        native_structured_output=_bool_option(config, "structured_output", True),
        native_tool_calling=_bool_option(config, "tool_calling", True),
        metadata=metadata,
        verify_checksum=_bool_option(config, "verify_checksum", True),
    )


def load_model_metadata(path: str | Path = DEFAULT_METADATA_PATH) -> LocalModelMetadata:
    return LocalModelMetadata.model_validate_json(Path(path).read_text(encoding="utf-8"))


def verify_model_checksum(path: str | Path, expected_sha256: str) -> None:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected_sha256:
        raise ValueError("local model checksum does not match recorded metadata")


def run_fake_runtime_smoke() -> dict[str, str]:
    """Exercise the complete adapter boundary without an installed runtime."""
    model_bytes = b"deterministic-local-model-placeholder"
    checksum = hashlib.sha256(model_bytes).hexdigest()
    metadata = LocalModelMetadata(
        repository="local/fake",
        filename="fake.gguf",
        quantisation="test",
        sha256=checksum,
        licence="Apache-2.0",
        source_revision="test",
    )
    runtime = FakeLlamaCppRuntime(
        [RuntimeCompletion(response_id="fake-smoke", content="offline local smoke")]
    )
    with tempfile.TemporaryDirectory() as directory:
        model_path = Path(directory) / metadata.filename
        model_path.write_bytes(model_bytes)
        client = LocalLlamaCppClient(
            LocalLlamaCppConfig(
                model_path=model_path,
                model="fake-local-model",
                metadata=metadata,
            ),
            runtime,
        )
        response = asyncio.run(client.generate([Message(role=MessageRole.USER, content="smoke")]))
    return {"mode": "fake-runtime", "provider": response.provider, "status": "ok"}


def _validate_model_file(config: LocalLlamaCppConfig) -> None:
    if not config.model_path.is_file():
        raise ValueError(f"local model file does not exist: {config.model_path}")
    if config.verify_checksum:
        verify_model_checksum(config.model_path, config.metadata.sha256)


def _message_payload(message: Message) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {"role": message.role.value, "content": message.content}
    if message.name is not None:
        payload["name"] = message.name
    if message.tool_call_id is not None:
        payload["tool_call_id"] = message.tool_call_id
    return payload


def _request_messages(
    messages: Sequence[Message], response_schema: type[BaseModel] | None
) -> tuple[dict[str, JsonValue], ...]:
    payload = tuple(_message_payload(message) for message in messages)
    if response_schema is None:
        return payload
    schema = json.dumps(response_schema.model_json_schema(), separators=(",", ":"))
    instruction: dict[str, JsonValue] = {
        "role": "system",
        "content": (
            "Return only one concise, complete JSON object matching this JSON Schema. "
            "Do not include analysis, think tags, Markdown fences or commentary. "
            f"Schema: {schema}"
        ),
    }
    return (instruction, *payload)


def _tool_payload(tool: ToolDefinition) -> dict[str, JsonValue]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _response_format(schema: type[BaseModel] | None) -> dict[str, JsonValue] | None:
    if schema is None:
        return None
    return {"type": "json_object", "schema": schema.model_json_schema()}


def _canonical_response(
    completion: RuntimeCompletion,
    client: LocalLlamaCppClient,
    response_schema: type[BaseModel] | None,
) -> ModelResponse:
    calls = tuple(
        ToolCall(call_id=call.call_id, name=call.name, arguments=call.arguments)
        for call in completion.tool_calls
    )
    structured: dict[str, JsonValue] | None = None
    if response_schema is not None:
        if completion.content:
            validation_error: ValueError | ValidationError | None = None
            for candidate in _json_object_candidates(completion.content):
                try:
                    validated = response_schema.model_validate(candidate)
                except (ValueError, ValidationError) as error:
                    validation_error = error
                    continue
                structured = validated.model_dump(mode="json")
                break
            if structured is None:
                raise InvalidModelResponseError(
                    "local structured output does not satisfy the requested schema",
                    provider=client.provider,
                    cause=validation_error,
                ) from validation_error
        elif calls:
            candidate = {
                "action": {
                    "action_type": "tool",
                    "tool_call": calls[0].model_dump(mode="json"),
                }
            }
            try:
                structured = response_schema.model_validate(candidate).model_dump(mode="json")
            except ValidationError as error:
                raise InvalidModelResponseError(
                    "local tool call does not satisfy the requested response schema",
                    provider=client.provider,
                    cause=error,
                ) from error
        else:
            raise InvalidModelResponseError(
                "local runtime returned no structured content", provider=client.provider
            )
    message = (
        Message(role=MessageRole.ASSISTANT, content=completion.content)
        if completion.content is not None
        else None
    )
    return ModelResponse(
        response_id=completion.response_id,
        provider=client.provider,
        model=client.model,
        message=message,
        tool_calls=calls,
        structured_output=structured,
        usage=Usage(
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            total_tokens=completion.total_tokens,
        ),
        finish_reason=_finish_reason(completion.finish_reason, bool(calls)),
    )


def _json_object_candidates(content: str) -> tuple[dict[str, Any], ...]:
    """Extract JSON objects even when a local chat model adds prose or think tags."""
    decoder = json.JSONDecoder()
    candidates: list[dict[str, Any]] = []
    stripped = content.strip()
    try:
        loaded = json.loads(stripped)
    except json.JSONDecodeError:
        loaded = None
    if isinstance(loaded, dict):
        candidates.append(loaded)

    for index, character in enumerate(content):
        if character != "{":
            continue
        try:
            loaded, _end = decoder.raw_decode(content[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict) and loaded not in candidates:
            candidates.append(loaded)
    return tuple(candidates)


def _finish_reason(value: str, has_calls: bool) -> FinishReason:
    if has_calls:
        return FinishReason.TOOL_CALLS
    return {
        "stop": FinishReason.STOP,
        "length": FinishReason.LENGTH,
        "content_filter": FinishReason.CONTENT_FILTER,
    }.get(value, FinishReason.ERROR)


def _parse_runtime_completion(
    raw: Any, *, latency_seconds: float, peak_memory_mb: float | None
) -> RuntimeCompletion:
    try:
        choice = raw["choices"][0]
        message = choice["message"]
        usage = raw.get("usage", {})
        calls = tuple(_parse_tool_call(item) for item in message.get("tool_calls", ()))
        return RuntimeCompletion(
            response_id=str(raw.get("id", "local-response")),
            content=message.get("content"),
            tool_calls=calls,
            finish_reason=str(choice.get("finish_reason", "stop")),
            input_tokens=_optional_int(usage.get("prompt_tokens")),
            output_tokens=_optional_int(usage.get("completion_tokens")),
            total_tokens=_optional_int(usage.get("total_tokens")),
            latency_seconds=latency_seconds,
            peak_memory_mb=peak_memory_mb,
        )
    except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as error:
        raise InvalidModelResponseError(
            "llama.cpp returned an invalid completion payload",
            provider=PROVIDER_ID,
            cause=error,
        ) from error


def _parse_tool_call(raw: Any) -> RuntimeToolCall:
    function = raw["function"]
    arguments = function.get("arguments", {})
    if isinstance(arguments, str):
        arguments = json.loads(arguments)
    return RuntimeToolCall(
        call_id=str(raw.get("id", "local-tool-call")),
        name=str(function["name"]),
        arguments=arguments,
    )


def _peak_memory_mb() -> float | None:
    try:
        resource_module: Any = importlib.import_module("resource")
        value = float(resource_module.getrusage(resource_module.RUSAGE_SELF).ru_maxrss)
    except (ImportError, AttributeError, ValueError):
        return None
    return value / (1024 * 1024) if platform.system() == "Darwin" else value / 1024


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _string_option(config: ModelConfig, name: str, default: str) -> str:
    value = config.options.get(name, default)
    if not isinstance(value, str) or not value:
        raise ValueError(f"local model option {name!r} must be a non-empty string")
    return value


def _optional_string(config: ModelConfig, name: str) -> str | None:
    value = config.options.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"local model option {name!r} must be a non-empty string")
    return value


def _int_option(config: ModelConfig, name: str, default: int) -> int:
    value = config.options.get(name, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"local model option {name!r} must be an integer")
    return value


def _float_option(config: ModelConfig, name: str, default: float) -> float:
    value = config.options.get(name, default)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"local model option {name!r} must be numeric")
    return float(value)


def _bool_option(config: ModelConfig, name: str, default: bool) -> bool:
    value = config.options.get(name, default)
    if not isinstance(value, bool):
        raise ValueError(f"local model option {name!r} must be boolean")
    return value
