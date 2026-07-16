"""Tests for T03 deterministic mock and strict replay clients."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from agentic_tutorial.models import (
    DeterministicMockClient,
    InvalidModelResponseError,
    ModelConfig,
    ReplayClient,
    ReplayMismatchError,
    create_model_client,
)
from agentic_tutorial.schemas import FinalAnswer, Message, MessageRole, ToolDefinition

FIXTURES = Path(__file__).parent / "fixtures" / "models"
MOCK_FIXTURE = FIXTURES / "mock" / "scenario_v1.json"
REPLAY_FIXTURE = FIXTURES / "replay" / "catalogue_v1.jsonl"


def _tool() -> ToolDefinition:
    return ToolDefinition(
        name="catalogue_search",
        description="Search the fixed local catalogue.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )


def test_mock_repeated_runs_are_byte_equivalent() -> None:
    async def run_once() -> bytes:
        client = DeterministicMockClient.from_file(MOCK_FIXTURE, scenario="catalogue-answer")
        first = await client.generate(
            [Message(role=MessageRole.USER, content="find evidence")], tools=[_tool()]
        )
        second = await client.generate(
            [Message(role=MessageRole.USER, content="finish")], response_schema=FinalAnswer
        )
        payload = [first.model_dump(mode="json"), second.model_dump(mode="json")]
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

    assert asyncio.run(run_once()) == asyncio.run(run_once())


def test_mock_supports_registry_construction() -> None:
    client = create_model_client(
        ModelConfig(
            provider="deterministic-mock",
            model="offline-fixture-v1",
            options={"fixture_path": str(MOCK_FIXTURE), "scenario": "catalogue-answer"},
        )
    )

    assert isinstance(client, DeterministicMockClient)
    assert client.scenario == "catalogue-answer"


def test_replay_supports_registry_construction() -> None:
    client = create_model_client(
        ModelConfig(
            provider="replay",
            model="recorded-fixture-v1",
            execution_mode="replay",
            options={"fixture_path": str(REPLAY_FIXTURE)},
        )
    )

    assert isinstance(client, ReplayClient)
    assert client.scenario == "catalogue-replay"


def test_mock_exhaustion_fails_explicitly() -> None:
    async def exhaust() -> None:
        client = DeterministicMockClient.from_file(MOCK_FIXTURE)
        await client.generate([Message(role=MessageRole.USER, content="one")], tools=[_tool()])
        await client.generate(
            [Message(role=MessageRole.USER, content="two")], response_schema=FinalAnswer
        )
        await client.generate([Message(role=MessageRole.USER, content="three")])

    with pytest.raises(InvalidModelResponseError, match="exhausted"):
        asyncio.run(exhaust())


def test_replay_returns_only_matching_recorded_responses() -> None:
    async def replay() -> tuple[str, str]:
        client = ReplayClient.from_jsonl(REPLAY_FIXTURE)
        first = await client.generate(
            [Message(role=MessageRole.USER, content="Find evidence about agent evaluation.")],
            tools=[_tool()],
        )
        second = await client.generate(
            [Message(role=MessageRole.USER, content="Return the structured final answer.")],
            response_schema=FinalAnswer,
        )
        return first.response_id, second.response_id

    assert asyncio.run(replay()) == ("replay-response-001", "replay-response-002")


@pytest.mark.parametrize(
    ("messages", "tools"),
    [
        ([Message(role=MessageRole.USER, content="different request")], [_tool()]),
        ([Message(role=MessageRole.USER, content="Find evidence about agent evaluation.")], []),
    ],
)
def test_replay_request_mismatch_is_diagnostic(
    messages: list[Message], tools: list[ToolDefinition]
) -> None:
    client = ReplayClient.from_jsonl(REPLAY_FIXTURE)

    with pytest.raises(ReplayMismatchError, match=r"replay mismatch at step 1: .+ differ"):
        asyncio.run(client.generate(messages, tools=tools))


def test_replay_response_schema_mismatch_is_diagnostic() -> None:
    async def mismatch() -> None:
        client = ReplayClient.from_jsonl(REPLAY_FIXTURE)
        await client.generate(
            [Message(role=MessageRole.USER, content="Find evidence about agent evaluation.")],
            tools=[_tool()],
        )
        await client.generate(
            [Message(role=MessageRole.USER, content="Return the structured final answer.")]
        )

    with pytest.raises(ReplayMismatchError, match="response_schema differ"):
        asyncio.run(mismatch())


@pytest.mark.parametrize(
    ("contents", "expected"),
    [
        ("not-json", "invalid deterministic mock fixture"),
        ('{"fixture_version":"1"}', "invalid deterministic mock fixture"),
    ],
)
def test_malformed_mock_fixtures_fail_clearly(tmp_path: Path, contents: str, expected: str) -> None:
    path = tmp_path / "mock.json"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(InvalidModelResponseError, match=expected):
        DeterministicMockClient.from_file(path)


@pytest.mark.parametrize(
    "contents",
    [
        "not-json\n",
        '{"record_type":"header","fixture_version":"1","scenario":"x",'
        '"provenance":{"source":"x","description":"x","recorded_by":"x"}}\n',
        '{"record_type":"response","step":1}\n',
    ],
)
def test_malformed_replay_fixtures_fail_clearly(tmp_path: Path, contents: str) -> None:
    path = tmp_path / "replay.jsonl"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(InvalidModelResponseError, match="invalid replay fixture"):
        ReplayClient.from_jsonl(path)
