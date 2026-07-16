"""Run the matched deterministic comparison across the four implementations."""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import importlib.metadata
import io
import json
import os
import platform
import statistics
import subprocess
import sys
import time
import tracemalloc
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from packaging.requirements import Requirement
from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentic_tutorial.case_study import CaseStudyVariant, case_study_hash, load_definition
from agentic_tutorial.case_study.plain_python import PlainPythonCaseStudy
from agentic_tutorial.evaluation import EvaluationMetrics, evaluate_run
from agentic_tutorial.schemas import TerminationStatus
from agentic_tutorial.tracing import TraceEvent, TraceEventType, TraceReader
from frameworks.crewai import CrewAICaseStudy
from frameworks.langgraph import LangGraphCaseStudy
from frameworks.openai_agents import OpenAIAgentsCaseStudy

ImplementationName = Literal["plain-python", "langgraph", "crewai", "openai-agents"]


class ComparisonModel(BaseModel):
    """Strict versioned base for comparison configuration and results."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    comparison_schema_version: Literal["1"] = "1"


class ComparisonConfig(ComparisonModel):
    """Inputs held constant across every framework run."""

    experiment_id: str = Field(default="matched-offline-v1", min_length=1)
    implementations: tuple[ImplementationName, ...] = (
        "plain-python",
        "langgraph",
        "crewai",
        "openai-agents",
    )
    variant: Literal[CaseStudyVariant.STANDARD] = CaseStudyVariant.STANDARD
    repetitions: int = Field(default=3, ge=2, le=20)
    provider: Literal["deterministic-mock"] = "deterministic-mock"
    output_root: str = "outputs/comparison"

    @model_validator(mode="after")
    def validate_matched_scope(self) -> ComparisonConfig:
        expected = {"plain-python", "langgraph", "crewai", "openai-agents"}
        if len(self.implementations) != 4 or set(self.implementations) != expected:
            raise ValueError("the matched comparison requires each of the four implementations")
        output = Path(self.output_root)
        if output.is_absolute() or ".." in output.parts:
            raise ValueError("output_root must be a repository-relative path")
        return self


class DependencyFootprint(ComparisonModel):
    distribution: str
    version: str
    transitive_distribution_count: int = Field(ge=1)
    installed_size_mb: float = Field(ge=0.0)


class ImplementationProfile(ComparisonModel):
    implementation: ImplementationName
    orchestration_path: str
    orchestration_nonblank_noncomment_lines: int = Field(ge=1)
    dependency_footprint: DependencyFootprint
    checkpoint_resume_verified: bool
    human_approval_support: str
    autonomous_features_disabled: tuple[str, ...] = ()
    strength: str
    limitation: str


class ComparisonRun(ComparisonModel):
    implementation: ImplementationName
    repetition: int = Field(gt=0)
    run_id: str
    metrics: EvaluationMetrics
    total_steps: int = Field(ge=0)
    framework_specific_trace_events: int = Field(ge=0)
    framework_event_kinds: dict[str, int]
    wall_latency_seconds: float = Field(ge=0.0)
    python_peak_allocated_mb: float = Field(ge=0.0)
    state_path: str
    trace_path: str
    manifest_path: str


class ImplementationAggregate(ComparisonModel):
    implementation: ImplementationName
    repetitions: int = Field(gt=0)
    task_completion_rate: float
    final_answer_valid_rate: float
    mean_evidence_precision: float
    mean_evidence_recall: float
    mean_tool_selection_validity: float
    trajectory_valid_rate: float
    failure_recovery: None = None
    mean_model_calls: float
    mean_tool_calls: float
    mean_total_steps: float
    mean_framework_specific_trace_events: float
    mean_wall_latency_seconds: float
    wall_latency_stddev_seconds: float
    mean_python_peak_allocated_mb: float
    python_peak_allocated_stddev_mb: float
    mean_startup_overhead_seconds: float
    startup_overhead_stddev_seconds: float


class ComparisonResult(ComparisonModel):
    experiment_id: str
    configuration_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_specification_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: datetime
    code_revision: str
    python_version: str
    platform: str
    fairness_controls: tuple[str, ...]
    profiles: tuple[ImplementationProfile, ...]
    runs: tuple[ComparisonRun, ...]
    aggregates: tuple[ImplementationAggregate, ...]


IMPLEMENTATIONS: dict[
    ImplementationName,
    tuple[
        type[PlainPythonCaseStudy | LangGraphCaseStudy | CrewAICaseStudy | OpenAIAgentsCaseStudy],
        str,
        str,
    ],
] = {
    "plain-python": (
        PlainPythonCaseStudy,
        "src/agentic_tutorial/case_study/plain_python.py",
        "agentic_tutorial.case_study.plain_python",
    ),
    "langgraph": (
        LangGraphCaseStudy,
        "frameworks/langgraph/research_assistant.py",
        "frameworks.langgraph.research_assistant",
    ),
    "crewai": (
        CrewAICaseStudy,
        "frameworks/crewai/research_assistant.py",
        "frameworks.crewai.research_assistant",
    ),
    "openai-agents": (
        OpenAIAgentsCaseStudy,
        "frameworks/openai_agents/research_assistant.py",
        "frameworks.openai_agents.research_assistant",
    ),
}

PROFILE_NOTES: dict[ImplementationName, tuple[tuple[str, ...], str, str]] = {
    "plain-python": (
        (),
        "Transparent reference flow with no framework-native state.",
        "The application owns all orchestration and persistence integration.",
    ),
    "langgraph": (
        (),
        "Explicit nodes, conditional edges and visible recovery cycles.",
        "Native checkpoints are in-memory here; durable resume uses canonical JSON state.",
    ),
    "crewai": (
        ("autonomous delegation", "memory", "manager calls", "automatic planning", "retries"),
        "Functionally distinct specialist agents and task ownership.",
        "Disabling autonomous features is necessary to prevent unmatched hidden calls.",
    ),
    "openai-agents": (
        ("autonomous Runner", "SDK retries", "SDK sessions", "hosted tracing"),
        "First-class agents, function tools, handoffs, context and guardrails.",
        "The autonomous Runner is excluded because it would own unmatched model turns.",
    ),
}

DISTRIBUTIONS: dict[ImplementationName, str] = {
    "plain-python": "agentic-ai-tutorial",
    "langgraph": "langgraph",
    "crewai": "crewai",
    "openai-agents": "openai-agents",
}


async def run_comparison(configuration: ComparisonConfig) -> ComparisonResult:
    """Run matched standard tasks and retain every canonical raw artefact."""
    root = Path(configuration.output_root)
    definition = load_definition()
    variant = definition.variant(configuration.variant)
    records: list[ComparisonRun] = []
    profiles: list[ImplementationProfile] = []
    startup: dict[ImplementationName, list[float]] = {}

    for name in configuration.implementations:
        implementation_type, source_path, import_module = IMPLEMENTATIONS[name]
        implementation_root = root / "runs" / name
        implementation = implementation_type(output_root=implementation_root)
        startup[name] = [_measure_import(import_module) for _ in range(configuration.repetitions)]
        for repetition in range(1, configuration.repetitions + 1):
            run_id = f"{configuration.experiment_id}-{name}-{repetition}"
            tracemalloc.start()
            started = time.perf_counter()
            state = await implementation.run(configuration.variant, run_id=run_id)
            wall_latency = time.perf_counter() - started
            _, peak_bytes = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            run_directory = implementation_root / run_id
            state_path = run_directory / "state.json"
            state_path.write_text(state.model_dump_json(indent=2) + "\n", encoding="utf-8")
            events = TraceReader(run_directory / "trace.jsonl").read()
            metrics = evaluate_run(state, events, variant, definition)
            kinds = _framework_event_kinds(events)
            records.append(
                ComparisonRun(
                    implementation=name,
                    repetition=repetition,
                    run_id=run_id,
                    metrics=metrics,
                    total_steps=len(state.steps),
                    framework_specific_trace_events=sum(kinds.values()),
                    framework_event_kinds=kinds,
                    wall_latency_seconds=wall_latency,
                    python_peak_allocated_mb=peak_bytes / (1024 * 1024),
                    state_path=state_path.as_posix(),
                    trace_path=(run_directory / "trace.jsonl").as_posix(),
                    manifest_path=(run_directory / "manifest.json").as_posix(),
                )
            )
        checkpoint_verified = await _verify_checkpoint_resume(
            implementation,
            configuration.variant,
            f"{configuration.experiment_id}-{name}-resume",
        )
        disabled, strength, limitation = PROFILE_NOTES[name]
        profiles.append(
            ImplementationProfile(
                implementation=name,
                orchestration_path=source_path,
                orchestration_nonblank_noncomment_lines=_source_lines(Path(source_path)),
                dependency_footprint=_dependency_footprint(DISTRIBUTIONS[name]),
                checkpoint_resume_verified=checkpoint_verified,
                human_approval_support=(
                    "Shared exact-action policy and canonical checkpoint boundary; "
                    "not triggered by the read-only comparison task."
                ),
                autonomous_features_disabled=disabled,
                strength=strength,
                limitation=limitation,
            )
        )

    result = ComparisonResult(
        experiment_id=configuration.experiment_id,
        configuration_hash=_hash(configuration.model_dump(mode="json")),
        task_specification_hash=case_study_hash(definition),
        generated_at=datetime.now(UTC),
        code_revision=_code_revision(),
        python_version=platform.python_version(),
        platform=platform.platform(),
        fairness_controls=(
            "One standard task specification and deterministic mock response fixture.",
            "Identical prompts, canonical tools, budgets, safety policy and stopping rules.",
            "Every implementation is scored by the same deterministic evaluator.",
            "Framework defaults that introduce hidden model calls, retries or memory are disabled.",
            "Latency, memory, dependency footprint and source size are descriptive, "
            "not equality criteria.",
        ),
        profiles=tuple(profiles),
        runs=tuple(records),
        aggregates=tuple(
            _aggregate(name, records, startup[name]) for name in configuration.implementations
        ),
    )
    _write_results(root, configuration, result)
    return result


async def _verify_checkpoint_resume(
    implementation: PlainPythonCaseStudy
    | LangGraphCaseStudy
    | CrewAICaseStudy
    | OpenAIAgentsCaseStudy,
    variant: CaseStudyVariant,
    run_id: str,
) -> bool:
    first = await implementation.run(variant, run_id=run_id, interrupt_after_steps=2)
    resumed = await implementation.run(variant, run_id=run_id, resume=True)
    return (
        first.termination is not None
        and first.termination.status is TerminationStatus.INTERRUPTED
        and len(first.steps) == 2
        and resumed.termination is not None
        and resumed.termination.status is TerminationStatus.SUCCESS
        and resumed.steps[:2] == first.steps
    )


def _framework_event_kinds(events: Sequence[TraceEvent]) -> dict[str, int]:
    kinds: dict[str, int] = {}
    for event in events:
        if event.event_type is not TraceEventType.DECISION:
            continue
        for key in ("framework_node", "delegation", "handoff", "recovery"):
            if key in event.payload:
                kinds[key] = kinds.get(key, 0) + 1
    return kinds


def _aggregate(
    name: ImplementationName,
    records: Sequence[ComparisonRun],
    startup: Sequence[float],
) -> ImplementationAggregate:
    selected = [record for record in records if record.implementation == name]
    metrics = [record.metrics for record in selected]
    latency = [record.wall_latency_seconds for record in selected]
    memory = [record.python_peak_allocated_mb for record in selected]
    return ImplementationAggregate(
        implementation=name,
        repetitions=len(selected),
        task_completion_rate=_mean([item.task_completed for item in metrics]),
        final_answer_valid_rate=_mean([item.final_answer_schema_valid for item in metrics]),
        mean_evidence_precision=_mean([item.evidence_precision for item in metrics]),
        mean_evidence_recall=_mean([item.evidence_recall for item in metrics]),
        mean_tool_selection_validity=_mean([item.tool_selection_valid_rate for item in metrics]),
        trajectory_valid_rate=_mean([item.trajectory_valid for item in metrics]),
        failure_recovery=None,
        mean_model_calls=_mean([item.model_calls for item in metrics]),
        mean_tool_calls=_mean([item.tool_calls for item in metrics]),
        mean_total_steps=_mean([item.total_steps for item in selected]),
        mean_framework_specific_trace_events=_mean(
            [item.framework_specific_trace_events for item in selected]
        ),
        mean_wall_latency_seconds=_mean(latency),
        wall_latency_stddev_seconds=_stddev(latency),
        mean_python_peak_allocated_mb=_mean(memory),
        python_peak_allocated_stddev_mb=_stddev(memory),
        mean_startup_overhead_seconds=_mean(startup),
        startup_overhead_stddev_seconds=_stddev(startup),
    )


def _measure_import(module: str) -> float:
    code = (
        "import time\n"
        "started=time.perf_counter()\n"
        f"import {module}\n"
        "print(time.perf_counter()-started)\n"
    )
    environment = dict(os.environ)
    environment.update(
        {
            "CREWAI_DISABLE_TRACKING": "true",
            "CREWAI_TRACING_ENABLED": "false",
            "OTEL_SDK_DISABLED": "true",
        }
    )
    process = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    return float(process.stdout.strip().splitlines()[-1])


def _dependency_footprint(distribution_name: str) -> DependencyFootprint:
    names = _dependency_closure(distribution_name)
    size = 0
    for name in names:
        distribution = importlib.metadata.distribution(name)
        for file in distribution.files or ():
            path = Path(str(distribution.locate_file(file)))
            try:
                if path.is_file():
                    size += path.stat().st_size
            except OSError:
                continue
    root = importlib.metadata.distribution(distribution_name)
    return DependencyFootprint(
        distribution=distribution_name,
        version=root.version,
        transitive_distribution_count=len(names),
        installed_size_mb=size / (1024 * 1024),
    )


def _dependency_closure(root_name: str) -> set[str]:
    pending = [root_name]
    found: set[str] = set()
    while pending:
        name = pending.pop()
        normalised = name.casefold().replace("_", "-")
        if normalised in found:
            continue
        found.add(normalised)
        distribution = importlib.metadata.distribution(name)
        for raw_requirement in distribution.requires or ():
            requirement = Requirement(raw_requirement)
            if requirement.marker is not None and not requirement.marker.evaluate({"extra": ""}):
                continue
            dependency = requirement.name.casefold().replace("_", "-")
            if dependency not in found:
                pending.append(requirement.name)
    return found


def _source_lines(path: Path) -> int:
    return sum(
        bool(line.strip()) and not line.lstrip().startswith("#")
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def _hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _code_revision() -> str:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return f"{revision}+dirty" if dirty else revision


def _mean(values: Sequence[int | float | bool]) -> float:
    return statistics.fmean(float(value) for value in values)


def _stddev(values: Sequence[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def _write_results(
    root: Path,
    configuration: ComparisonConfig,
    result: ComparisonResult,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.json").write_text(
        configuration.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (root / "result.json").write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    output = io.StringIO()
    fieldnames = list(ImplementationAggregate.model_fields)
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for aggregate in result.aggregates:
        writer.writerow(aggregate.model_dump(mode="json"))
    (root / "summary.csv").write_text(output.getvalue(), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output-root", default="outputs/comparison")
    parser.add_argument("--snapshot-root")
    args = parser.parse_args()
    configuration = ComparisonConfig(
        repetitions=args.repetitions,
        output_root=args.output_root,
    )
    result = asyncio.run(run_comparison(configuration))
    if args.snapshot_root:
        _write_results(Path(args.snapshot_root), configuration, result)
    print(
        json.dumps(
            {
                aggregate.implementation: {
                    "model_calls": aggregate.mean_model_calls,
                    "task_completion": aggregate.task_completion_rate,
                    "tool_calls": aggregate.mean_tool_calls,
                }
                for aggregate in result.aggregates
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
