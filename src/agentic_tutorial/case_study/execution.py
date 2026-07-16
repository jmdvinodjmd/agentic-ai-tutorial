"""Framework-independent execution operations for matched case-study adapters."""

from __future__ import annotations

import json
from collections.abc import Sequence

from pydantic import ValidationError

from agentic_tutorial.budgets import BudgetManager
from agentic_tutorial.checkpoints import CheckpointStore
from agentic_tutorial.execution import AgentDecision
from agentic_tutorial.models import GenerationSettings, ModelClient, ModelProviderError
from agentic_tutorial.schemas import (
    AgentError,
    AgentState,
    AgentStep,
    ErrorClass,
    FinalAnswer,
    FinishAction,
    Message,
    MessageRole,
    ModelResponse,
    StepStatus,
    Termination,
    TerminationReason,
    TerminationStatus,
    ToolAction,
    ToolDefinition,
    ToolResult,
    ToolResultStatus,
)
from agentic_tutorial.tools import ToolExecutor
from agentic_tutorial.tracing import TraceEventType, TraceWriter


class CaseStudyExecution:
    """Execute one canonical decision at a time under shared controls."""

    def __init__(
        self,
        model: ModelClient,
        tools: ToolExecutor,
        *,
        allowed_tools: Sequence[str],
        checkpoint_store: CheckpointStore,
        trace_writer: TraceWriter,
        settings: GenerationSettings | None = None,
    ) -> None:
        self.model = model
        self.tools = tools
        self.allowed_tools = tuple(allowed_tools)
        self.checkpoint_store = checkpoint_store
        self.trace_writer = trace_writer
        self.settings = settings or GenerationSettings()

    def manager(self, state: AgentState) -> BudgetManager:
        return BudgetManager(
            state.budget,
            initial_usage=state.usage,
            initial_actions=tuple(step.action for step in state.steps if step.action is not None),
        )

    async def tool_step(self, state: AgentState, expected_tool: str) -> AgentState:
        """Request and safely execute exactly one specialist tool action."""
        if state.termination is not None:
            return state
        manager = self.manager(state)
        reason = manager.check(steps=len(state.steps))
        self.emit_budget(manager, len(state.steps))
        if reason is not None:
            return await self.fail(state, reason, manager)
        response_or_error = await self.model_call(state, manager)
        if isinstance(response_or_error, AgentError):
            return await self.error(state, response_or_error, manager)
        response = response_or_error
        try:
            decision = AgentDecision.model_validate(response.structured_output)
        except ValidationError:
            return await self.error(
                state,
                AgentError(
                    error_class=ErrorClass.RECOVERABLE,
                    code="malformed_action",
                    message="model response action failed canonical validation",
                    source=response.provider,
                ),
                manager,
                response=response,
            )
        self.trace_writer.emit(
            TraceEventType.DECISION,
            {"action": decision.action.model_dump(mode="json")},
        )
        repeated = manager.observe_action(decision.action)
        if repeated is not None:
            return await self.fail(state, repeated, manager)
        if (
            not isinstance(decision.action, ToolAction)
            or decision.action.tool_call.name != expected_tool
        ):
            return await self.error(
                state,
                AgentError(
                    error_class=ErrorClass.RECOVERABLE,
                    code="unexpected_specialist_action",
                    message=f"specialist requires tool {expected_tool!r}",
                    source="case_study_execution",
                ),
                manager,
                response=response,
            )
        reason = manager.check_before_tool()
        if reason is not None:
            return await self.fail(state, reason, manager)
        action = decision.action
        self.trace_writer.emit(
            TraceEventType.TOOL_REQUEST,
            {"tool_call": action.tool_call.model_dump(mode="json")},
        )
        result = await self.tools.execute(
            action.tool_call,
            allowed_tools=self.allowed_tools,
        )
        self.trace_writer.emit(
            TraceEventType.TOOL_RESULT,
            {"tool_result": result.model_dump(mode="json")},
        )
        manager.record_tool_result(result)
        errors = (result.error,) if result.error else ()
        if result.error is not None:
            self.trace_writer.emit(
                TraceEventType.ERROR,
                {"error": result.error.model_dump(mode="json")},
            )
        step = AgentStep(
            step_number=len(state.steps) + 1,
            status=(
                StepStatus.COMPLETED
                if result.status is ToolResultStatus.SUCCESS
                else StepStatus.FAILED
            ),
            action=action,
            model_response=response,
            tool_result=result,
            errors=errors,
            cumulative_usage=manager.usage,
        )
        state = state.model_copy(
            update={
                "messages": (
                    *state.messages,
                    Message(
                        role=MessageRole.TOOL,
                        content=json.dumps(_model_visible_tool_result(result), sort_keys=True),
                        name=result.name,
                        tool_call_id=result.call_id,
                    ),
                ),
                "steps": (*state.steps, step),
                "usage": manager.usage,
                "errors": (*state.errors, *errors),
            }
        )
        self.trace_writer.emit(
            TraceEventType.STATE_TRANSITION,
            {"step": step.model_dump(mode="json"), "usage": state.usage.model_dump(mode="json")},
        )
        self.emit_budget(manager, len(state.steps))
        return await self.save(state)

    async def finish_step(self, state: AgentState) -> AgentState:
        """Request exactly one canonical finish action."""
        if state.termination is not None:
            return state
        manager = self.manager(state)
        reason = manager.check(steps=len(state.steps))
        self.emit_budget(manager, len(state.steps))
        if reason is not None:
            return await self.fail(state, reason, manager)
        response_or_error = await self.model_call(state, manager)
        if isinstance(response_or_error, AgentError):
            return await self.error(state, response_or_error, manager)
        response = response_or_error
        try:
            decision = AgentDecision.model_validate(response.structured_output)
        except ValidationError:
            return await self.error(
                state,
                AgentError(
                    error_class=ErrorClass.RECOVERABLE,
                    code="malformed_action",
                    message="model response action failed canonical validation",
                    source=response.provider,
                ),
                manager,
                response=response,
            )
        self.trace_writer.emit(
            TraceEventType.DECISION,
            {"action": decision.action.model_dump(mode="json")},
        )
        repeated = manager.observe_action(decision.action)
        if repeated is not None:
            return await self.fail(state, repeated, manager)
        if not isinstance(decision.action, FinishAction):
            return await self.error(
                state,
                AgentError(
                    error_class=ErrorClass.RECOVERABLE,
                    code="unexpected_specialist_action",
                    message="coordinator requires a finish action",
                    source="case_study_execution",
                ),
                manager,
                response=response,
            )
        step_number = len(state.steps) + 1
        termination = Termination(
            status=TerminationStatus.SUCCESS,
            reason=TerminationReason.COMPLETED,
            message="The model returned a valid finish action.",
            step_number=step_number,
        )
        step = AgentStep(
            step_number=step_number,
            status=StepStatus.COMPLETED,
            action=decision.action,
            model_response=response,
            cumulative_usage=manager.usage,
        )
        state = state.model_copy(
            update={
                "steps": (*state.steps, step),
                "usage": manager.usage,
                "termination": termination,
                "final_answer": FinalAnswer(
                    task_id=state.task.task_id,
                    answer=decision.action.answer,
                ),
            }
        )
        self.trace_writer.emit(
            TraceEventType.STATE_TRANSITION,
            {"step": step.model_dump(mode="json"), "usage": state.usage.model_dump(mode="json")},
        )
        self.trace_writer.emit(
            TraceEventType.TERMINATION,
            {"termination": termination.model_dump(mode="json")},
        )
        return await self.save(state)

    async def model_call(
        self,
        state: AgentState,
        manager: BudgetManager,
    ) -> ModelResponse | AgentError:
        definitions = self.definitions()
        self.trace_writer.emit(
            TraceEventType.MODEL_REQUEST,
            {
                "messages": [message.model_dump(mode="json") for message in state.messages],
                "tools": [tool.model_dump(mode="json") for tool in definitions],
                "response_schema": AgentDecision.schema_id,
                "settings": self.settings.model_dump(mode="json"),
            },
        )
        try:
            response = await self.model.generate(
                state.messages,
                tools=definitions,
                response_schema=AgentDecision,
                settings=self.settings,
            )
        except ModelProviderError as error:
            manager.record_model_failure()
            canonical = error.as_agent_error()
            self.trace_writer.emit(
                TraceEventType.ERROR,
                {"error": canonical.model_dump(mode="json")},
            )
            return canonical
        manager.record_model_response(response)
        self.trace_writer.emit(
            TraceEventType.MODEL_RESPONSE,
            {"response": response.model_dump(mode="json")},
        )
        self.emit_budget(manager, len(state.steps))
        return response

    async def interrupt(self, state: AgentState, message: str) -> AgentState:
        termination = Termination(
            status=TerminationStatus.INTERRUPTED,
            reason=TerminationReason.HUMAN_INTERRUPTION,
            message=message,
            step_number=len(state.steps),
        )
        state = state.model_copy(update={"termination": termination})
        self.trace_writer.emit(
            TraceEventType.HUMAN_DECISION,
            {"decision": "interrupt", "tool_execution_permitted": False},
        )
        self.trace_writer.emit(
            TraceEventType.TERMINATION,
            {"termination": termination.model_dump(mode="json")},
        )
        return await self.save(state)

    async def save(self, state: AgentState) -> AgentState:
        await self.checkpoint_store.save(state)
        self.trace_writer.emit(
            TraceEventType.CHECKPOINT,
            {"run_id": state.run_id, "step_number": len(state.steps)},
        )
        return state

    async def error(
        self,
        state: AgentState,
        error: AgentError,
        manager: BudgetManager,
        *,
        response: ModelResponse | None = None,
    ) -> AgentState:
        steps = state.steps
        if response is not None:
            steps = (
                *steps,
                AgentStep(
                    step_number=len(steps) + 1,
                    status=StepStatus.FAILED,
                    model_response=response,
                    errors=(error,),
                    cumulative_usage=manager.usage,
                ),
            )
        state = state.model_copy(update={"steps": steps, "errors": (*state.errors, error)})
        return await self.fail(state, TerminationReason.ERROR, manager)

    async def fail(
        self,
        state: AgentState,
        reason: TerminationReason,
        manager: BudgetManager,
    ) -> AgentState:
        termination = Termination(
            status=TerminationStatus.FAILURE,
            reason=reason,
            message=f"Execution stopped: {reason.value}.",
            step_number=len(state.steps),
        )
        state = state.model_copy(update={"usage": manager.usage, "termination": termination})
        self.trace_writer.emit(
            TraceEventType.TERMINATION,
            {"termination": termination.model_dump(mode="json")},
        )
        return await self.save(state)

    def definitions(self) -> tuple[ToolDefinition, ...]:
        allowed = set(self.allowed_tools)
        return tuple(
            definition
            for definition in self.tools.registry.definitions()
            if definition.name in allowed
        )

    def emit_budget(self, manager: BudgetManager, steps: int) -> None:
        snapshot = manager.snapshot(steps=steps)
        self.trace_writer.emit(
            TraceEventType.BUDGET,
            {
                "configured": snapshot.budget.model_dump(mode="json"),
                "consumed": snapshot.consumed.model_dump(mode="json"),
                "remaining": {
                    "model_calls": snapshot.remaining_model_calls,
                    "steps": snapshot.remaining_steps,
                    "tool_calls": snapshot.remaining_tool_calls,
                    "tokens": snapshot.remaining_tokens,
                    "seconds": snapshot.remaining_seconds,
                    "failures": snapshot.remaining_failures,
                    "cost_usd": snapshot.remaining_cost_usd,
                },
            },
        )


def _model_visible_tool_result(result: ToolResult) -> dict[str, object]:
    """Remove runtime timing noise from model context and strict replay keys."""
    payload: dict[str, object] = result.model_dump(mode="json")
    payload["elapsed_ms"] = 0
    return payload
