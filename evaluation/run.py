"""Run all common case-study variants through the deterministic evaluator."""

from __future__ import annotations

import asyncio
import json
from typing import cast

from agentic_tutorial.case_study import CaseStudyVariant, case_study_hash
from agentic_tutorial.case_study.plain_python import PlainPythonCaseStudy
from agentic_tutorial.evaluation import ExperimentConfig, ExperimentRunner
from agentic_tutorial.schemas import AgentState


async def _run() -> dict[str, object]:
    baseline = PlainPythonCaseStudy()

    async def implementation(variant: CaseStudyVariant, run_id: str) -> AgentState:
        return await baseline.run(variant, run_id=run_id)

    result = await ExperimentRunner(implementation).run(
        ExperimentConfig(
            experiment_id="plain-python-offline-v1",
            implementation="plain-python",
            variants=tuple(CaseStudyVariant),
            task_specification_hash=case_study_hash(),
            provider_metadata={"provider": "deterministic-mock", "model": "case-study-script-v1"},
        )
    )
    return cast(dict[str, object], result.aggregate.model_dump(mode="json"))


def main() -> int:
    print(json.dumps(asyncio.run(_run()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
