"""Reusable evaluation contract tests."""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from agentic_tutorial.evaluation import MalformedResponseFaultClient, qualify_model
from agentic_tutorial.models import DeterministicMockClient, GeminiClient, InvalidModelResponseError
from agentic_tutorial.schemas import Message, MessageRole, RecoveryDecision

FIXTURE = Path(__file__).parent / "fixtures" / "models" / "qualification" / "mock_v1.json"


def test_model_qualification_reports_every_required_check() -> None:
    report = asyncio.run(qualify_model(DeterministicMockClient.from_file(FIXTURE)))

    assert report.qualified
    assert report.required_passes == report.passed_count == 8
    assert all(check.passed for check in report.checks)


def test_malformed_response_fault_is_injected_once_then_delegates() -> None:
    def transport(
        url: str,
        api_key: str,
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        del url, api_key, payload, timeout_seconds
        return {
            "candidates": [
                {
                    "content": {"parts": [{"text": '{"action":"retry","reason":"bounded"}'}]},
                    "finishReason": "STOP",
                }
            ]
        }

    async def exercise() -> None:
        client = MalformedResponseFaultClient(
            GeminiClient(model="gemini-test", api_key="test-secret", transport=transport),
            on_schema=RecoveryDecision,
        )
        messages = [Message(role=MessageRole.USER, content="Recover safely.")]
        with pytest.raises(InvalidModelResponseError, match="injected malformed"):
            await client.generate(messages, response_schema=RecoveryDecision)
        response = await client.generate(messages, response_schema=RecoveryDecision)
        assert response.structured_output is not None
        assert response.structured_output["action"] == "retry"
        assert response.structured_output["reason"] == "bounded"

    asyncio.run(exercise())
