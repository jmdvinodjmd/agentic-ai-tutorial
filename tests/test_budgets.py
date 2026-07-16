"""Tests for shared budgets and circuit breakers."""

from __future__ import annotations

from agentic_tutorial.budgets import BudgetManager
from agentic_tutorial.schemas import (
    AgentError,
    Budget,
    ErrorClass,
    FinishAction,
    TerminationReason,
    ToolResult,
    ToolResultStatus,
    Usage,
)
from tests.test_agent_loop import _finish


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


def test_iteration_and_model_call_limits() -> None:
    manager = BudgetManager(Budget(max_steps=1, max_model_calls=1))
    assert manager.check(steps=1) is TerminationReason.MAX_STEPS
    manager.record_model_response(_finish())
    assert manager.check(steps=0) is TerminationReason.MAX_MODEL_CALLS


def test_token_and_time_limits() -> None:
    clock = FakeClock()
    manager = BudgetManager(Budget(max_tokens=6, max_elapsed_seconds=2), clock=clock)
    manager.record_model_response(_finish())
    assert manager.check(steps=0) is TerminationReason.MAX_TOKENS
    assert manager.check_post_action() is TerminationReason.MAX_TOKENS
    manager = BudgetManager(Budget(max_tokens=100, max_elapsed_seconds=2), clock=clock)
    clock.value = 2.0
    assert manager.check(steps=0) is TerminationReason.MAX_ELAPSED_TIME


def test_repeated_action_and_short_cycle_detection() -> None:
    repeated = BudgetManager(Budget(max_repeated_actions=2))
    finish = FinishAction(answer="same")
    assert repeated.observe_action(finish) is None
    assert repeated.observe_action(finish) is TerminationReason.REPEATED_ACTION

    cycle = BudgetManager(Budget(max_repeated_actions=3))
    first = FinishAction(answer="first")
    second = FinishAction(answer="second")
    for action in (first, second, first):
        assert cycle.observe_action(action) is None
    assert cycle.observe_action(second) is TerminationReason.REPEATED_ACTION


def test_tool_failures_trigger_circuit_breaker() -> None:
    manager = BudgetManager(Budget(max_failures=1))
    result = ToolResult(
        call_id="1",
        name="search",
        status=ToolResultStatus.ERROR,
        error=AgentError(
            error_class=ErrorClass.RECOVERABLE,
            code="failed",
            message="simulated failure",
        ),
    )
    manager.record_tool_result(result)
    assert manager.check(steps=0) is TerminationReason.MAX_FAILURES
    assert manager.check_post_action() is TerminationReason.MAX_FAILURES


def test_tool_precheck_blocks_exhausted_allowance() -> None:
    manager = BudgetManager(Budget(max_tool_calls=1))
    result = ToolResult(call_id="1", name="search", status=ToolResultStatus.SUCCESS)
    manager.record_tool_result(result)
    assert manager.check_before_tool() is TerminationReason.MAX_TOOL_CALLS


def test_nested_budget_cannot_exceed_parent_remaining() -> None:
    parent = BudgetManager(Budget(max_model_calls=3, max_steps=3, max_tool_calls=3, max_failures=3))
    parent.record_model_response(_finish())
    child = parent.nested(
        Budget(max_model_calls=2, max_steps=2, max_tool_calls=2, max_failures=2), steps=1
    )
    assert child.budget.max_steps == 2
    try:
        parent.nested(Budget(max_model_calls=3), steps=1)
    except ValueError as error:
        assert "exceeds" in str(error)
    else:
        raise AssertionError("invalid nested budget was accepted")


def test_unknown_tokens_and_cost_do_not_disable_other_limits() -> None:
    manager = BudgetManager(
        Budget(max_model_calls=1, max_cost_usd=1.0),
        initial_usage=Usage(model_calls=1, monetary_cost_usd=None, total_tokens=None),
    )
    assert manager.check(steps=0) is TerminationReason.MAX_MODEL_CALLS


def test_snapshot_preserves_resumed_consumption() -> None:
    initial = Usage(
        input_tokens=4,
        output_tokens=2,
        total_tokens=6,
        model_calls=1,
        tool_calls=1,
        elapsed_seconds=1.0,
    )
    manager = BudgetManager(Budget(max_model_calls=3, max_steps=3), initial_usage=initial)
    snapshot = manager.snapshot(steps=1)
    assert snapshot.remaining_model_calls == 2
    assert snapshot.remaining_steps == 2
