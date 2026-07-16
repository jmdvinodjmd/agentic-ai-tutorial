"""Matched integration tests for OpenAI Agents SDK orchestration."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

import pytest
from agents import FunctionTool, Handoff

from agentic_tutorial.case_study import CaseStudyVariant, case_study_hash
from agentic_tutorial.evaluation import ExperimentConfig, ExperimentRunner
from agentic_tutorial.models.providers import ReplayClient
from agentic_tutorial.models.providers.fixtures import (
    CanonicalRequest,
    FixtureProvenance,
    ReplayHeader,
    ReplayRecord,
)
from agentic_tutorial.schemas import (
    AgentState,
    Budget,
    FinalAnswer,
    ModelResponse,
    TerminationReason,
    TerminationStatus,
)
from agentic_tutorial.tracing import TraceEventType, TraceReader, normalise_events
from frameworks.openai_agents import OpenAIAgentsCaseStudy


@pytest.mark.parametrize(
    ("variant", "model_calls", "tool_calls", "expected_sources"),
    [
        (CaseStudyVariant.STANDARD, 4, 3, {"source-001", "source-002"}),
        (CaseStudyVariant.INSUFFICIENT_EVIDENCE, 3, 2, set()),
        (CaseStudyVariant.TOOL_FAILURE, 5, 4, {"source-002"}),
    ],
)
def test_matched_variants_and_complete_call_accounting(
    tmp_path: Path,
    variant: CaseStudyVariant,
    model_calls: int,
    tool_calls: int,
    expected_sources: set[str],
) -> None:
    run_id = f"sdk-{variant.value}"
    state = asyncio.run(OpenAIAgentsCaseStudy(output_root=tmp_path).run(variant, run_id=run_id))

    assert state.termination is not None
    assert state.termination.status is TerminationStatus.SUCCESS
    assert state.usage.model_calls == model_calls
    assert state.usage.tool_calls == tool_calls
    assert state.final_answer is not None
    assert (
        FinalAnswer.model_validate_json(
            (tmp_path / run_id / "final_answer.json").read_text(encoding="utf-8")
        )
        == state.final_answer
    )
    assert {item.source_id for item in state.final_answer.evidence} == expected_sources

    events = TraceReader(tmp_path / run_id / "trace.jsonl").read()
    assert sum(event.event_type is TraceEventType.MODEL_RESPONSE for event in events) == model_calls
    assert sum(event.event_type is TraceEventType.TOOL_RESULT for event in events) == tool_calls
    assert (
        sum(
            event.event_type is TraceEventType.DECISION and "handoff" in event.payload
            for event in events
        )
        >= 4
    )
    assert {
        TraceEventType.POLICY_DECISION,
        TraceEventType.BUDGET,
        TraceEventType.CHECKPOINT,
        TraceEventType.TERMINATION,
    } <= {event.event_type for event in events}


def test_sdk_roles_tools_handoffs_and_guardrails_are_functional(tmp_path: Path) -> None:
    implementation = OpenAIAgentsCaseStudy(output_root=tmp_path)
    asyncio.run(implementation.run(CaseStudyVariant.STANDARD, run_id="sdk-structure"))
    structure = implementation.last_structure
    assert structure is not None

    agents = (
        structure.coordinator,
        structure.searcher,
        structure.extractor,
        structure.synthesiser,
        structure.critic,
    )
    assert len({agent.name for agent in agents}) == 5
    assert structure.permissions == {
        "coordinator": (),
        "search": ("search_catalogue",),
        "evidence": ("extract_evidence",),
        "synthesis": (),
        "critique": ("critique_draft",),
    }
    assert [tool.name for tool in structure.searcher.tools] == ["search_catalogue"]
    assert [tool.name for tool in structure.extractor.tools] == ["extract_evidence"]
    assert [tool.name for tool in structure.critic.tools] == ["critique_draft"]
    assert not structure.synthesiser.tools
    assert all(isinstance(tool, FunctionTool) for agent in agents for tool in agent.tools)
    assert all(isinstance(item, Handoff) for item in structure.handoffs.values())
    assert structure.coordinator.input_guardrails
    assert structure.coordinator.output_guardrails


def test_sdk_tool_schemas_are_canonical_adapters(tmp_path: Path) -> None:
    implementation = OpenAIAgentsCaseStudy(output_root=tmp_path)
    asyncio.run(implementation.run(CaseStudyVariant.STANDARD, run_id="sdk-tool-schema"))
    structure = implementation.last_structure
    assert structure is not None
    search_tool = structure.searcher.tools[0]
    assert isinstance(search_tool, FunctionTool)
    assert search_tool.params_json_schema["properties"] == {
        "query": {"title": "Query", "type": "string"}
    }
    assert search_tool.strict_json_schema

    async def invoke_tool() -> str:
        value = await search_tool.on_invoke_tool(
            cast(Any, None), '{"query":"trajectory evaluation"}'
        )
        assert isinstance(value, str)
        return value

    result = json.loads(asyncio.run(invoke_tool()))
    assert result["name"] == "search_catalogue"
    assert result["status"] == "success"


def test_clarification_interrupts_without_specialist_calls(tmp_path: Path) -> None:
    state = asyncio.run(
        OpenAIAgentsCaseStudy(output_root=tmp_path).run(
            CaseStudyVariant.CLARIFICATION_REQUIRED,
            run_id="sdk-clarification",
        )
    )
    assert state.termination is not None
    assert state.termination.status is TerminationStatus.INTERRUPTED
    assert state.usage.model_calls == 0
    assert state.usage.tool_calls == 0


def test_interruption_and_resume_do_not_repeat_successful_handoffs(tmp_path: Path) -> None:
    implementation = OpenAIAgentsCaseStudy(output_root=tmp_path)
    first = asyncio.run(
        implementation.run(
            CaseStudyVariant.STANDARD,
            run_id="sdk-resume",
            interrupt_after_steps=2,
        )
    )
    resumed = asyncio.run(
        implementation.run(CaseStudyVariant.STANDARD, run_id="sdk-resume", resume=True)
    )
    assert first.termination is not None
    assert first.termination.status is TerminationStatus.INTERRUPTED
    assert len(first.steps) == 2
    assert resumed.termination is not None
    assert resumed.termination.status is TerminationStatus.SUCCESS
    assert resumed.steps[:2] == first.steps
    assert resumed.usage.model_calls == 4
    assert resumed.usage.tool_calls == 3


def test_budget_termination_stops_handoffs_safely(tmp_path: Path) -> None:
    state = asyncio.run(
        OpenAIAgentsCaseStudy(output_root=tmp_path).run(
            CaseStudyVariant.STANDARD,
            run_id="sdk-budget",
            budget=Budget(max_steps=1),
        )
    )
    assert state.termination is not None
    assert state.termination.status is TerminationStatus.FAILURE
    assert state.termination.reason is TerminationReason.MAX_STEPS
    assert state.usage.model_calls == 1
    assert state.usage.tool_calls == 1


def test_repeated_runs_are_deterministic_after_normalisation(tmp_path: Path) -> None:
    implementation = OpenAIAgentsCaseStudy(output_root=tmp_path)
    left = asyncio.run(implementation.run(CaseStudyVariant.STANDARD, run_id="sdk-repeat-a"))
    right = asyncio.run(implementation.run(CaseStudyVariant.STANDARD, run_id="sdk-repeat-b"))
    assert _normalise_state(left) == _normalise_state(right)
    assert normalise_events(
        TraceReader(tmp_path / "sdk-repeat-a" / "trace.jsonl").read()
    ) == normalise_events(TraceReader(tmp_path / "sdk-repeat-b" / "trace.jsonl").read())


def test_strict_replay_uses_the_same_canonical_requests(tmp_path: Path) -> None:
    recorded = OpenAIAgentsCaseStudy(output_root=tmp_path / "recorded")
    expected = asyncio.run(recorded.run(CaseStudyVariant.STANDARD, run_id="sdk-recorded"))
    events = TraceReader(tmp_path / "recorded" / "sdk-recorded" / "trace.jsonl").read()
    requests = [
        CanonicalRequest.model_validate(event.payload)
        for event in events
        if event.event_type is TraceEventType.MODEL_REQUEST
    ]
    responses = [
        ModelResponse.model_validate(event.payload["response"])
        for event in events
        if event.event_type is TraceEventType.MODEL_RESPONSE
    ]
    fixture = tmp_path / "standard-replay.jsonl"
    lines = [
        ReplayHeader(
            record_type="header",
            fixture_version="1",
            scenario="sdk-standard-replay",
            provenance=FixtureProvenance(
                source="deterministic test recording",
                description="Canonical matched case-study requests.",
                recorded_by="automated test",
            ),
        ).model_dump_json(),
        *[
            ReplayRecord(
                record_type="response",
                step=index,
                request=request,
                response=response,
            ).model_dump_json()
            for index, (request, response) in enumerate(
                zip(requests, responses, strict=True), start=1
            )
        ],
    ]
    fixture.write_text("\n".join(lines) + "\n", encoding="utf-8")
    replayed = asyncio.run(
        OpenAIAgentsCaseStudy(
            output_root=tmp_path / "replayed",
            model_factory=lambda _variant, _offset: ReplayClient.from_jsonl(fixture),
        ).run(CaseStudyVariant.STANDARD, run_id="sdk-replayed")
    )
    assert replayed.final_answer == expected.final_answer, replayed.errors
    assert (
        replayed.usage.model_calls,
        replayed.usage.tool_calls,
        replayed.usage.total_tokens,
    ) == (
        expected.usage.model_calls,
        expected.usage.tool_calls,
        expected.usage.total_tokens,
    )


def test_shared_evaluation_harness_accepts_sdk(tmp_path: Path) -> None:
    implementation = OpenAIAgentsCaseStudy(output_root=tmp_path / "runs")

    async def run(variant: CaseStudyVariant, run_id: str) -> AgentState:
        return await implementation.run(variant, run_id=run_id)

    result = asyncio.run(
        ExperimentRunner(
            run,
            run_root=tmp_path / "runs",
            result_root=tmp_path / "evaluations",
        ).run(
            ExperimentConfig(
                experiment_id="sdk-evaluation",
                implementation="openai-agents-sdk",
                variants=tuple(CaseStudyVariant),
                task_specification_hash=case_study_hash(),
            )
        )
    )
    assert len(result.runs) == 4
    assert result.aggregate.task_completion_rate == 1.0
    assert result.aggregate.final_answer_valid_rate == 1.0
    assert result.aggregate.mean_model_calls == 3.0
    assert result.aggregate.mean_tool_calls == 2.25
    assert all(run.metrics.trajectory_valid for run in result.runs)


def test_manifest_and_state_contain_no_sdk_objects(tmp_path: Path) -> None:
    state = asyncio.run(
        OpenAIAgentsCaseStudy(output_root=tmp_path).run(
            CaseStudyVariant.STANDARD,
            run_id="sdk-manifest",
        )
    )
    manifest = json.loads((tmp_path / "sdk-manifest" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["dependencies"]["openai-agents"] == "0.17.8"
    assert manifest["task_specification_hash"] == case_study_hash()
    assert "openai_agents" not in state.model_dump_json().casefold()
    assert all(type(step).__module__.startswith("agentic_tutorial") for step in state.steps)


def _normalise_state(state: AgentState) -> object:
    def visit(value: object) -> object:
        if isinstance(value, dict):
            return {
                key: 0 if key in {"elapsed_ms", "elapsed_seconds"} else visit(item)
                for key, item in value.items()
                if key != "run_id"
            }
        if isinstance(value, list):
            return [visit(item) for item in value]
        if isinstance(value, str) and value.startswith(("{", "[")):
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                return value
            return json.dumps(visit(decoded), sort_keys=True, separators=(",", ":"))
        return value

    return visit(state.model_dump(mode="json"))
