"""Tests for T06 minimal framework-free agent execution."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from pydantic import BaseModel, JsonValue

from agentic_tutorial.execution import PlainPythonAgent, minimal_research_task
from agentic_tutorial.models import GenerationSettings, ModelCapabilities
from agentic_tutorial.schemas import (
    Budget,
    FinishReason,
    Message,
    MessageRole,
    ModelResponse,
    TerminationReason,
    ToolCall,
    ToolDefinition,
    Usage,
)
from agentic_tutorial.tools import ToolExecutor, build_tutorial_registry


class ScriptClient:
    """Small protocol client used to isolate loop mechanics."""

    provider = "test-script"
    model = "test-v1"
    capabilities = ModelCapabilities(structured_output=True, native_tool_calling=True)

    def __init__(self, responses: Sequence[ModelResponse]) -> None:
        self.responses = tuple(responses)
        self.index = 0

    async def generate(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolDefinition] = (),
        response_schema: type[BaseModel] | None = None,
        settings: GenerationSettings | None = None,
    ) -> ModelResponse:
        del messages, tools, response_schema, settings
        response = self.responses[self.index]
        self.index += 1
        return response


def _response(identifier: str, action: dict[str, JsonValue] | None) -> ModelResponse:
    tool_calls: tuple[ToolCall, ...] = ()
    finish_reason = FinishReason.STOP
    if action and action.get("action_type") == "tool":
        call = ToolCall.model_validate(action["tool_call"])
        tool_calls = (call,)
        finish_reason = FinishReason.TOOL_CALLS
    return ModelResponse(
        response_id=identifier,
        provider="test-script",
        model="test-v1",
        message=Message(role=MessageRole.ASSISTANT, content="canonical decision"),
        tool_calls=tool_calls,
        structured_output={"action": action} if action is not None else {"invalid": True},
        usage=Usage(input_tokens=4, output_tokens=2, total_tokens=6, model_calls=1),
        finish_reason=finish_reason,
    )


def _finish(identifier: str = "finish") -> ModelResponse:
    return _response(
        identifier, {"action_type": "finish", "answer": "Paper paper-001 is relevant."}
    )


def _search(identifier: str = "search") -> ModelResponse:
    return _response(
        identifier,
        {
            "action_type": "tool",
            "tool_call": {
                "call_id": "call-1",
                "name": "catalogue_search",
                "arguments": {"query": "agent evaluation"},
            },
        },
    )


def _agent(responses: Sequence[ModelResponse], budget: Budget | None = None) -> PlainPythonAgent:
    return PlainPythonAgent(
        ScriptClient(responses),
        ToolExecutor(build_tutorial_registry()),
        budget=budget,
        allowed_tools=("catalogue_search",),
    )


def test_successful_finish_loop() -> None:
    state = asyncio.run(_agent([_finish()]).run(minimal_research_task(), run_id="finish-run"))
    assert state.termination is not None
    assert state.termination.reason is TerminationReason.COMPLETED
    assert state.final_answer is not None


def test_successful_tool_use_then_finish() -> None:
    state = asyncio.run(
        _agent([_search(), _finish()]).run(minimal_research_task(), run_id="tool-run")
    )
    assert len(state.steps) == 2
    assert state.steps[0].tool_result is not None
    assert state.steps[0].tool_result.content == [
        {
            "paper_id": "paper-001",
            "title": "Evaluating Agent Trajectories",
            "topic": "agent evaluation",
        }
    ]
    assert state.usage.model_calls == 2 and state.usage.tool_calls == 1


def test_malformed_action_is_recorded_and_terminates() -> None:
    state = asyncio.run(
        _agent([_response("bad", None)]).run(minimal_research_task(), run_id="bad-run")
    )
    assert state.termination is not None and state.termination.reason is TerminationReason.ERROR
    assert state.steps[0].action is None
    assert state.errors[0].code == "malformed_action"


def test_repeated_action_terminates() -> None:
    state = asyncio.run(
        _agent([_search("one"), _search("two")]).run(minimal_research_task(), run_id="repeat-run")
    )
    assert state.termination is not None
    assert state.termination.reason is TerminationReason.REPEATED_ACTION


def test_maximum_step_termination() -> None:
    state = asyncio.run(
        _agent([_search()], Budget(max_steps=1)).run(minimal_research_task(), run_id="limited-run")
    )
    assert state.termination is not None
    assert state.termination.reason is TerminationReason.MAX_STEPS
