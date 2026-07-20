"""Thin Gemini REST adapter behind the shared model interface.

The adapter is optional and never runs in CI. It uses only the API key supplied
at construction or read from ``GEMINI_API_KEY``; credentials are never placed in
model configuration, prompts, responses, or traces.
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from typing import Any, cast

from pydantic import BaseModel, JsonValue, TypeAdapter, ValidationError

from agentic_tutorial.models.config import GenerationSettings, ModelCapabilities, ModelConfig
from agentic_tutorial.models.errors import (
    AuthenticationError,
    InvalidModelResponseError,
    ModelProviderError,
    ModelTimeoutError,
    RateLimitError,
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

PROVIDER_ID = "gemini"
DEFAULT_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta"
GeminiTransport = Callable[[str, str, dict[str, JsonValue], float], dict[str, Any]]


class GeminiClient:
    """Canonical client over Gemini's ``generateContent`` REST method."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout_seconds: float = 60.0,
        transport: GeminiTransport | None = None,
    ) -> None:
        if not api_key:
            raise AuthenticationError(
                "GEMINI_API_KEY is required for MODEL_PROVIDER=gemini",
                provider=PROVIDER_ID,
            )
        self._model = model
        self._api_key = api_key
        self._endpoint = endpoint.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._transport = transport or _urllib_transport

    @property
    def provider(self) -> str:
        return PROVIDER_ID

    @property
    def model(self) -> str:
        return self._model

    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            structured_output=True,
            native_tool_calling=True,
            streaming=False,
            usage_reporting=True,
        )

    async def generate(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolDefinition] = (),
        response_schema: type[BaseModel] | None = None,
        settings: GenerationSettings | None = None,
    ) -> ModelResponse:
        effective = settings or GenerationSettings()
        validate_capabilities(
            self,
            tools=tools,
            response_schema=response_schema,
            settings=effective,
        )
        payload = _request_payload(messages, tools, response_schema, effective)
        url = f"{self._endpoint}/models/{self.model}:generateContent"
        try:
            raw = await asyncio.to_thread(
                self._transport,
                url,
                self._api_key,
                payload,
                self._timeout_seconds,
            )
        except ModelProviderError:
            raise
        except TimeoutError as error:
            raise ModelTimeoutError(
                "Gemini request timed out", provider=self.provider, cause=error
            ) from error
        except Exception as error:
            raise InvalidModelResponseError(
                "Gemini request failed", provider=self.provider, cause=error
            ) from error
        return _canonical_response(raw, self.model, response_schema)


def register_gemini_provider(
    registry: ProviderRegistry,
    *,
    transport: GeminiTransport | None = None,
    environment: dict[str, str] | None = None,
) -> None:
    """Register Gemini without making a request or importing an SDK."""

    source = environment if environment is not None else os.environ

    def create(config: ModelConfig) -> GeminiClient:
        if config.provider != PROVIDER_ID or config.execution_mode != "live":
            raise ValueError("gemini requires provider='gemini' and execution_mode='live'")
        return GeminiClient(
            model=config.model,
            api_key=source.get("GEMINI_API_KEY", ""),
            endpoint=_string_option(config, "endpoint", DEFAULT_ENDPOINT),
            timeout_seconds=_float_option(config, "timeout_seconds", 60.0),
            transport=transport,
        )

    registry.register(PROVIDER_ID, create)


def _request_payload(
    messages: Sequence[Message],
    tools: Sequence[ToolDefinition],
    response_schema: type[BaseModel] | None,
    settings: GenerationSettings,
) -> dict[str, JsonValue]:
    systems = [message.content for message in messages if message.role is MessageRole.SYSTEM]
    contents: list[dict[str, JsonValue]] = []
    for message in messages:
        if message.role is MessageRole.SYSTEM:
            continue
        role = "model" if message.role is MessageRole.ASSISTANT else "user"
        contents.append({"role": role, "parts": [{"text": message.content}]})
    generation: dict[str, JsonValue] = {
        "temperature": settings.temperature,
        "maxOutputTokens": settings.max_output_tokens,
    }
    if response_schema is not None:
        generation.update(
            {
                "responseMimeType": "application/json",
                "responseJsonSchema": TypeAdapter(dict[str, JsonValue]).validate_python(
                    response_schema.model_json_schema()
                ),
            }
        )
    payload: dict[str, object] = {"contents": contents, "generationConfig": generation}
    if systems:
        payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(systems)}]}
    if tools:
        payload["tools"] = [
            {
                "functionDeclarations": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    }
                    for tool in tools
                ]
            }
        ]
    return TypeAdapter(dict[str, JsonValue]).validate_python(payload)


