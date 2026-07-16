"""Controlled matched framework comparison tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evaluation.compare import ComparisonConfig, ComparisonResult, run_comparison


def test_comparison_configuration_requires_all_matched_implementations() -> None:
    with pytest.raises(ValidationError, match="requires each of the four"):
        ComparisonConfig(implementations=("plain-python", "langgraph"))
    with pytest.raises(ValidationError, match="repository-relative"):
        ComparisonConfig(output_root="/tmp/comparison")


def test_matched_comparison_preserves_metrics_raw_outputs_and_support(tmp_path: Path) -> None:
    output = Path("outputs") / f"test-comparison-{tmp_path.name}"
    configuration = ComparisonConfig(repetitions=2, output_root=output.as_posix())
    result = asyncio.run(run_comparison(configuration))

    assert len(result.runs) == 8
    assert {profile.implementation for profile in result.profiles} == {
        "plain-python",
        "langgraph",
        "crewai",
        "openai-agents",
    }
    assert all(profile.checkpoint_resume_verified for profile in result.profiles)
    assert all(aggregate.task_completion_rate == 1.0 for aggregate in result.aggregates)
    assert all(aggregate.final_answer_valid_rate == 1.0 for aggregate in result.aggregates)
    assert all(aggregate.mean_evidence_precision == 1.0 for aggregate in result.aggregates)
    assert all(aggregate.mean_evidence_recall == 1.0 for aggregate in result.aggregates)
    assert all(aggregate.mean_tool_selection_validity == 1.0 for aggregate in result.aggregates)
    assert all(aggregate.trajectory_valid_rate == 1.0 for aggregate in result.aggregates)
    assert all(aggregate.mean_model_calls == 4.0 for aggregate in result.aggregates)
    assert all(aggregate.mean_tool_calls == 3.0 for aggregate in result.aggregates)
    assert all(aggregate.mean_total_steps == 4.0 for aggregate in result.aggregates)
    assert (
        next(
            item for item in result.aggregates if item.implementation == "plain-python"
        ).mean_framework_specific_trace_events
        == 0.0
    )
    assert all(Path(run.trace_path).is_file() for run in result.runs)
    assert all(Path(run.state_path).is_file() for run in result.runs)
    assert (
        ComparisonResult.model_validate_json((output / "result.json").read_text(encoding="utf-8"))
        == result
    )
    assert (output / "summary.csv").is_file()


def test_deterministic_comparison_fields_repeat(tmp_path: Path) -> None:
    async def repeat() -> tuple[ComparisonResult, ComparisonResult]:
        first, second = await asyncio.gather(
            run_comparison(
                ComparisonConfig(repetitions=1, output_root="outputs/test-comparison-repeat-a")
            ),
            run_comparison(
                ComparisonConfig(repetitions=1, output_root="outputs/test-comparison-repeat-b")
            ),
        )
        return first, second

    first, second = asyncio.run(repeat())

    def deterministic_projection(result: ComparisonResult) -> str:
        projection = [
            {
                "implementation": run.implementation,
                "metrics": run.metrics.model_dump(
                    mode="json", exclude={"latency_seconds", "peak_memory_mb"}
                ),
                "steps": run.total_steps,
                "event_kinds": run.framework_event_kinds,
            }
            for run in result.runs
        ]
        return json.dumps(projection, sort_keys=True)

    assert deterministic_projection(first) == deterministic_projection(second)
