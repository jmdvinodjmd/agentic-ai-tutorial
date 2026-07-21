"""Optional 8/8 qualification against Gemini's live API."""

from __future__ import annotations

import asyncio
import os

import pytest

from agentic_tutorial.evaluation import MalformedResponseFaultClient, qualify_model
from agentic_tutorial.models import GenerationSettings, ModelConfig, create_model_client
from agentic_tutorial.schemas import RecoveryDecision


@pytest.mark.slow
def test_gemini_passes_all_qualification_checks() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY is unavailable")

    client = create_model_client(
        ModelConfig(
            provider="gemini",
            model=os.getenv("MODEL_NAME", "gemini-2.5-flash-lite"),
            execution_mode="live",
            settings=GenerationSettings(temperature=0.0, max_output_tokens=256),
            options={"timeout_seconds": 60.0},
        )
    )
    injected_client = MalformedResponseFaultClient(client, on_schema=RecoveryDecision)
    report = asyncio.run(qualify_model(injected_client))

    assert report.qualified and report.passed_count == 8, report.model_dump(mode="json")
