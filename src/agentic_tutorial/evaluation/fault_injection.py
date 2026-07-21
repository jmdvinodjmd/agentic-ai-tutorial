"""Explicit model-boundary faults for recovery evaluation."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel

from agentic_tutorial.models import (
    GenerationSettings,
    InvalidModelResponseError,
    ModelCapabilities,
    ModelClient,
)
from agentic_tutorial.schemas import Message, ModelResponse, ToolDefinition


class MalformedResponseFaultClient:
    """Inject one malformed structured response before delegating normally.

    Live providers should not be prompted to behave incorrectly merely to test
    recovery. This wrapper introduces the fault deterministically at the model
    boundary, allowing the following request to measure the model's recovery
    decision.
    """

    def __init__(self, client: ModelClient, *, on_schema: type[BaseModel]) -> None:
        self._client = client
        self._on_schema = on_schema
        self._injected = False

    @property
    def provider(self) -> str:
        return self._client.provider

    @property
    def model(self) -> str:
        return self._client.model

    @property
    def capabilities(self) -> ModelCapabilities:
        return self._client.capabilities

    async def generate(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolDefinition] = (),
        response_schema: type[BaseModel] | None = None,
        settings: GenerationSettings | None = None,
    ) -> ModelResponse:
        if not self._injected and response_schema is self._on_schema:
            self._injected = True
            raise InvalidModelResponseError(
                "injected malformed structured response",
                provider=self.provider,
            )
        return await self._client.generate(
            messages,
            tools=tools,
            response_schema=response_schema,
            settings=settings,
        )
