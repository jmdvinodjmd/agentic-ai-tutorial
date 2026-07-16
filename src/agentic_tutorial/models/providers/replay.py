"""Strict replay of recorded canonical request-response pairs."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from agentic_tutorial.models.config import GenerationSettings, ModelCapabilities
from agentic_tutorial.models.errors import InvalidModelResponseError
from agentic_tutorial.models.interface import validate_capabilities
from agentic_tutorial.models.providers.fixtures import (
    CanonicalRequest,
    ReplayFixture,
    ReplayHeader,
    ReplayRecord,
)
from agentic_tutorial.models.providers.validation import (
    response_schema_identity,
    validate_offline_response,
)
from agentic_tutorial.schemas import Message, ModelResponse, ToolDefinition


class ReplayMismatchError(InvalidModelResponseError):
    """The current canonical request diverges from the recorded request."""

    error_code = "replay_mismatch"


class ReplayClient:
    """Replay canonical responses only when current requests remain compatible."""

    def __init__(self, fixture: ReplayFixture) -> None:
        first_response = fixture.records[0].response
        self._fixture = fixture
        self._provider = first_response.provider
        self._model = first_response.model
        self._next_record = 0
        if any(
            record.response.provider != self._provider or record.response.model != self._model
            for record in fixture.records
        ):
            raise InvalidModelResponseError(
                "all replay responses must use one provider and model identity",
                provider=self._provider,
            )

    @classmethod
    def from_jsonl(cls, path: str | Path) -> ReplayClient:
        """Read a versioned JSONL replay fixture with a mandatory provenance header."""
        fixture_path = Path(path)
        try:
            lines = [line for line in fixture_path.read_text(encoding="utf-8").splitlines() if line]
            if len(lines) < 2:
                raise ValueError("replay fixtures require a header and at least one response")
            header_payload: Any = json.loads(lines[0])
            header = ReplayHeader.model_validate(header_payload)
            records = tuple(ReplayRecord.model_validate_json(line) for line in lines[1:])
            fixture = ReplayFixture(header=header, records=records)
        except (OSError, ValueError, json.JSONDecodeError, ValidationError) as error:
            raise InvalidModelResponseError(
                f"invalid replay fixture: {fixture_path}",
                provider="replay",
                cause=error,
            ) from error
        return cls(fixture)

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    @property
    def scenario(self) -> str:
        """Recorded replay scenario."""
        return self._fixture.header.scenario

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
        """Return the matching recorded response or explain request divergence."""
        validate_capabilities(
            self,
            tools=tools,
            response_schema=response_schema,
            settings=settings,
        )
        if self._next_record >= len(self._fixture.records):
            raise ReplayMismatchError(
                f"replay scenario {self.scenario!r} is exhausted",
                provider=self.provider,
            )

        expected = self._fixture.records[self._next_record]
        current = CanonicalRequest(
            messages=tuple(messages),
            tools=tuple(tools),
            response_schema=response_schema_identity(response_schema),
            settings=settings or GenerationSettings(),
        )
        differences = _request_differences(expected.request, current)
        if differences:
            summary = ", ".join(differences)
            raise ReplayMismatchError(
                f"replay mismatch at step {expected.step}: {summary} differ",
                provider=self.provider,
            )

        response = expected.response
        validate_offline_response(
            response,
            provider=self.provider,
            model=self.model,
            tools=tools,
            response_schema=response_schema,
        )
        self._next_record += 1
        return response.model_copy(deep=True)


def _request_differences(expected: CanonicalRequest, current: CanonicalRequest) -> list[str]:
    fields = ("messages", "tools", "response_schema", "settings")
    return [field for field in fields if getattr(expected, field) != getattr(current, field)]
