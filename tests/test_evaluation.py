"""Tests for deterministic common evaluation and repeated experiments."""

from __future__ import annotations

import asyncio
from pathlib import Path

from agentic_tutorial.case_study import CaseStudyVariant, case_study_hash, load_definition
from agentic_tutorial.case_study.plain_python import PlainPythonCaseStudy
from agentic_tutorial.evaluation import ExperimentConfig, ExperimentRunner, evaluate_run
from agentic_tutorial.evaluation.metrics import aggregate_metrics
from agentic_tutorial.evaluation.models import EvaluationMetrics, ExperimentResult
from agentic_tutorial.schemas import AgentState
from agentic_tutorial.tracing import TraceReader


def test_known_success_metrics_are_grounded_in_annotations(tmp_path: Path) -> None:
    baseline = PlainPythonCaseStudy(output_root=tmp_path / "runs")
    state = asyncio.run(baseline.run(CaseStudyVariant.STANDARD, run_id="known"))
    metrics = evaluate_run(
        state,
        TraceReader(tmp_path / "runs" / "known" / "trace.jsonl").read(),
        load_definition().variant(CaseStudyVariant.STANDARD),
        load_definition(),
    )
    assert metrics.task_completed and metrics.final_answer_schema_valid
    assert metrics.evidence_precision == metrics.evidence_recall == 1.0
    assert metrics.unsupported_claim_rate == 0.0
    assert metrics.routing_correct and metrics.trajectory_valid and metrics.budget_adhered


def test_unavailable_resources_remain_none_in_aggregate() -> None:
    metric = EvaluationMetrics(
        task_completed=True,
        final_answer_schema_valid=True,
        evidence_precision=1,
        evidence_recall=1,
        provenance_valid=True,
        unsupported_claim_rate=0,
        tool_selection_valid_rate=1,
        routing_correct=True,
        trajectory_valid=True,
        unnecessary_actions=0,
        repeated_actions=0,
        recovered_from_failure=None,
        budget_adhered=True,
        human_interventions=0,
        model_calls=1,
        tool_calls=0,
        input_tokens=None,
        output_tokens=None,
        total_tokens=None,
        latency_seconds=None,
        cost_usd=None,
        peak_memory_mb=None,
        structured_output_valid_rate=1,
    )
    aggregate = aggregate_metrics([metric])
    assert aggregate.mean_total_tokens is None
    assert aggregate.mean_latency_seconds is None
    assert aggregate.mean_cost_usd is None
    assert aggregate.mean_peak_memory_mb is None


def test_repeated_experiment_is_deterministic_and_serialisable(tmp_path: Path) -> None:
    run_root = tmp_path / "runs"
    baseline = PlainPythonCaseStudy(output_root=run_root)

    async def implementation(variant: CaseStudyVariant, run_id: str) -> AgentState:
        return await baseline.run(variant, run_id=run_id)

    configuration = ExperimentConfig(
        experiment_id="repeat",
        implementation="plain-python",
        variants=(CaseStudyVariant.STANDARD, CaseStudyVariant.TOOL_FAILURE),
        repetitions=2,
        task_specification_hash=case_study_hash(),
    )
    result = asyncio.run(
        ExperimentRunner(
            implementation,
            run_root=run_root,
            result_root=tmp_path / "evaluations",
        ).run(configuration)
    )
    assert len(result.runs) == 4
    for left, right in ((result.runs[0], result.runs[1]), (result.runs[2], result.runs[3])):
        assert left.metrics.model_dump(exclude={"latency_seconds"}) == right.metrics.model_dump(
            exclude={"latency_seconds"}
        )
    restored = ExperimentResult.model_validate_json(result.model_dump_json())
    assert restored == result
    assert len(result.configuration_hash) == 64
    assert (tmp_path / "evaluations" / "repeat" / "result.json").exists()
