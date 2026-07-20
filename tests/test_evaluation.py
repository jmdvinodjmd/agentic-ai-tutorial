"""Reusable evaluation contract tests."""

import asyncio
from pathlib import Path

from agentic_tutorial.evaluation import qualify_model
from agentic_tutorial.models import DeterministicMockClient

FIXTURE = Path(__file__).parent / "fixtures" / "models" / "qualification" / "mock_v1.json"


def test_model_qualification_reports_every_required_check() -> None:
    report = asyncio.run(qualify_model(DeterministicMockClient.from_file(FIXTURE)))

    assert report.qualified
    assert report.required_passes == report.passed_count == 8
    assert all(check.passed for check in report.checks)
