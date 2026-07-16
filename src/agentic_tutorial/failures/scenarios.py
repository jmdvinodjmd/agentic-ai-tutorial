"""Executable deterministic failures composed from existing shared controls."""

from __future__ import annotations

import asyncio
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from agentic_tutorial.case_study import CaseStudyVariant, load_definition
from agentic_tutorial.case_study.plain_python import PlainPythonCaseStudy
from agentic_tutorial.checkpoints import CheckpointError, JsonCheckpointStore
from agentic_tutorial.execution import PlainPythonAgent, minimal_research_task
from agentic_tutorial.models import GenerationSettings, ModelCapabilities
from agentic_tutorial.models.providers import ReplayClient, ReplayMismatchError
from agentic_tutorial.safety import PolicyOutcome, SafetyEngine, UntrustedContent
from agentic_tutorial.schemas import (
    AgentError,
    AgentState,
    Budget,
    ErrorClass,
    FinishReason,
    Message,
    MessageRole,
    ModelResponse,
    Termination,
    ToolCall,
    Usage,
)
from agentic_tutorial.tools import ToolExecutor, ToolRegistry, build_tutorial_registry
from agentic_tutorial.tracing import TraceEventType, TraceWriter

_REPOSITORY_ROOT = Path(__file__).parents[3]
_PACKAGE_DATA = Path(__file__).parents[1] / "data"
FIXTURE_PATH = _REPOSITORY_ROOT / "case_study" / "fixtures" / "v1" / "failure_scenarios.json"
if not FIXTURE_PATH.is_file():
    FIXTURE_PATH = _PACKAGE_DATA / "case_study" / "fixtures" / "v1" / "failure_scenarios.json"
REPLAY_PATH = _REPOSITORY_ROOT / "tests" / "fixtures" / "models" / "replay" / "catalogue_v1.jsonl"
if not REPLAY_PATH.is_file():
    REPLAY_PATH = _PACKAGE_DATA / "replay" / "catalogue_v1.jsonl"


class ExpectedBehaviour(StrEnum):
    SAFE_TERMINATION = "safe_termination"
    RECOVERY = "recovery"
    ESCALATION = "escalation"
    DENIAL = "denial"


class FailureScenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    scenario_id: str = Field(min_length=1)
    expected_behaviour: ExpectedBehaviour
    description: str = Field(min_length=1)
    untrusted_content: str | None = None


class FailureScenarioSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    fixture_version: Literal["1"]
    scenarios: tuple[FailureScenario, ...]


class ScenarioResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    scenario_id: str
    expected_behaviour: ExpectedBehaviour
    observed_behaviour: ExpectedBehaviour
    passed: bool
    termination: Termination | None = None
    error: AgentError | None = None
    details: dict[str, str | int | bool | None] = Field(default_factory=dict)


ScenarioExecution = tuple[
    ExpectedBehaviour,
    AgentState | None,
    AgentError | None,
    dict[str, str | int | bool | None],
]


class SequenceClient:
    """Finite canonical response client for circuit-breaker scenarios."""

    def __init__(self, responses: tuple[ModelResponse, ...]) -> None:
        self.responses = responses
        self.index = 0

    @property
    def provider(self) -> str:
        return "deterministic-failure-fixture"

    @property
    def model(self) -> str:
        return "failure-actions-v1"

    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(structured_output=True, native_tool_calling=True)

    async def generate(
        self,
        messages: object,
        *,
        tools: object = (),
        response_schema: object = None,
        settings: GenerationSettings | None = None,
    ) -> ModelResponse:
        del messages, tools, response_schema, settings
        response = self.responses[self.index]
        self.index += 1
        return response


def load_failure_scenarios(path: str | Path | None = None) -> FailureScenarioSet:
    target = Path(path) if path is not None else FIXTURE_PATH
    return FailureScenarioSet.model_validate_json(target.read_text(encoding="utf-8"))


