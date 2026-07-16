"""Tests for T05 shared tool registration and safe execution."""

from __future__ import annotations

import asyncio
import time

from agentic_tutorial.schemas import ToolCall, ToolResultStatus, ToolSideEffect
from agentic_tutorial.tools import (
    ApprovalToken,
    ToolExecutor,
    ToolRegistry,
    build_tutorial_registry,
)


def test_registry_derives_canonical_schema_and_rejects_duplicates() -> None:
    registry = ToolRegistry()

    @registry.tool(description="Repeat text.")
    def repeat(text: str, count: int = 1) -> str:
        return text * count

    definition = registry.definitions()[0]
    assert definition.name == "repeat"
    assert definition.parameters["required"] == ["text"]
    try:
        registry.register(repeat)
    except ValueError as error:
        assert "already registered" in str(error)
    else:
        raise AssertionError("duplicate registration was accepted")


def test_valid_sync_and_async_tools_execute() -> None:
    registry = ToolRegistry()

    @registry.tool()
    def add(left: int, right: int) -> int:
        """Add integers."""
        return left + right

    @registry.tool()
    async def upper(text: str) -> str:
        """Upper-case text."""
        return text.upper()

    executor = ToolExecutor(registry)
    sync_result = asyncio.run(
        executor.execute(ToolCall(call_id="1", name="add", arguments={"left": 2, "right": 3}))
    )
    async_result = asyncio.run(
        executor.execute(ToolCall(call_id="2", name="upper", arguments={"text": "ok"}))
    )
    assert sync_result.content == 5
    assert async_result.content == "OK"


def test_unknown_invalid_and_unauthorised_tools_never_execute() -> None:
    calls = 0
    registry = ToolRegistry()

    @registry.tool()
    def counted(value: int) -> int:
        """Count valid executions."""
        nonlocal calls
        calls += 1
        return value

    executor = ToolExecutor(registry)
    unknown = asyncio.run(executor.execute(ToolCall(call_id="1", name="missing")))
    invalid = asyncio.run(
        executor.execute(ToolCall(call_id="2", name="counted", arguments={"value": "bad"}))
    )
    denied = asyncio.run(
        executor.execute(
            ToolCall(call_id="3", name="counted", arguments={"value": 1}), allowed_tools=set()
        )
    )
    assert unknown.error is not None
    assert invalid.error is not None
    assert denied.error is not None
    assert [unknown.error.code, invalid.error.code, denied.error.code] == [
        "unknown_tool",
        "invalid_tool_arguments",
        "unauthorised_tool",
    ]
    assert calls == 0


def test_exceptions_and_timeouts_become_canonical_results() -> None:
    registry = ToolRegistry()

    @registry.tool()
    def broken() -> str:
        """Fail safely."""
        raise RuntimeError("secret implementation detail")

    @registry.tool()
    def slow() -> str:
        """Exceed the test timeout."""
        time.sleep(0.05)
        return "late"

    executor = ToolExecutor(registry, timeout_seconds=0.005)
    broken_result = asyncio.run(executor.execute(ToolCall(call_id="1", name="broken")))
    timeout_result = asyncio.run(executor.execute(ToolCall(call_id="2", name="slow")))
    assert broken_result.error is not None and broken_result.error.code == "tool_exception"
    assert timeout_result.status is ToolResultStatus.TIMEOUT


def test_side_effect_requires_matching_approval() -> None:
    registry = ToolRegistry()

    @registry.tool(side_effect=ToolSideEffect.SIDE_EFFECTING)
    def consequential(value: str) -> str:
        """Simulate a consequential action."""
        return value

    call = ToolCall(call_id="call-1", name="consequential", arguments={"value": "approved"})
    executor = ToolExecutor(registry)
    denied = asyncio.run(executor.execute(call))
    approved = asyncio.run(
        executor.execute(call, approval=ApprovalToken(tool_name=call.name, call_id=call.call_id))
    )
    assert denied.status is ToolResultStatus.DENIED
    assert approved.content == "approved"


def test_builtin_catalogue_is_deterministic() -> None:
    executor = ToolExecutor(build_tutorial_registry())
    call = ToolCall(call_id="1", name="catalogue_search", arguments={"query": "agent evaluation"})
    first = asyncio.run(executor.execute(call))
    second = asyncio.run(executor.execute(call))
    assert first.content == second.content
