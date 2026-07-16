"""Local human approval, interruption and controlled resumption example."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from agentic_tutorial.checkpoints import CheckpointStore, JsonCheckpointStore
from agentic_tutorial.schemas import (
    AgentError,
    AgentState,
    AgentStep,
    Budget,
    ErrorClass,
    FinishReason,
    HumanDecision,
    HumanDecisionType,
    Message,
    MessageRole,
    ModelResponse,
    StepStatus,
    TaskSpec,
    Termination,
    TerminationReason,
    TerminationStatus,
    ToolAction,
    ToolCall,
    ToolResult,
    ToolResultStatus,
    ToolSideEffect,
    Usage,
)
from agentic_tutorial.tools import ApprovalToken, ToolExecutor, ToolRegistry
from agentic_tutorial.tracing import TraceEventType, TraceWriter


def build_approval_executor(executed: list[str]) -> ToolExecutor:
    """Build a safe simulated consequential tool for one demonstration run."""
    registry = ToolRegistry()

    @registry.tool(side_effect=ToolSideEffect.SIDE_EFFECTING)
    def prepare_submission(title: str) -> dict[str, str]:
        """Prepare a local in-memory submission record."""
        executed.append(title)
        return {"status": "prepared", "title": title}

    return ToolExecutor(registry)


class ApprovalWorkflow:
    """Persist a proposed action, record a decision and resume exactly once."""

    def __init__(
        self,
        store: CheckpointStore,
        executor: ToolExecutor,
        trace: TraceWriter,
        *,
        budget: Budget | None = None,
    ) -> None:
        self.store = store
        self.executor = executor
        self.trace = trace
        self.budget = budget or Budget(max_steps=3)

    async def propose(self, *, run_id: str, title: str) -> AgentState:
        call = ToolCall(
            call_id=f"{run_id}-prepare",
            name="prepare_submission",
            arguments={"title": title},
        )
        response = ModelResponse(
            response_id=f"{run_id}-proposal",
            provider="deterministic-mock",
            model="approval-fixture-v1",
            message=Message(role=MessageRole.ASSISTANT, content="Approval is required."),
            tool_calls=(call,),
            structured_output={"action": ToolAction(tool_call=call).model_dump(mode="json")},
            usage=Usage(input_tokens=5, output_tokens=3, total_tokens=8, model_calls=1),
            finish_reason=FinishReason.TOOL_CALLS,
        )
        usage = Usage(input_tokens=5, output_tokens=3, total_tokens=8, model_calls=1)
        step = AgentStep(
            step_number=1,
            status=StepStatus.INTERRUPTED,
            action=ToolAction(tool_call=call),
            model_response=response,
            cumulative_usage=usage,
        )
        task = TaskSpec(task_id="approval-example", objective="Prepare a simulated submission.")
        state = AgentState(
            run_id=run_id,
            task=task,
            messages=(Message(role=MessageRole.USER, content=task.objective),),
            steps=(step,),
            usage=usage,
            budget=self.budget,
            pending_action=call,
            termination=Termination(
                status=TerminationStatus.INTERRUPTED,
                reason=TerminationReason.HUMAN_INTERRUPTION,
                message="Waiting for a human decision.",
                step_number=1,
            ),
        )
        self.trace.emit(TraceEventType.TOOL_REQUEST, {"tool_call": call.model_dump(mode="json")})
        self.trace.emit(TraceEventType.CHECKPOINT, {"step_number": 1, "pending": True})
        await self.store.save(state)
        return state

    async def decide(
        self,
        run_id: str,
        decision_type: HumanDecisionType,
        *,
        revised_title: str | None = None,
    ) -> AgentState:
        state = await self.store.load(run_id)
        if state is None or state.pending_action is None:
            raise ValueError("no pending action exists for this run")
        proposed = state.pending_action
        revised = None
        if decision_type is HumanDecisionType.REVISE:
            if revised_title is None:
                raise ValueError("revised_title is required")
            revised = ToolCall(
                call_id=f"{proposed.call_id}-revised",
                name=proposed.name,
                arguments={"title": revised_title},
            )
        decision = HumanDecision(
            decision=decision_type,
            proposed_call=proposed,
            revised_call=revised,
            rationale=f"Deterministic {decision_type.value} decision.",
        )
        self.trace.emit(
            TraceEventType.HUMAN_DECISION, {"decision": decision.model_dump(mode="json")}
        )
        if decision_type is HumanDecisionType.REQUEST_INFORMATION:
            updated = state.model_copy(
                update={"human_decisions": (*state.human_decisions, decision)}
            )
            await self.store.save(updated)
            return updated
        call = revised or proposed
        if decision_type is HumanDecisionType.REJECT:
            result = ToolResult(
                call_id=call.call_id,
                name=call.name,
                status=ToolResultStatus.DENIED,
                error=AgentError(
                    error_class=ErrorClass.TERMINAL,
                    code="human_rejected",
                    message="The proposed action was rejected.",
                    source="human",
                ),
            )
        else:
            result = await self.executor.execute(
                call,
                allowed_tools={call.name},
                approval=ApprovalToken.for_call(call),
            )
        self.trace.emit(TraceEventType.TOOL_RESULT, {"tool_result": result.model_dump(mode="json")})
        usage = state.usage.model_copy(
            update={
                "tool_calls": state.usage.tool_calls
                + int(decision_type is not HumanDecisionType.REJECT),
                "failures": state.usage.failures
                + int(result.status is not ToolResultStatus.SUCCESS),
            }
        )
        completed_step = state.steps[0].model_copy(
            update={
                "status": (
                    StepStatus.COMPLETED
                    if result.status is ToolResultStatus.SUCCESS
                    else StepStatus.FAILED
                ),
                "action": ToolAction(tool_call=call),
                "tool_result": result,
                "errors": (result.error,) if result.error else (),
                "cumulative_usage": usage,
            }
        )
        success = result.status is ToolResultStatus.SUCCESS
        updated = state.model_copy(
            update={
                "steps": (completed_step,),
                "usage": usage,
                "errors": (*state.errors, *((result.error,) if result.error else ())),
                "pending_action": None,
                "human_decisions": (*state.human_decisions, decision),
                "termination": Termination(
                    status=TerminationStatus.SUCCESS if success else TerminationStatus.FAILURE,
                    reason=TerminationReason.COMPLETED if success else TerminationReason.ERROR,
                    message="Approved action completed." if success else "Action did not execute.",
                    step_number=1,
                ),
            }
        )
        await self.store.save(updated)
        termination = updated.termination
        if termination is None:  # pragma: no cover - guarded by the construction above
            raise RuntimeError("resumed approval run has no termination")
        self.trace.emit(
            TraceEventType.TERMINATION,
            {"termination": termination.model_dump(mode="json")},
        )
        return updated


def run_approval_cli(decision: str | None, revised_title: str) -> int:
    """Run either interactively or with a deterministic command-line decision."""
    selected = decision or input("Decision [approve/reject/revise/request_information]: ").strip()
    decision_type = HumanDecisionType(selected)
    run_id = "approval-demo"
    directory = Path("outputs/runs") / run_id
    trace_path = directory / "trace.jsonl"
    trace_path.unlink(missing_ok=True)
    executed: list[str] = []
    workflow = ApprovalWorkflow(
        JsonCheckpointStore(directory / "checkpoints"),
        build_approval_executor(executed),
        TraceWriter(trace_path, run_id=run_id),
    )

    async def run() -> AgentState:
        await workflow.propose(run_id=run_id, title="Initial local submission")
        return await workflow.decide(
            run_id,
            decision_type,
            revised_title=revised_title if decision_type is HumanDecisionType.REVISE else None,
        )

    state = asyncio.run(run())
    print(
        json.dumps(
            {
                "decision": decision_type.value,
                "executed": executed,
                "termination": state.termination.status if state.termination else None,
            },
            sort_keys=True,
        )
    )
    return 0