def _canonical_response(
    raw: dict[str, Any],
    model: str,
    response_schema: type[BaseModel] | None,
) -> ModelResponse:
    try:
        candidate = raw["candidates"][0]
        parts = candidate["content"]["parts"]
        text = next((part["text"] for part in parts if "text" in part), None)
        calls = tuple(
            ToolCall(
                call_id=str(part.get("functionCall", {}).get("id", f"gemini-call-{index}")),
                name=str(part["functionCall"]["name"]),
                arguments=TypeAdapter(dict[str, JsonValue]).validate_python(
                    part["functionCall"].get("args", {})
                ),
            )
            for index, part in enumerate(parts, start=1)
            if "functionCall" in part
        )
        structured = None
        if response_schema is not None:
            if text is None:
                raise ValueError("structured response did not contain JSON text")
            structured = response_schema.model_validate_json(text).model_dump(mode="json")
        usage = raw.get("usageMetadata", {})
        message = Message(role=MessageRole.ASSISTANT, content=text) if text is not None else None
        return ModelResponse(
            response_id=str(raw.get("responseId", "gemini-response")),
            provider=PROVIDER_ID,
            model=model,
            message=message,
            tool_calls=calls,
            structured_output=structured,
            usage=Usage(
                input_tokens=_optional_int(usage.get("promptTokenCount")),
                output_tokens=_optional_int(usage.get("candidatesTokenCount")),
                total_tokens=_optional_int(usage.get("totalTokenCount")),
                model_calls=1,
            ),
            finish_reason=FinishReason.TOOL_CALLS if calls else _finish_reason(candidate),
        )
    except (KeyError, IndexError, TypeError, ValueError, ValidationError) as error:
        raise InvalidModelResponseError(
            "Gemini returned an invalid response", provider=PROVIDER_ID, cause=error
        ) from error


def _urllib_transport(
    url: str,
    api_key: str,
    payload: dict[str, JsonValue],
    timeout_seconds: float,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            loaded = json.loads(response.read().decode("utf-8"))
            if not isinstance(loaded, dict):
                raise InvalidModelResponseError(
                    "Gemini returned a non-object response", provider=PROVIDER_ID
                )
            return cast(dict[str, Any], loaded)
    except urllib.error.HTTPError as error:
        if error.code in {401, 403}:
            raise AuthenticationError(
                "Gemini rejected the configured credential", provider=PROVIDER_ID, cause=error
            ) from error
        if error.code == 429:
            raise RateLimitError(
                "Gemini rate limit exceeded", provider=PROVIDER_ID, cause=error
            ) from error
        raise InvalidModelResponseError(
            f"Gemini HTTP request failed with status {error.code}",
            provider=PROVIDER_ID,
            cause=error,
        ) from error


def _finish_reason(candidate: dict[str, Any]) -> FinishReason:
    return {
        "STOP": FinishReason.STOP,
        "MAX_TOKENS": FinishReason.LENGTH,
        "SAFETY": FinishReason.CONTENT_FILTER,
        "RECITATION": FinishReason.CONTENT_FILTER,
    }.get(str(candidate.get("finishReason", "STOP")), FinishReason.ERROR)


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _string_option(config: ModelConfig, name: str, default: str) -> str:
    value = config.options.get(name, default)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Gemini option {name!r} must be a non-empty string")
    return value


def _float_option(config: ModelConfig, name: str, default: float) -> float:
    value = config.options.get(name, default)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"Gemini option {name!r} must be numeric")
    return float(value)
