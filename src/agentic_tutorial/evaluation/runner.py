"""Repeated experiment orchestration over implementation-neutral callables."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from pathlib import Path

from agentic_tutorial.case_study import CaseStudyDefinition, CaseStudyVariant, load_definition
from agentic_tutorial.evaluation.metrics import aggregate_metrics, evaluate_run
from agentic_tutorial.evaluation.models import EvaluationRun, ExperimentConfig, ExperimentResult
from agentic_tutorial.schemas import AgentState
from agentic_tutorial.tracing import TraceReader

ImplementationRunner = Callable[[CaseStudyVariant, str], Awaitable[AgentState]]


class ExperimentRunner:
    """Evaluate any implementation that returns canonical ``AgentState`` objects."""

    def __init__(
        self,
        implementation: ImplementationRunner,
        *,
        run_root: str | Path = "outputs/runs",
        result_root: str | Path = "outputs/evaluations",
        definition: CaseStudyDefinition | None = None,
    ) -> None:
        self.implementation = implementation
        self.run_root = Path(run_root)
        self.result_root = Path(result_root)
        self.definition = definition or load_definition()

    async def run(self, configuration: ExperimentConfig) -> ExperimentResult:
        """Run every matched variant/repetition and retain raw canonical artefacts."""
        records: list[EvaluationRun] = []
        for variant_name in configuration.variants:
            variant = self.definition.variant(variant_name)
            for repetition in range(1, configuration.repetitions + 1):
                run_id = f"{configuration.experiment_id}-{variant_name.value}-{repetition}"
                state = await self.implementation(variant_name, run_id)
                run_directory = self.run_root / run_id
                state_path = run_directory / "state.json"
                state_path.parent.mkdir(parents=True, exist_ok=True)
                state_path.write_text(state.model_dump_json(indent=2) + "\n", encoding="utf-8")
                trace_path = run_directory / "trace.jsonl"
                final_path = run_directory / "final_answer.json"
                metrics = evaluate_run(
                    state,
                    TraceReader(trace_path).read(),
                    variant,
                    self.definition,
                )
                records.append(
                    EvaluationRun(
                        experiment_id=configuration.experiment_id,
                        run_id=run_id,
                        implementation=configuration.implementation,
                        variant=variant_name,
                        repetition=repetition,
                        metrics=metrics,
                        state_path=state_path.as_posix(),
                        trace_path=trace_path.as_posix(),
                        final_answer_path=final_path.as_posix() if final_path.exists() else None,
                        provider_metadata=configuration.provider_metadata,
                        local_model_metadata=configuration.local_model_metadata,
                    )
                )
        result = ExperimentResult(
            configuration=configuration,
            configuration_hash=_configuration_hash(configuration),
            runs=tuple(records),
            aggregate=aggregate_metrics([record.metrics for record in records]),
        )
        directory = self.result_root / configuration.experiment_id
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "result.json").write_text(
            result.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        (directory / "summary.json").write_text(
            json.dumps(result.aggregate.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return result


def _configuration_hash(configuration: ExperimentConfig) -> str:
    encoded = json.dumps(
        configuration.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()
