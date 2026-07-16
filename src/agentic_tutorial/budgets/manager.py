"""Single shared authority for execution limits and consumption."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic

from agentic_tutorial.schemas import (
    Action,
    Budget,
    ModelResponse,
    TerminationReason,
    ToolResult,
    ToolResultStatus,
    Usage,
)


@dataclass(frozen=True)
class BudgetSnapshot:
    """A deterministic view of configured, consumed and remaining limits."""

    budget: Budget
    consumed: Usage
    remaining_model_calls: int
    remaining_steps: int
    remaining_tool_calls: int
    remaining_tokens: int | None
    remaining_seconds: float
    remaining_failures: int
    remaining_cost_usd: float | None


class BudgetManager:
    """Track usage and detect limits, repeated actions and short cycles."""

    def __init__(
        self,
        budget: Budget,
        *,
        initial_usage: Usage | None = None,
        initial_actions: tuple[Action, ...] = (),
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.budget = budget
        self._usage = initial_usage or Usage()
        self._clock = clock
        self._started = clock() - self._usage.elapsed_seconds
        self._actions = [_action_key(action) for action in initial_actions]

    @property
    def usage(self) -> Usage:
        return self._usage.model_copy(update={"elapsed_seconds": self.elapsed_seconds})

    @property
    def elapsed_seconds(self) -> float:
        return max(self._usage.elapsed_seconds, self._clock() - self._started)

    def check(self, *, steps: int) -> TerminationReason | None:
        """Return the first exhausted limit in deterministic priority order."""
        usage = self.usage
        if steps >= self.budget.max_steps:
            return TerminationReason.MAX_STEPS
        if usage.model_calls >= self.budget.max_model_calls:
            return TerminationReason.MAX_MODEL_CALLS
        if usage.tool_calls >= self.budget.max_tool_calls:
            return TerminationReason.MAX_TOOL_CALLS
        if usage.total_tokens is not None and usage.total_tokens >= self.budget.max_tokens:
            return TerminationReason.MAX_TOKENS
        if usage.elapsed_seconds >= self.budget.max_elapsed_seconds:
            return TerminationReason.MAX_ELAPSED_TIME
        if usage.failures >= self.budget.max_failures:
            return TerminationReason.MAX_FAILURES
        if (
            self.budget.max_cost_usd is not None
            and usage.monetary_cost_usd is not None
            and usage.monetary_cost_usd >= self.budget.max_cost_usd
        ):
            return TerminationReason.MAX_COST
        return None

    def record_model_response(self, response: ModelResponse) -> None:
        """Account for one completed model call and any reported usage."""
        first = self._usage.model_calls == 0
        reported = response.usage
        self._usage = self._usage.model_copy(
            update={
                "input_tokens": _sum_optional(
                    self._usage.input_tokens, reported.input_tokens, first
                ),
                "output_tokens": _sum_optional(
                    self._usage.output_tokens, reported.output_tokens, first
                ),
                "total_tokens": _sum_optional(
                    self._usage.total_tokens, reported.total_tokens, first
                ),
                "model_calls": self._usage.model_calls + 1,
                "monetary_cost_usd": _sum_optional(
                    self._usage.monetary_cost_usd, reported.monetary_cost_usd, first
                ),
                "elapsed_seconds": self.elapsed_seconds,
            }
        )

    def record_model_failure(self) -> None:
        self._usage = self._usage.model_copy(
            update={
                "model_calls": self._usage.model_calls + 1,
                "failures": self._usage.failures + 1,
                "elapsed_seconds": self.elapsed_seconds,
            }
        )

    def check_post_action(self) -> TerminationReason | None:
        """Check limits that may be crossed by a completed model or tool action."""
        usage = self.usage
        if usage.total_tokens is not None and usage.total_tokens >= self.budget.max_tokens:
            return TerminationReason.MAX_TOKENS
        if usage.elapsed_seconds >= self.budget.max_elapsed_seconds:
            return TerminationReason.MAX_ELAPSED_TIME
        if usage.failures >= self.budget.max_failures:
            return TerminationReason.MAX_FAILURES
        if (
            self.budget.max_cost_usd is not None
            and usage.monetary_cost_usd is not None
            and usage.monetary_cost_usd >= self.budget.max_cost_usd
        ):
            return TerminationReason.MAX_COST
        return None

    def check_before_tool(self) -> TerminationReason | None:
        """Prevent a tool call once its dedicated allowance is exhausted."""
        if self._usage.tool_calls >= self.budget.max_tool_calls:
            return TerminationReason.MAX_TOOL_CALLS
        return self.check_post_action()

    def record_tool_result(self, result: ToolResult) -> None:
        self._usage = self._usage.model_copy(
            update={
                "tool_calls": self._usage.tool_calls + 1,
                "failures": self._usage.failures
                + int(result.status is not ToolResultStatus.SUCCESS),
                "elapsed_seconds": self.elapsed_seconds,
            }
        )

    def observe_action(self, action: Action) -> TerminationReason | None:
        self._actions.append(_action_key(action))
        limit = self.budget.max_repeated_actions
        if len(self._actions) >= limit and len(set(self._actions[-limit:])) == 1:
            return TerminationReason.REPEATED_ACTION
        if len(self._actions) >= 4 and self._actions[-4:-2] == self._actions[-2:]:
            return TerminationReason.REPEATED_ACTION
        return None

    def snapshot(self, *, steps: int) -> BudgetSnapshot:
        usage = self.usage
        return BudgetSnapshot(
            budget=self.budget,
            consumed=usage,
            remaining_model_calls=max(0, self.budget.max_model_calls - usage.model_calls),
            remaining_steps=max(0, self.budget.max_steps - steps),
            remaining_tool_calls=max(0, self.budget.max_tool_calls - usage.tool_calls),
            remaining_tokens=(
                None
                if usage.total_tokens is None
                else max(0, self.budget.max_tokens - usage.total_tokens)
            ),
            remaining_seconds=max(0.0, self.budget.max_elapsed_seconds - usage.elapsed_seconds),
            remaining_failures=max(0, self.budget.max_failures - usage.failures),
            remaining_cost_usd=(
                None
                if self.budget.max_cost_usd is None or usage.monetary_cost_usd is None
                else max(0.0, self.budget.max_cost_usd - usage.monetary_cost_usd)
            ),
        )

    def nested(self, budget: Budget, *, steps: int) -> BudgetManager:
        """Create a stricter child manager bounded by remaining parent resources."""
        remaining = self.snapshot(steps=steps)
        if (
            budget.max_model_calls > remaining.remaining_model_calls
            or budget.max_steps > remaining.remaining_steps
            or budget.max_tool_calls > remaining.remaining_tool_calls
            or budget.max_failures > remaining.remaining_failures
        ):
            raise ValueError("nested budget exceeds remaining parent limits")
        return BudgetManager(budget, clock=self._clock)


def _sum_optional(
    left: int | float | None, right: int | float | None, first: bool
) -> int | float | None:
    if first:
        return right
    if left is None or right is None:
        return None
    return left + right


def _action_key(action: Action) -> str:
    return json.dumps(action.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
