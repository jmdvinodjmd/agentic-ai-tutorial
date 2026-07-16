"""Validated, permission-aware execution of registered tools."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Collection
from time import monotonic

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, ValidationError

from agentic_tutorial.schemas import (
    AgentError,
    ErrorClass,
    ToolCall,
    ToolResult,
    ToolResultStatus,
    ToolSideEffect,
)
from agentic_tutorial.tools.registry import RegisteredTool, ToolRegistry


class ApprovalToken(BaseModel):
    """Explicit authority for one consequential tool call."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    tool_name: str = Field(min_length=1)
    call_id: str = Field(min_length=1)


class ToolExecutor:
    """Execute only registered, allowed and validated tool calls."""

    def __init__(self, registry: ToolRegistry, *, timeout_seconds: float = 10.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.registry = registry
        self.timeout_seconds = timeout_seconds

    async def execute(
        self,
        call: ToolCall,
        *,
        allowed_tools: Collection[str] | None = None,
        approval: ApprovalToken | None = None,
    ) -> ToolResult:
        """Return a canonical result for success and every expected failure."""
        started = monotonic()
        registered = self.registry.get(call.name)
        if registered is None:
            return self._failure(call, "unknown_tool", "tool is not registered", started)
        if allowed_tools is not None and call.name not in allowed_tools:
            return self._failure(
                call,
                "unauthorised_tool",
                "tool is not in the execution allowlist",
                started,
                status=ToolResultStatus.DENIED,
            )
        if registered.definition.side_effect is ToolSideEffect.SIDE_EFFECTING and (
            approval is None or approval.tool_name != call.name or approval.call_id != call.call_id
        ):
            return self._failure(
                call,
                "approval_required",
                "side-effecting tool requires a matching approval token",
                started,
                status=ToolResultStatus.DENIED,
            )
        try:
            arguments = registered.arguments_model.model_validate(call.arguments)
        except ValidationError as error:
            return self._failure(
                call,
                "invalid_tool_arguments",
                _validation_message(error),
                started,
            )
        try:
            value = await asyncio.wait_for(
                _invoke(registered, arguments), timeout=self.timeout_seconds
            )
            content: JsonValue = TypeAdapter(JsonValue).validate_python(value)
            return ToolResult(
                call_id=call.call_id,
                name=call.name,
                status=ToolResultStatus.SUCCESS,
                content=content,
                elapsed_ms=_elapsed_ms(started),
            )
        except TimeoutError:
            return self._failure(
                call,
                "tool_timeout",
                "tool execution exceeded its timeout",
                started,
                status=ToolResultStatus.TIMEOUT,
                error_class=ErrorClass.RETRYABLE,
            )
        except Exception:
            return self._failure(
                call,
                "tool_exception",
                "tool execution failed",
                started,
                error_class=ErrorClass.RECOVERABLE,
            )

    @staticmethod
    def _failure(
        call: ToolCall,
        code: str,
        message: str,
        started: float,
        *,
        status: ToolResultStatus = ToolResultStatus.ERROR,
        error_class: ErrorClass = ErrorClass.TERMINAL,
    ) -> ToolResult:
        return ToolResult(
            call_id=call.call_id,
            name=call.name,
            status=status,
            elapsed_ms=_elapsed_ms(started),
            error=AgentError(error_class=error_class, code=code, message=message, source=call.name),
        )


async def _invoke(registered: RegisteredTool, arguments: BaseModel) -> object:
    kwargs = arguments.model_dump()
    if inspect.iscoroutinefunction(registered.handler):
        return await registered.handler(**kwargs)
    return await asyncio.to_thread(registered.handler, **kwargs)


def _elapsed_ms(started: float) -> int:
    return max(0, round((monotonic() - started) * 1_000))


def _validation_message(error: ValidationError) -> str:
    locations = [".".join(str(part) for part in item["loc"]) for item in error.errors()]
    return "invalid arguments: " + ", ".join(locations)
