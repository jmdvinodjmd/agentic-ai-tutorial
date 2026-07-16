"""Evaluate the OpenAI Agents SDK implementation through the shared harness."""

from __future__ import annotations

import asyncio

from agentic_tutorial.case_study import CaseStudyVariant, case_study_hash
from agentic_tutorial.evaluation import ExperimentConfig, ExperimentRunner
from agentic_tutorial.schemas import AgentState
from frameworks.openai_agents import OpenAIAgentsCaseStudy


async def main() -> None:
    implementation = OpenAIAgentsCaseStudy()

    async def run(variant: CaseStudyVariant, run_id: str) -> AgentState:
        return await implementation.run(variant, run_id=run_id)

    result = await ExperimentRunner(run).run(
        ExperimentConfig(
            experiment_id="openai-agents-offline",
            implementation="openai-agents-sdk",
            variants=tuple(CaseStudyVariant),
            repetitions=1,
            task_specification_hash=case_study_hash(),
            provider_metadata={"provider": "deterministic-mock"},
        )
    )
    print(result.aggregate.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
