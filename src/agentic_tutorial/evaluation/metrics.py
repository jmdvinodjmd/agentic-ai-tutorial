"""Deterministic metrics derived from canonical state, traces and annotations."""

from __future__ import annotations

import json
from collections.abc import Sequence

from pydantic import ValidationError

from agentic_tutorial.case_study import CaseStudyDefinition, TaskVariant, load_catalogue
from agentic_tutorial.evaluation.models import AggregateMetrics, EvaluationMetrics
from agentic_tutorial.schemas import AgentState, FinalAnswer, TerminationStatus, ToolAction
from agentic_tutorial.tracing import TraceEvent, TraceEventType


def evaluate_run(
    state: AgentState,
    events: Sequence[TraceEvent],
    variant: TaskVariant,
    definition: CaseStudyDefinition,
) -> EvaluationMetrics:
    """Score one run without an LLM judge or implementation-specific objects."""
    final_valid = _final_answer_valid(state)
    evidence_ids = (
        [item.source_id for item in state.final_answer.evidence] if state.final_answer else []
    )
    expected = set(variant.annotation.expected_source_ids)
    provided = set(evidence_ids)
    known = {entry.source_id for entry in load_catalogue() if entry.valid}
    precision = (
        len(provided & expected) / len(provided) if provided else (1.0 if not expected else 0.0)
    )
    recall = len(provided & expected) / len(expected) if expected else 1.0
    unsupported = len(provided - known)
    claim_count = max(1, len(evidence_ids))
    tool_actions = [step.action for step in state.steps if isinstance(step.action, ToolAction)]
    allowed = set(definition.safety.allowed_tools)
    valid_tools = sum(action.tool_call.name in allowed for action in tool_actions)
    logical_keys = [
        json.dumps(
            {"name": action.tool_call.name, "arguments": action.tool_call.arguments},
            sort_keys=True,
            separators=(",", ":"),
        )
        for action in tool_actions
    ]
    repeated = len(logical_keys) - len(set(logical_keys))
    expected_tools = _expected_tools(variant)
    unnecessary = sum(action.tool_call.name not in expected_tools for action in tool_actions)
    human_interventions = sum(event.event_type is TraceEventType.HUMAN_DECISION for event in events)
    failures = state.usage.failures
    recovered = None if failures == 0 else _task_completed(state, variant)
    structured_responses = [
        step.model_response.structured_output is not None for step in state.steps
    ]
    return EvaluationMetrics(
        task_completed=_task_completed(state, variant),
        final_answer_schema_valid=final_valid,
        evidence_precision=precision,
        evidence_recall=recall,
        provenance_valid=len(evidence_ids) == len(provided) and not (provided - known),
        unsupported_claim_rate=unsupported / claim_count,
        tool_selection_valid_rate=(valid_tools / len(tool_actions) if tool_actions else 1.0),
        routing_correct=all(action.tool_call.name in expected_tools for action in tool_actions),
        trajectory_valid=_trajectory_valid(state, events),
        unnecessary_actions=unnecessary,
        repeated_actions=repeated,
        recovered_from_failure=recovered,
        budget_adhered=_budget_adhered(state),
        human_interventions=human_interventions,
        model_calls=state.usage.model_calls,
        tool_calls=state.usage.tool_calls,
        input_tokens=state.usage.input_tokens,
        output_tokens=state.usage.output_tokens,
        total_tokens=state.usage.total_tokens,
        latency_seconds=state.usage.elapsed_seconds,
        cost_usd=state.usage.monetary_cost_usd,
        peak_memory_mb=None,
        structured_output_valid_rate=(
            sum(structured_responses) / len(structured_responses) if structured_responses else None
        ),
    )


def aggregate_metrics(metrics: Sequence[EvaluationMetrics]) -> AggregateMetrics:
    """Aggregate repeated runs while retaining unavailable measurements as ``None``."""
    if not metrics:
        raise ValueError("at least one evaluation is required")
    recovery = [
        item.recovered_from_failure for item in metrics if item.recovered_from_failure is not None
    ]
    return AggregateMetrics(
        run_count=len(metrics),
        task_completion_rate=_mean([item.task_completed for item in metrics]),
        final_answer_valid_rate=_mean([item.final_answer_schema_valid for item in metrics]),
        mean_evidence_precision=_mean([item.evidence_precision for item in metrics]),
        mean_evidence_recall=_mean([item.evidence_recall for item in metrics]),
        mean_unsupported_claim_rate=_mean([item.unsupported_claim_rate for item in metrics]),
        mean_tool_selection_valid_rate=_mean([item.tool_selection_valid_rate for item in metrics]),
        trajectory_valid_rate=_mean([item.trajectory_valid for item in metrics]),
        recovery_rate=_mean(recovery) if recovery else None,
        mean_model_calls=_mean([item.model_calls for item in metrics]),
        mean_tool_calls=_mean([item.tool_calls for item in metrics]),
        mean_total_tokens=_optional_mean([item.total_tokens for item in metrics]),
        mean_latency_seconds=_optional_mean([item.latency_seconds for item in metrics]),
        mean_cost_usd=_optional_mean([item.cost_usd for item in metrics]),
        mean_peak_memory_mb=_optional_mean([item.peak_memory_mb for item in metrics]),
    )


def _task_completed(state: AgentState, variant: TaskVariant) -> bool:
    if state.termination is None:
        return False
    if variant.annotation.expected_outcome.value == "clarification":
        return state.termination.status is TerminationStatus.INTERRUPTED
    return state.termination.status is TerminationStatus.SUCCESS


def _final_answer_valid(state: AgentState) -> bool:
    if state.final_answer is None:
        return (
            state.termination is not None
            and state.termination.status is TerminationStatus.INTERRUPTED
        )
    try:
        FinalAnswer.model_validate(state.final_answer.model_dump(mode="json"))
    except ValidationError:
        return False
    return True


def _expected_tools(variant: TaskVariant) -> set[str]:
    if variant.annotation.expected_outcome.value == "clarification":
        return set()
    if variant.annotation.expected_outcome.value == "insufficient_evidence":
        return {"search_catalogue", "critique_draft"}
    return {"search_catalogue", "extract_evidence", "critique_draft"}


def _trajectory_valid(state: AgentState, events: Sequence[TraceEvent]) -> bool:
    if not events or state.termination is None:
        return False
    sequences = [event.sequence for event in events]
    return sequences == list(range(1, len(events) + 1)) and any(
        event.event_type is TraceEventType.TERMINATION for event in events
    )


def _budget_adhered(state: AgentState) -> bool:
    usage = state.usage
    budget = state.budget
    return (
        len(state.steps) <= budget.max_steps
        and usage.model_calls <= budget.max_model_calls
        and usage.tool_calls <= budget.max_tool_calls
        and (usage.total_tokens is None or usage.total_tokens <= budget.max_tokens)
        and usage.elapsed_seconds <= budget.max_elapsed_seconds
        and usage.failures <= budget.max_failures
        and (
            budget.max_cost_usd is None
            or usage.monetary_cost_usd is None
            or usage.monetary_cost_usd <= budget.max_cost_usd
        )
    )


def _mean(values: Sequence[int | float | bool]) -> float:
    return sum(float(value) for value in values) / len(values)


def _optional_mean(values: Sequence[int | float | None]) -> float | None:
    available = [float(value) for value in values if value is not None]
    return sum(available) / len(available) if available else None