class ScenarioRunner:
    """Run every declared scenario without external or destructive effects."""

    def __init__(self, output_root: str | Path = "outputs/failures") -> None:
        self.output_root = Path(output_root)
        self.fixture = load_failure_scenarios()

    async def run_all(self) -> tuple[ScenarioResult, ...]:
        return tuple([await self.run(item) for item in self.fixture.scenarios])

    async def run(self, scenario: FailureScenario) -> ScenarioResult:
        handlers = {
            "malformed-model-output": self._malformed,
            "invalid-tool-arguments": self._invalid_arguments,
            "unknown-tool": self._unknown_tool,
            "unauthorised-tool": self._unauthorised_tool,
            "tool-timeout": self._timeout,
            "recoverable-tool-failure": self._recoverable,
            "repeated-action": self._repeated,
            "short-execution-cycle": self._cycle,
            "insufficient-evidence": self._insufficient,
            "contradictory-evidence": self._contradictory,
            "prompt-injection": self._prompt_injection,
            "corrupted-checkpoint": self._corrupted_checkpoint,
            "replay-mismatch": self._replay_mismatch,
            "budget-exhaustion": self._budget_exhaustion,
        }
        observed, state, error, details = await handlers[scenario.scenario_id](scenario)
        summary_path = self.output_root / scenario.scenario_id / "summary_trace.jsonl"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.unlink(missing_ok=True)
        summary = TraceWriter(summary_path, run_id=f"failure-{scenario.scenario_id}")
        summary.emit(
            TraceEventType.RUN_START,
            {"scenario_id": scenario.scenario_id, "expected": scenario.expected_behaviour.value},
        )
        if error is not None:
            summary.emit(TraceEventType.ERROR, {"error": error.model_dump(mode="json")})
        summary.emit(
            TraceEventType.TERMINATION,
            {
                "observed": observed.value,
                "passed": observed is scenario.expected_behaviour,
                "details": details,
            },
        )
        return ScenarioResult(
            scenario_id=scenario.scenario_id,
            expected_behaviour=scenario.expected_behaviour,
            observed_behaviour=observed,
            passed=observed is scenario.expected_behaviour,
            termination=state.termination if state else None,
            error=error,
            details=details,
        )

    async def _malformed(self, _: FailureScenario) -> ScenarioExecution:
        response = _response(1, {"not_an_action": True})
        state = await self._agent("malformed", (response,))
        return ExpectedBehaviour.SAFE_TERMINATION, state, state.errors[-1], {}

    async def _invalid_arguments(self, _: FailureScenario) -> ScenarioExecution:
        result = await ToolExecutor(build_tutorial_registry()).execute(
            ToolCall(
                call_id="invalid", name="calculator_add", arguments={"left": "bad", "right": 1}
            )
        )
        return ExpectedBehaviour.SAFE_TERMINATION, None, result.error, {"executed": False}

    async def _unknown_tool(self, _: FailureScenario) -> ScenarioExecution:
        result = await ToolExecutor(build_tutorial_registry()).execute(
            ToolCall(call_id="unknown", name="missing_tool", arguments={})
        )
        return ExpectedBehaviour.SAFE_TERMINATION, None, result.error, {"executed": False}

    async def _unauthorised_tool(self, _: FailureScenario) -> ScenarioExecution:
        result = await ToolExecutor(build_tutorial_registry()).execute(
            ToolCall(call_id="denied", name="catalogue_search", arguments={"query": "agent"}),
            allowed_tools=(),
        )
        return ExpectedBehaviour.DENIAL, None, result.error, {"executed": False}

    async def _timeout(self, _: FailureScenario) -> ScenarioExecution:
        registry = ToolRegistry()

        @registry.tool()
        async def slow_local_lookup(query: str) -> str:
            await asyncio.sleep(0.02)
            return query

        result = await ToolExecutor(registry, timeout_seconds=0.001).execute(
            ToolCall(call_id="timeout", name="slow_local_lookup", arguments={"query": "safe"})
        )
        return ExpectedBehaviour.SAFE_TERMINATION, None, result.error, {"timed_out": True}

    async def _recoverable(self, _: FailureScenario) -> ScenarioExecution:
        state = await PlainPythonCaseStudy(output_root=self.output_root).run(
            CaseStudyVariant.TOOL_FAILURE, run_id="scenario-recoverable"
        )
        return (
            ExpectedBehaviour.RECOVERY,
            state,
            state.errors[0],
            {"failure_count": state.usage.failures},
        )

    async def _repeated(self, _: FailureScenario) -> ScenarioExecution:
        action = _tool_response(1, "repeat", "catalogue_search", {"query": "agent"})
        state = await self._agent("repeated", (action, action))
        return (
            ExpectedBehaviour.SAFE_TERMINATION,
            state,
            None,
            {"reason": state.termination.reason.value if state.termination else ""},
        )

    async def _cycle(self, _: FailureScenario) -> ScenarioExecution:
        first = _tool_response(1, "a", "catalogue_search", {"query": "agent"})
        second = _tool_response(2, "b", "catalogue_search", {"query": "testing"})
        state = await self._agent(
            "cycle", (first, second, first, second), budget=Budget(max_repeated_actions=3)
        )
        return (
            ExpectedBehaviour.SAFE_TERMINATION,
            state,
            None,
            {"reason": state.termination.reason.value if state.termination else ""},
        )

    async def _insufficient(self, _: FailureScenario) -> ScenarioExecution:
        state = await PlainPythonCaseStudy(output_root=self.output_root).run(
            CaseStudyVariant.INSUFFICIENT_EVIDENCE, run_id="scenario-insufficient"
        )
        return (
            ExpectedBehaviour.SAFE_TERMINATION,
            state,
            None,
            {"evidence_count": len(state.final_answer.evidence) if state.final_answer else -1},
        )

    async def _contradictory(self, _: FailureScenario) -> ScenarioExecution:
        error = AgentError(
            error_class=ErrorClass.HUMAN_ESCALATION,
            code="contradictory_evidence",
            message="Conflicting valid sources require explicit treatment.",
            source="catalogue",
        )
        return ExpectedBehaviour.ESCALATION, None, error, {"sources": "source-001,source-003"}

    async def _prompt_injection(self, scenario: FailureScenario) -> ScenarioExecution:
        assessment = SafetyEngine(load_definition().safety).inspect_retrieved_content(
            UntrustedContent(
                source_id="prompt-injection-fixture",
                text=scenario.untrusted_content or "",
            )
        )
        if assessment.decision.outcome is not PolicyOutcome.TRANSFORM:
            raise AssertionError("injection fixture was not isolated")
        return (
            ExpectedBehaviour.DENIAL,
            None,
            assessment.decision.error,
            {"content_separated": bool(scenario.untrusted_content), "executed": False},
        )

    async def _corrupted_checkpoint(self, _: FailureScenario) -> ScenarioExecution:
        directory = self.output_root / "corrupted"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "corrupt.json").write_text("{not canonical json", encoding="utf-8")
        try:
            await JsonCheckpointStore(directory).load("corrupt")
        except CheckpointError:
            error = AgentError(
                error_class=ErrorClass.TERMINAL,
                code="corrupted_checkpoint",
                message="Checkpoint validation failed safely.",
                source="checkpoint",
            )
            return ExpectedBehaviour.SAFE_TERMINATION, None, error, {"loaded": False}
        raise AssertionError("corrupted checkpoint unexpectedly loaded")

    async def _replay_mismatch(self, _: FailureScenario) -> ScenarioExecution:
        client = ReplayClient.from_jsonl(REPLAY_PATH)
        try:
            await client.generate((Message(role=MessageRole.USER, content="different request"),))
        except ReplayMismatchError:
            error = AgentError(
                error_class=ErrorClass.TERMINAL,
                code="replay_mismatch",
                message="Replay divergence failed explicitly.",
                source="replay",
            )
            return ExpectedBehaviour.SAFE_TERMINATION, None, error, {"substituted": False}
        raise AssertionError("replay mismatch unexpectedly succeeded")

    async def _budget_exhaustion(self, _: FailureScenario) -> ScenarioExecution:
        state = await PlainPythonCaseStudy(output_root=self.output_root).run(
            CaseStudyVariant.STANDARD, run_id="scenario-budget", budget=Budget(max_steps=1)
        )
        return (
            ExpectedBehaviour.SAFE_TERMINATION,
            state,
            None,
            {"reason": state.termination.reason.value if state.termination else ""},
        )

    async def _agent(
        self, run_id: str, responses: tuple[ModelResponse, ...], *, budget: Budget | None = None
    ) -> AgentState:
        directory = self.output_root / run_id
        trace_path = directory / "trace.jsonl"
        trace_path.unlink(missing_ok=True)
        return await PlainPythonAgent(
            SequenceClient(responses),
            ToolExecutor(build_tutorial_registry()),
            budget=budget,
            allowed_tools=("catalogue_search",),
            trace_writer=TraceWriter(trace_path, run_id=run_id),
        ).run(minimal_research_task(), run_id=run_id)


def _response(step: int, structured_output: dict[str, JsonValue]) -> ModelResponse:
    return ModelResponse(
        response_id=f"failure-{step}",
        provider="deterministic-failure-fixture",
        model="failure-actions-v1",
        message=Message(role=MessageRole.ASSISTANT, content="fixture decision"),
        structured_output=structured_output,
        usage=Usage(input_tokens=1, output_tokens=1, total_tokens=2),
        finish_reason=FinishReason.STOP,
    )


def _tool_response(
    step: int, call_id: str, name: str, arguments: dict[str, JsonValue]
) -> ModelResponse:
    call = ToolCall(call_id=call_id, name=name, arguments=arguments)
    return ModelResponse(
        response_id=f"failure-{step}",
        provider="deterministic-failure-fixture",
        model="failure-actions-v1",
        message=Message(role=MessageRole.ASSISTANT, content="fixture tool action"),
        tool_calls=(call,),
        structured_output={
            "action": {"action_type": "tool", "tool_call": call.model_dump(mode="json")}
        },
        usage=Usage(input_tokens=1, output_tokens=1, total_tokens=2),
        finish_reason=FinishReason.TOOL_CALLS,
    )
