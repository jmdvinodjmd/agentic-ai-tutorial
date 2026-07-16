"""Focused tests for approval, interruption and controlled resumption."""

from __future__ import annotations

import asyncio
from pathlib import Path

from agentic_tutorial.checkpoints import JsonCheckpointStore
from agentic_tutorial.education.approval import (
    ApprovalWorkflow,
    build_approval_executor,
    run_approval_demo,
)
from agentic_tutorial.schemas import HumanDecisionType, TerminationStatus, ToolCall
from agentic_tutorial.tools import ApprovalToken
from agentic_tutorial.tracing import TraceEventType, TraceReader, TraceWriter


def _workflow(tmp_path: Path) -> tuple[ApprovalWorkflow, list[str], Path]:
    executed: list[str] = []
    trace_path = tmp_path / "trace.jsonl"
    return (
        ApprovalWorkflow(
            JsonCheckpointStore(tmp_path / "checkpoints"),
            build_approval_executor(executed),
            TraceWriter(trace_path, run_id="approval-test"),
        ),
        executed,
        trace_path,
    )


def test_approve_resumes_without_repeating_proposal(tmp_path: Path) -> None:
    workflow, executed, trace = _workflow(tmp_path)
    proposed = asyncio.run(workflow.propose(run_id="approval-test", title="Draft"))
    state = asyncio.run(workflow.decide("approval-test", HumanDecisionType.APPROVE))
    assert proposed.usage.model_calls == state.usage.model_calls == 1
    assert proposed.usage.total_tokens == state.usage.total_tokens == 8
    assert proposed.budget == state.budget
    assert len(state.steps) == 1
    assert executed == ["Draft"]
    assert state.pending_action is None
    assert state.termination is not None and state.termination.status is TerminationStatus.SUCCESS
    assert TraceEventType.HUMAN_DECISION in {
        event.event_type for event in TraceReader(trace).read()
    }


def test_reject_never_executes(tmp_path: Path) -> None:
    workflow, executed, _ = _workflow(tmp_path)
    asyncio.run(workflow.propose(run_id="approval-test", title="Draft"))
    state = asyncio.run(workflow.decide("approval-test", HumanDecisionType.REJECT))
    assert executed == []
    assert state.steps[0].tool_result is not None
    error = state.steps[0].tool_result.error
    assert error is not None and error.code == "human_rejected"


def test_approval_demo_runs_inside_an_event_loop() -> None:
    async def run() -> None:
        state, executed = await run_approval_demo("reject", "Unused revised title")
        assert executed == []
        assert state.termination is not None
        assert state.termination.status is TerminationStatus.FAILURE

    asyncio.run(run())


def test_revise_executes_only_revised_action(tmp_path: Path) -> None:
    workflow, executed, _ = _workflow(tmp_path)
    asyncio.run(workflow.propose(run_id="approval-test", title="Draft"))
    state = asyncio.run(
        workflow.decide("approval-test", HumanDecisionType.REVISE, revised_title="Checked revision")
    )
    assert executed == ["Checked revision"]
    assert state.human_decisions[0].revised_call is not None


def test_request_information_remains_interrupted(tmp_path: Path) -> None:
    workflow, executed, _ = _workflow(tmp_path)
    asyncio.run(workflow.propose(run_id="approval-test", title="Draft"))
    state = asyncio.run(workflow.decide("approval-test", HumanDecisionType.REQUEST_INFORMATION))
    assert executed == []
    assert state.pending_action is not None
    assert (
        state.termination is not None and state.termination.status is TerminationStatus.INTERRUPTED
    )


def test_approval_token_is_invalid_after_argument_change(tmp_path: Path) -> None:
    executed: list[str] = []
    executor = build_approval_executor(executed)
    proposed = ToolCall(call_id="call", name="prepare_submission", arguments={"title": "Original"})
    changed = proposed.model_copy(update={"arguments": {"title": "Changed"}})
    result = asyncio.run(executor.execute(changed, approval=ApprovalToken.for_call(proposed)))
    assert result.error is not None and result.error.code == "approval_required"
    assert executed == []
