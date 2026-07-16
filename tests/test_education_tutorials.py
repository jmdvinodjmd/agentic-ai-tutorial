"""Focused tests for progressive component examples."""

from agentic_tutorial.education import TUTORIAL_NAMES, run_tutorial


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
