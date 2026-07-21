"""Shared validation for deterministic offline responses."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ValidationError

from agentic_tutorial.models.errors import InvalidModelResponseError
from agentic_tutorial.schemas import ModelResponse, ToolDefinition


def validate_offline_response(
    response: ModelResponse,
    *,
    provider: str,
    model: str,
    tools: Sequence[ToolDefinition],
    response_schema: type[BaseModel] | None,
) -> None:
    """Ensure a fixture response remains compatible with the current request."""
    if response.provider != provider or response.model != model:
        raise InvalidModelResponseError(
            "fixture response provider or model does not match the configured client",
            provider=provider,
        )

    allowed_tools = {tool.name for tool in tools}
    unexpected_tools = sorted(
        call.name for call in response.tool_calls if call.name not in allowed_tools
    )
    if unexpected_tools:
        names = ", ".join(unexpected_tools)
        raise InvalidModelResponseError(
            f"fixture response requested tools not present in the request: {names}",
            provider=provider,
        )

    if response_schema is None:
        return
    if response.structured_output is None:
        raise InvalidModelResponseError(
            "fixture response has no structured output for the requested schema",
            provider=provider,
        )
    try:
        response_schema.model_validate(response.structured_output)
    except ValidationError as error:
        raise InvalidModelResponseError(
            "fixture structured output does not satisfy the requested schema",
            provider=provider,
            cause=error,
        ) from error


def response_schema_identity(response_schema: type[BaseModel] | None) -> str | None:
    """Return the explicit stable identifier used in reproducibility records."""
    if response_schema is None:
        return None
    schema_id = getattr(response_schema, "schema_id", None)
    if not isinstance(schema_id, str) or not schema_id:
        raise InvalidModelResponseError(
            "response schema must define a stable non-empty schema_id",
            provider="shared",
        )
    return schema_id
