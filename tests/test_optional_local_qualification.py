"""Optional 8/8 qualification against a separately downloaded local GGUF."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from agentic_tutorial.evaluation import (
    MalformedResponseFaultClient,
    ModelCandidate,
    select_first_qualified,
)
from agentic_tutorial.models import (
    GenerationSettings,
    ModelClient,
    ModelConfig,
    create_model_client,
)
from agentic_tutorial.schemas import RecoveryDecision

ROOT = Path(__file__).parents[1]


@pytest.mark.slow
def test_smallest_local_candidate_qualifies_before_selection() -> None:
    model_path = os.getenv("AGENTIC_TUTORIAL_LOCAL_MODEL_PATH")
    if not model_path or not Path(model_path).is_file():
        pytest.skip("verified local GGUF model is unavailable")
    pytest.importorskip("llama_cpp")
    payload = json.loads((ROOT / "models/qualification_candidates.json").read_text())
    candidates = tuple(ModelCandidate.model_validate(item) for item in payload["candidates"])

    async def client_factory(candidate: ModelCandidate) -> ModelClient:
        client = create_model_client(
            ModelConfig(
                provider="local-llama-cpp",
                model=candidate.model,
                execution_mode="local",
                settings=GenerationSettings(temperature=0.0, max_output_tokens=256, seed=0),
                options={
                    "model_path": model_path,
                    "metadata_path": candidate.metadata_path,
                    "timeout_seconds": 180.0,
                },
            )
        )
        return MalformedResponseFaultClient(client, on_schema=RecoveryDecision)

    selected, reports = asyncio.run(select_first_qualified(candidates, client_factory))
    assert reports
    assert selected is not None, [report.model_dump(mode="json") for report in reports]
    assert reports[-1].qualified and reports[-1].passed_count == 8
