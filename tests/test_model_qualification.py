"""Deterministic qualification and candidate-order tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from agentic_tutorial.evaluation import ModelCandidate, qualify_model, select_first_qualified
from agentic_tutorial.models import DeterministicMockClient

FIXTURE = Path(__file__).parent / "fixtures" / "models" / "qualification" / "mock_v1.json"
CANDIDATES = Path(__file__).parents[1] / "models" / "qualification_candidates.json"


def test_mock_passes_all_eight_qualification_checks() -> None:
    report = asyncio.run(qualify_model(DeterministicMockClient.from_file(FIXTURE)))

    assert report.qualified
    assert report.passed_count == report.required_passes == 8
    assert [check.name for check in report.checks] == [
        "schema_valid",
        "routing",
        "tool_selection",
        "tool_arguments",
        "planning",
        "critic",
        "stopping",
        "malformed_recovery",
    ]


def test_candidate_manifest_starts_with_smallest_model_and_is_not_prequalified() -> None:
    payload = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    sizes = [candidate["parameter_count_billions"] for candidate in payload["candidates"]]

    assert sizes == sorted(sizes)
    assert payload["candidates"][0]["model"] == "Qwen3-0.6B-Q8_0"
    assert payload["selection_status"] == "not_yet_qualified"


def test_selection_stops_at_first_qualified_candidate_in_size_order() -> None:
    attempted: list[str] = []
    candidates = [
        ModelCandidate(model="larger", parameter_count_billions=1.7, metadata_path="larger.json"),
        ModelCandidate(model="smallest", parameter_count_billions=0.6, metadata_path="small.json"),
    ]

    async def factory(candidate: ModelCandidate) -> DeterministicMockClient:
        attempted.append(candidate.model)
        return DeterministicMockClient.from_file(FIXTURE)

    selected, reports = asyncio.run(select_first_qualified(candidates, factory))

    assert selected is not None
    assert selected.model == "smallest"
    assert attempted == ["smallest"]
    assert len(reports) == 1
