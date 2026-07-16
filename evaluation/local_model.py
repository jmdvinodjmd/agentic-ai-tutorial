"""Optional local-model evaluation; never used by the core test suite."""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import platform
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from agentic_tutorial.case_study import (
    CaseStudyVariant,
    PlainPythonCaseStudy,
    case_study_hash,
    load_definition,
)
from agentic_tutorial.evaluation import ExperimentConfig, ExperimentRunner
from agentic_tutorial.models import ModelConfig, create_model_client
from agentic_tutorial.schemas import AgentState, Message, MessageRole


class LocalTutorialAnswer(BaseModel):
    """Small structured-output probe for the local runtime."""

    model_config = ConfigDict(extra="forbid")
    answer: str


def _configuration() -> ModelConfig:
    model_path = os.getenv("AGENTIC_TUTORIAL_LOCAL_MODEL_PATH")
    if not model_path:
        raise SystemExit("set AGENTIC_TUTORIAL_LOCAL_MODEL_PATH to a verified GGUF file")
    return ModelConfig.model_validate(
        {
            "provider": "local-llama-cpp",
            "model": Path(model_path).stem,
            "execution_mode": "local",
            "settings": {"temperature": 0.0, "max_output_tokens": 512, "seed": 0},
            "options": {
                "model_path": model_path,
                "metadata_path": "models/local/model_metadata.json",
                "context_size": 4096,
                "thread_count": max(1, os.cpu_count() or 1),
            },
        }
    )


async def main() -> None:
    """Run a structured probe and two matched case-study variants."""
    configuration = _configuration()
    probe_client = create_model_client(configuration)
    probe = await probe_client.generate(
        [Message(role=MessageRole.USER, content="Return JSON with answer set to ready.")],
        response_schema=LocalTutorialAnswer,
    )
    local_metadata = getattr(probe_client, "manifest_metadata", None)
    case_study = PlainPythonCaseStudy(
        model_factory=lambda _variant, _offset: create_model_client(configuration)
    )

    async def implementation(variant: CaseStudyVariant, run_id: str) -> AgentState:
        return await case_study.run(variant, run_id=run_id)

    definition = load_definition()
    result = await ExperimentRunner(implementation).run(
        ExperimentConfig(
            experiment_id="local-small-model",
            implementation="plain-python-local-llama-cpp",
            variants=(
                CaseStudyVariant.STANDARD,
                CaseStudyVariant.INSUFFICIENT_EVIDENCE,
            ),
            task_specification_hash=case_study_hash(definition),
            provider_metadata={"provider": configuration.provider},
            local_model_metadata=local_metadata,
        )
    )
    print(
        json.dumps(
            {
                "structured_output_valid": probe.structured_output is not None,
                "latency_seconds": getattr(
                    getattr(probe_client, "last_completion", None),
                    "latency_seconds",
                    None,
                ),
                "token_usage": probe.usage.model_dump(mode="json"),
                "peak_memory_mb": _peak_memory_mb(),
                "aggregate": result.aggregate.model_dump(mode="json"),
            },
            indent=2,
            sort_keys=True,
        )
    )


def _peak_memory_mb() -> float | None:
    try:
        resource_module = importlib.import_module("resource")
        value = float(resource_module.getrusage(resource_module.RUSAGE_SELF).ru_maxrss)
    except (ImportError, AttributeError, ValueError):
        return None
    return value / (1024 * 1024) if platform.system() == "Darwin" else value / 1024


if __name__ == "__main__":
    asyncio.run(main())
