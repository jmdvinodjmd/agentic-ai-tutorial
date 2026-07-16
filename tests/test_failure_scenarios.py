"""Integration tests for every versioned controlled failure scenario."""

from __future__ import annotations

import asyncio
from pathlib import Path

from agentic_tutorial.failures import ExpectedBehaviour, ScenarioRunner, load_failure_scenarios
from agentic_tutorial.schemas import ErrorClass, TerminationReason
from agentic_tutorial.tracing import TraceEventType, TraceReader


def test_every_declared_scenario_reaches_its_expected_boundary(tmp_path: Path) -> None:
    fixture = load_failure_scenarios()
    results = asyncio.run(ScenarioRunner(tmp_path).run_all())
    assert len(results) == len(fixture.scenarios) == 14
    assert all(result.passed for result in results)
    assert all(result.error is not None or result.termination is not None for result in results)
    for result in results:
        events = TraceReader(tmp_path / result.scenario_id / "summary_trace.jsonl").read()
        assert events[-1].event_type is TraceEventType.TERMINATION


def test_circuit_breakers_stop_repetition_and_short_cycles(tmp_path: Path) -> None:
    runner = ScenarioRunner(tmp_path)
    fixture = {item.scenario_id: item for item in runner.fixture.scenarios}
    repeated = asyncio.run(runner.run(fixture["repeated-action"]))
    cycle = asyncio.run(runner.run(fixture["short-execution-cycle"]))
    assert repeated.termination is not None
    assert repeated.termination.reason is TerminationReason.REPEATED_ACTION
    assert cycle.termination is not None
    assert cycle.termination.reason is TerminationReason.REPEATED_ACTION


def test_injection_is_denied_and_conflict_escalates(tmp_path: Path) -> None:
    runner = ScenarioRunner(tmp_path)
    fixture = {item.scenario_id: item for item in runner.fixture.scenarios}
    injection = asyncio.run(runner.run(fixture["prompt-injection"]))
    conflict = asyncio.run(runner.run(fixture["contradictory-evidence"]))
    assert injection.observed_behaviour is ExpectedBehaviour.DENIAL
    assert injection.details["executed"] is False
    assert conflict.observed_behaviour is ExpectedBehaviour.ESCALATION
    assert conflict.error is not None
    assert conflict.error.error_class is ErrorClass.HUMAN_ESCALATION
