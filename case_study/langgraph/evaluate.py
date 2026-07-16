"""Evaluate the LangGraph implementation through the shared harness."""

from __future__ import annotations

import asyncio

from agentic_tutorial.case_study import CaseStudyVariant, case_study_hash
from agentic_tutorial.evaluation import ExperimentConfig, ExperimentRunner
from agentic_tutorial.schemas import AgentState
from frameworks.langgraph import LangGraphCaseStudy


async def main() -> None:
    implementation = LangGraphCaseStudy()

    async def run(variant: CaseStudyVariant, run_id: str) -> AgentState:
        return await implementation.run(variant, run_id=run_id)

    result = await ExperimentRunner(run).run(
        ExperimentConfig(
            experiment_id="langgraph-offline",
            implementation="langgraph",
            variants=tuple(CaseStudyVariant),
            repetitions=1,
            task_specification_hash=case_study_hash(),
            provider_metadata={"provider": "deterministic-mock"},
        )
    )
    print(result.aggregate.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
