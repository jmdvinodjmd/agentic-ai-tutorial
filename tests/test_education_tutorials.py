"""Focused tests for progressive component examples."""

import asyncio

from agentic_tutorial.education import (
    PATTERN_NAMES,
    TUTORIAL_NAMES,
    run_pattern_async,
    run_tutorial,
    run_tutorial_async,
)


def test_every_progressive_example_is_deterministic() -> None:
    for name in TUTORIAL_NAMES:
        assert run_tutorial(name) == run_tutorial(name)


def test_progression_exposes_one_named_concept_each() -> None:
    concepts = [run_tutorial(name)["concept"] for name in TUTORIAL_NAMES]
    assert len(concepts) == len(set(concepts)) == 7


def test_validation_example_demonstrates_correction() -> None:
    result = run_tutorial("critique-validation")
    assert result["valid_initially"] is False
    assert "paper-001" in str(result["revised"])


def test_async_entry_point_runs_inside_an_event_loop() -> None:
    async def run() -> list[str]:
        return [str((await run_tutorial_async(name))["concept"]) for name in TUTORIAL_NAMES]

    assert len(asyncio.run(run())) == len(TUTORIAL_NAMES)


def test_patterns_run_inside_an_event_loop() -> None:
    async def run() -> list[str]:
        return [str((await run_pattern_async(name))["pattern"]) for name in PATTERN_NAMES]

    assert len(asyncio.run(run())) == len(PATTERN_NAMES)
