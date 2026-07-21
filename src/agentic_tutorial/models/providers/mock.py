"""Deterministic scripted model client for default offline execution."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ValidationError

from agentic_tutorial.models.config import GenerationSettings, ModelCapabilities
from agentic_tutorial.models.errors import InvalidModelResponseError
from agentic_tutorial.models.interface import validate_capabilities
from agentic_tutorial.models.providers.fixtures import ScriptedScenarioFixture
from agentic_tutorial.models.providers.validation import validate_offline_response
from agentic_tutorial.schemas import Message, ModelResponse, ToolDefinition


class DeterministicMockClient:
    """Return a finite sequence of canonical responses without network access."""

    def __init__(self, fixture: ScriptedScenarioFixture) -> None:
        first_response = fixture.responses[0]
        self._fixture = fixture
        self._provider = first_response.provider
        self._model = first_response.model
        self._next_step = 0
        if any(
            response.provider != self._provider or response.model != self._model
            for response in fixture.responses
        ):
            raise InvalidModelResponseError(
                "all scripted responses must use one provider and model identity",
                provider=self._provider,
            )

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        scenario: str | None = None,
    ) -> DeterministicMockClient:
        """Load and validate a versioned scenario fixture."""
        fixture_path = Path(path)
        try:
            fixture = ScriptedScenarioFixture.model_validate_json(
                fixture_path.read_text(encoding="utf-8")
            )
        except (OSError, ValidationError) as error:
            raise InvalidModelResponseError(
                f"invalid deterministic mock fixture: {fixture_path}",
                provider="deterministic-mock",
                cause=error,
            ) from error
        if scenario is not None and scenario != fixture.scenario:
            raise InvalidModelResponseError(
                "mock fixture scenario mismatch: "
                f"expected {scenario!r}, found {fixture.scenario!r}",
                provider="deterministic-mock",
            )
        return cls(fixture)

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    @property
    def scenario(self) -> str:
        """Fixture scenario selected for this finite client instance."""
        return self._fixture.scenario

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
        """Return the next response, failing when the finite script is exhausted."""
        del messages
        validate_capabilities(
            self,
            tools=tools,
            response_schema=response_schema,
            settings=settings,
        )
        if self._next_step >= len(self._fixture.responses):
            raise InvalidModelResponseError(
                f"deterministic mock scenario {self.scenario!r} is exhausted",
                provider=self.provider,
            )
        response = self._fixture.responses[self._next_step]
        # A malformed response is still an observed model attempt. Consume it
        # before validation so bounded retry logic can request the next result.
        self._next_step += 1
        validate_offline_response(
            response,
            provider=self.provider,
            model=self.model,
            tools=tools,
            response_schema=response_schema,
        )
        return response.model_copy(deep=True)
