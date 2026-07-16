"""The narrow asynchronous interface consumed by tutorials."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from agentic_tutorial.models.config import GenerationSettings, ModelCapabilities
from agentic_tutorial.models.errors import UnsupportedCapabilityError
from agentic_tutorial.schemas import Message, ModelResponse, ToolDefinition


@runtime_checkable
class ModelClient(Protocol):
    """Structural interface implemented by offline and live model adapters."""

    @property
    def provider(self) -> str:
        """Stable provider identifier recorded in canonical responses."""
        ...

    @property
    def model(self) -> str:
        """Configured model or fixture identifier."""
        ...

    @property
    def capabilities(self) -> ModelCapabilities:
        """Common capabilities supported by this client."""
        ...

    async def generate(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolDefinition] = (),
        response_schema: type[BaseModel] | None = None,
        settings: GenerationSettings | None = None,
    ) -> ModelResponse:
        """Generate one canonical response."""
        ...


def validate_capabilities(
    client: ModelClient,
    *,
    tools: Sequence[ToolDefinition] = (),
    response_schema: type[BaseModel] | None = None,
    settings: GenerationSettings | None = None,
) -> None:
    """Fail explicitly when a request exceeds the client's common capabilities."""
    capabilities = client.capabilities
    if tools and not capabilities.native_tool_calling:
        raise UnsupportedCapabilityError(
            "native tool calling is not supported",
            provider=client.provider,
        )
    if response_schema is not None and not capabilities.structured_output:
        raise UnsupportedCapabilityError(
            "structured output is not supported",
            provider=client.provider,
        )
    if settings is not None and settings.stream and not capabilities.streaming:
        raise UnsupportedCapabilityError(
            "streaming is not supported",
            provider=client.provider,
        )
