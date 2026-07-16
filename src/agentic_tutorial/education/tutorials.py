"""Progressive component demonstrations with one conceptual change each."""

from __future__ import annotations

import asyncio
from pathlib import Path

from agentic_tutorial.budgets import BudgetManager
from agentic_tutorial.models import DeterministicMockClient
from agentic_tutorial.models.providers.fixtures import FixtureProvenance, ScriptedScenarioFixture
from agentic_tutorial.schemas import (
    AgentState,
    Budget,
    FinishReason,
    Message,
    MessageRole,
    ModelResponse,
    TaskSpec,
    ToolCall,
    Usage,
)
from agentic_tutorial.tools import ToolExecutor, build_tutorial_registry
from agentic_tutorial.tracing import TraceEventType, TraceReader, TraceWriter, normalise_events

TUTORIAL_NAMES = (
    "basic-model",
    "tool-use",
    "explicit-state",
    "planning",
    "retained-context",
    "critique-validation",
    "bounded-tracing",
)


def run_tutorial(name: str) -> dict[str, object]:
    """Run one named deterministic tutorial."""
    runners = {
        "basic-model": _basic_model,
        "tool-use": _tool_use,
        "explicit-state": _explicit_state,
        "planning": _planning,
        "retained-context": _retained_context,
        "critique-validation": _critique_validation,
        "bounded-tracing": _bounded_tracing,
    }
    try:
        return runners[name]()
    except KeyError as error:
        raise ValueError(f"unknown tutorial: {name}") from error


def _basic_model() -> dict[str, object]:
    response = ModelResponse(
        response_id="basic-1",
        provider="deterministic-mock",
        model="education-v1",
        message=Message(role=MessageRole.ASSISTANT, content="Paper paper-001 is relevant."),
        usage=Usage(input_tokens=4, output_tokens=3, total_tokens=7, model_calls=1),
        finish_reason=FinishReason.STOP,
    )
    client = DeterministicMockClient(
        ScriptedScenarioFixture(
            fixture_version="1",
            scenario="basic-model",
            provenance=FixtureProvenance(
                source="public deterministic example",
                description="One canonical offline response.",
                recorded_by="Agentic AI Tutorial maintainers",
            ),
            responses=(response,),
        )
    )
    result = asyncio.run(client.generate([Message(role=MessageRole.USER, content="Find evidence")]))
    return {
        "concept": "model invocation",
        "answer": result.message.content if result.message else "",
    }


def _tool_use() -> dict[str, object]:
    result = asyncio.run(
        ToolExecutor(build_tutorial_registry()).execute(
            ToolCall(
                call_id="tutorial-call",
                name="catalogue_search",
                arguments={"query": "agent evaluation"},
            )
        )
    )
    return {"concept": "tool use", "result": result.content}


def _explicit_state() -> dict[str, object]:
    task = TaskSpec(task_id="state-example", objective="Retain explicit execution state.")
    state = AgentState(
        run_id="state-example-run",
        task=task,
        messages=(Message(role=MessageRole.USER, content=task.objective),),
    )
    return {
        "concept": "explicit state",
        "run_id": state.run_id,
        "message_count": len(state.messages),
    }


def _planning() -> dict[str, object]:
    plan = ("search local catalogue", "inspect evidence", "write concise answer")
    return {"concept": "planning", "plan": plan, "bounded_steps": len(plan)}


def _retained_context() -> dict[str, object]:
    messages = (
        Message(role=MessageRole.USER, content="Remember paper-001."),
        Message(role=MessageRole.ASSISTANT, content="Retained paper-001."),
        Message(role=MessageRole.USER, content="Which paper was retained?"),
    )
    return {"concept": "retained context", "answer": "paper-001", "message_count": len(messages)}


def _critique_validation() -> dict[str, object]:
    draft = "Paper paper-999 is relevant."
    valid = "paper-001" in draft
    revised = draft if valid else "Paper paper-001 is relevant."
    return {"concept": "critique and validation", "valid_initially": valid, "revised": revised}


def _bounded_tracing() -> dict[str, object]:
    path = Path("outputs/runs/tutorial-bounded/trace.jsonl")
    path.unlink(missing_ok=True)
    writer = TraceWriter(path, run_id="tutorial-bounded")
    manager = BudgetManager(Budget(max_steps=2))
    writer.emit(TraceEventType.RUN_START, {"budget": manager.budget.model_dump(mode="json")})
    writer.emit(TraceEventType.BUDGET, {"consumed": manager.usage.model_dump(mode="json")})
    writer.emit(TraceEventType.TERMINATION, {"reason": "completed"})
    events = TraceReader(path).read()
    return {
        "concept": "bounded execution and tracing",
        "event_types": [event.event_type.value for event in events],
        "deterministic_trace_bytes": len(normalise_events(events)),
    }
