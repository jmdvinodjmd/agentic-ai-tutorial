"""Six compact execution-flow patterns over shared infrastructure."""

from __future__ import annotations

import asyncio
from pathlib import Path

from agentic_tutorial.budgets import BudgetManager
from agentic_tutorial.schemas import Budget, ToolCall
from agentic_tutorial.tools import ToolExecutor, build_tutorial_registry
from agentic_tutorial.tracing import TraceEventType, TraceWriter

PATTERN_NAMES = (
    "prompt-chaining",
    "routing-parallelisation",
    "react-tool-use",
    "planner-executor",
    "critic-reviser",
    "orchestrator-worker",
)


def run_pattern(name: str) -> dict[str, object]:
    return asyncio.run(run_pattern_async(name))


async def run_pattern_async(name: str) -> dict[str, object]:
    """Run one pattern inside an existing event loop."""
    runners = {
        "prompt-chaining": _prompt_chaining,
        "planner-executor": _planner_executor,
        "critic-reviser": _critic_reviser,
    }
    if name == "routing-parallelisation":
        result = await _routing_parallelisation()
    elif name == "react-tool-use":
        result = await _react()
    elif name == "orchestrator-worker":
        result = await _orchestrator_worker()
    else:
        try:
            result = runners[name]()
        except KeyError as error:
            raise ValueError(f"unknown pattern: {name}") from error
    trace_path = Path("outputs/runs") / f"pattern-{name}" / "trace.jsonl"
    trace_path.unlink(missing_ok=True)
    trace = TraceWriter(trace_path, run_id=f"pattern-{name}")
    trace.emit(TraceEventType.RUN_START, {"pattern": name})
    trace.emit(TraceEventType.DECISION, {"result": result})
    trace.emit(TraceEventType.TERMINATION, {"reason": "completed"})
    return result


def _prompt_chaining() -> dict[str, object]:
    extracted = "paper-001"
    checked = extracted if extracted.startswith("paper-") else "invalid"
    answer = f"Evidence source: {checked}"
    return {
        "pattern": "prompt chaining",
        "stages": [extracted, checked, answer],
        "limitation": "errors propagate",
    }


async def _routing_parallelisation() -> dict[str, object]:
    async def worker(label: str) -> str:
        await asyncio.sleep(0)
        return f"{label}:complete"

    async def run() -> list[str]:
        route = "evidence" if "paper" in "find paper evidence" else "general"
        results = await asyncio.gather(worker("metadata"), worker("claims"))
        return [route, *sorted(results)]

    return {
        "pattern": "routing and parallelisation",
        "ordered_results": await run(),
        "limitation": "incorrect routing selects the wrong workers",
    }


async def _react() -> dict[str, object]:
    call = ToolCall(
        call_id="react-search",
        name="catalogue_search",
        arguments={"query": "agent evaluation"},
    )
    result = await ToolExecutor(build_tutorial_registry()).execute(call)
    return {
        "pattern": "ReAct-style tool use",
        "trajectory": ["reason: search is needed", "act: catalogue_search", "observe: paper-001"],
        "success": result.content is not None,
        "limitation": "repeated actions require a circuit breaker",
    }


def _planner_executor() -> dict[str, object]:
    manager = BudgetManager(Budget(max_steps=3))
    plan = ("search", "extract", "synthesise")
    completed: list[str] = []
    for step in plan:
        if manager.check(steps=len(completed)) is not None:
            break
        completed.append(step)
    return {
        "pattern": "planner-executor",
        "plan": plan,
        "completed": completed,
        "limitation": "a poor plan constrains execution",
    }


def _critic_reviser() -> dict[str, object]:
    draft = "Paper paper-999 is relevant."
    revisions = 0
    for _ in range(2):
        if "paper-001" in draft:
            break
        draft = "Paper paper-001 is relevant."
        revisions += 1
    return {
        "pattern": "critic-reviser",
        "answer": draft,
        "revisions": revisions,
        "limitation": "critique can still accept a plausible error",
    }


async def _orchestrator_worker() -> dict[str, object]:
    registry = build_tutorial_registry()
    executor = ToolExecutor(registry)
    research = await executor.execute(
        ToolCall(
            call_id="research",
            name="catalogue_search",
            arguments={"query": "agent evaluation"},
        ),
        allowed_tools={"catalogue_search"},
    )
    analysis = await executor.execute(
        ToolCall(call_id="analysis", name="calculator_add", arguments={"left": 1, "right": 1}),
        allowed_tools={"calculator_add"},
    )
    return {
        "pattern": "orchestrator-worker",
        "researcher_output": research.content,
        "analyst_output": analysis.content,
        "separate_permissions": True,
        "limitation": "coordination adds calls and failure paths",
    }
