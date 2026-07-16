"""Minimal transparent sense-decide-act-observe loop."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, ValidationError

from agentic_tutorial.budgets import BudgetManager
from agentic_tutorial.checkpoints import CheckpointStore
from agentic_tutorial.models import GenerationSettings, ModelClient, ModelProviderError
from agentic_tutorial.schemas import (
    Action,
    AgentError,
    AgentState,
    AgentStep,
    Budget,
    ErrorClass,
    FinalAnswer,
    FinishAction,
    Message,
    MessageRole,
    ModelResponse,
    StepStatus,
    TaskSpec,
    Termination,
    TerminationReason,
    TerminationStatus,
    ToolAction,
    ToolDefinition,
    ToolResultStatus,
    Usage,
)
from agentic_tutorial.tools import ToolExecutor
from agentic_tutorial.tracing import TraceEventType, TraceWriter


class AgentDecision(BaseModel):
    """Stable structured-output envelope containing one canonical action."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_id: ClassVar[str] = "agentic_tutorial.agent_decision.v1"
    action: Action


class PlainPythonAgent:
    """Reference loop governed solely by the shared budget manager."""

    def __init__(
        self,
        model: ModelClient,
        tools: ToolExecutor,
        *,
        budget: Budget | None = None,
        allowed_tools: Sequence[str] | None = None,
        settings: GenerationSettings | None = None,
        checkpoint_store: CheckpointStore | None = None,
        trace_writer: TraceWriter | None = None,
    ) -> None:
        self.model = model
        self.tools = tools
        self.budget = budget or Budget()
        self.allowed_tools = tuple(allowed_tools) if allowed_tools is not None else None
        self.settings = settings or GenerationSettings()
        self.checkpoint_store = checkpoint_store
        self.trace_writer = trace_writer

    async def run(
        self,
        task: TaskSpec,
        *,
        run_id: str,
        initial_state: AgentState | None = None,
        resume: bool = False,
        interrupt_after_steps: int | None = None,
    ) -> AgentState:
        """Run until an explicit success, failure, interruption or budget condition."""
        loaded = (
            await self.checkpoint_store.load(run_id) if resume and self.checkpoint_store else None
        )
        state = initial_state or loaded or self._initial_state(task, run_id)
        if state.run_id != run_id or state.task != task or state.budget != self.budget:
            raise ValueError("initial state does not match run_id, task and budget")
        if resume and state.termination is not None:
            if state.termination.status is not TerminationStatus.INTERRUPTED:
                raise ValueError("only interrupted checkpoints may be resumed")
            state = state.model_copy(update={"termination": None})
        manager = BudgetManager(
            self.budget,
            initial_usage=state.usage,
            initial_actions=tuple(step.action for step in state.steps if step.action is not None),
        )
        self._emit(
            TraceEventType.RUN_START,
            {"task": task.model_dump(mode="json"), "budget": self.budget.model_dump(mode="json")},
        )

        for _ in range(len(state.steps), self.budget.max_steps + 1):
            reason = manager.check(steps=len(state.steps))
            self._emit_budget(manager, len(state.steps))
            if reason is not None:
                return await self._save(_terminate(state, reason, manager.usage))
            try:
                self._emit(
                    TraceEventType.MODEL_REQUEST,
                    {
                        "messages": [message.model_dump(mode="json") for message in state.messages],
                        "tools": [tool.model_dump(mode="json") for tool in self._definitions()],
                        "response_schema": AgentDecision.schema_id,
                        "settings": self.settings.model_dump(mode="json"),
                    },
                )
                response = await self.model.generate(
                    state.messages,
                    tools=self._definitions(),
                    response_schema=AgentDecision,
                    settings=self.settings,
                )
            except ModelProviderError as error:
                manager.record_model_failure()
                self._emit(
                    TraceEventType.ERROR, {"error": error.as_agent_error().model_dump(mode="json")}
                )
                failed = state.model_copy(
                    update={"errors": (*state.errors, error.as_agent_error())}
                )
                return await self._save(_terminate(failed, TerminationReason.ERROR, manager.usage))
            manager.record_model_response(response)
            self._emit(
                TraceEventType.MODEL_RESPONSE, {"response": response.model_dump(mode="json")}
            )
            self._emit_budget(manager, len(state.steps))
            reason = manager.check_post_action()
            if reason is not None:
                return await self._save(_terminate(state, reason, manager.usage))
            decision = _parse_decision(response)
            if isinstance(decision, AgentError):
                self._emit(TraceEventType.ERROR, {"error": decision.model_dump(mode="json")})
                state = _append_failed_decision(state, response, decision, manager.usage)
                self._emit_state(state)
                return await self._save(_terminate(state, TerminationReason.ERROR, manager.usage))

            reason = manager.observe_action(decision.action)
            self._emit(TraceEventType.DECISION, {"action": decision.action.model_dump(mode="json")})
            if reason is not None:
                return await self._save(_terminate(state, reason, manager.usage))
            if isinstance(decision.action, FinishAction):
                state = _append_finish(state, response, decision.action, manager.usage)
                self._emit_state(state)
                return await self._save(state)

            reason = manager.check_before_tool()
            if reason is not None:
                return await self._save(_terminate(state, reason, manager.usage))
            state = await self._execute_tool(state, response, decision.action, manager)
            await self._save(state)
            reason = manager.check_post_action()
            if reason is not None:
                return await self._save(_terminate(state, reason, manager.usage))
            if interrupt_after_steps is not None and len(state.steps) >= interrupt_after_steps:
                return await self._save(_interrupt(state, manager.usage))

        raise RuntimeError("bounded loop exited without an explicit termination")

    def _initial_state(self, task: TaskSpec, run_id: str) -> AgentState:
        return AgentState(
            run_id=run_id,
            task=task,
            messages=(Message(role=MessageRole.USER, content=task.objective),),
            budget=self.budget,
        )

    async def _save(self, state: AgentState) -> AgentState:
        if self.checkpoint_store is not None:
            await self.checkpoint_store.save(state)
            self._emit(
                TraceEventType.CHECKPOINT,
                {"run_id": state.run_id, "step_number": len(state.steps)},
            )
        if state.termination is not None:
            self._emit(
                TraceEventType.TERMINATION,
                {"termination": state.termination.model_dump(mode="json")},
            )
        return state

    def _emit(self, event_type: TraceEventType, payload: dict[str, object]) -> None:
        if self.trace_writer is not None:
            self.trace_writer.emit(event_type, payload)

    def _emit_budget(self, manager: BudgetManager, steps: int) -> None:
        snapshot = manager.snapshot(steps=steps)
        self._emit(
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

    def _emit_state(self, state: AgentState) -> None:
        self._emit(
            TraceEventType.STATE_TRANSITION,
            {
                "step": state.steps[-1].model_dump(mode="json"),
                "usage": state.usage.model_dump(mode="json"),
            },
        )

    def _definitions(self) -> tuple[ToolDefinition, ...]:
        definitions = self.tools.registry.definitions()
        if self.allowed_tools is None:
            return definitions
        allowed = set(self.allowed_tools)
        return tuple(definition for definition in definitions if definition.name in allowed)

    async def _execute_tool(
        self,
        state: AgentState,
        response: ModelResponse,
        action: ToolAction,
        manager: BudgetManager,
    ) -> AgentState:
        self._emit(
            TraceEventType.TOOL_REQUEST, {"tool_call": action.tool_call.model_dump(mode="json")}
        )
        result = await self.tools.execute(action.tool_call, allowed_tools=self.allowed_tools)
        self._emit(TraceEventType.TOOL_RESULT, {"tool_result": result.model_dump(mode="json")})
        if result.error is not None:
            self._emit(TraceEventType.ERROR, {"error": result.error.model_dump(mode="json")})
        manager.record_tool_result(result)
        self._emit_budget(manager, len(state.steps))
        usage = manager.usage
        errors = (result.error,) if result.error else ()
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
            cumulative_usage=usage,
        )
        tool_message = Message(
            role=MessageRole.TOOL,
            content=json.dumps(result.model_dump(mode="json"), sort_keys=True),
            name=result.name,
            tool_call_id=result.call_id,
        )
        updated = state.model_copy(
            update={
                "messages": (*state.messages, tool_message),
                "steps": (*state.steps, step),
                "usage": usage,
                "errors": (*state.errors, *errors),
            }
        )
        self._emit_state(updated)
        return updated


def _parse_decision(response: ModelResponse) -> AgentDecision | AgentError:
    try:
        return AgentDecision.model_validate(response.structured_output)
    except ValidationError:
        return AgentError(
            error_class=ErrorClass.RECOVERABLE,
            code="malformed_action",
            message="model response action failed canonical validation",
            source=response.provider,
        )


def _append_failed_decision(
    state: AgentState, response: ModelResponse, error: AgentError, usage: Usage
) -> AgentState:
    step = AgentStep(
        step_number=len(state.steps) + 1,
        status=StepStatus.FAILED,
        model_response=response,
        errors=(error,),
        cumulative_usage=usage,
    )
    return state.model_copy(
        update={
            "steps": (*state.steps, step),
            "usage": usage,
            "errors": (*state.errors, error),
        }
    )


def _append_finish(
    state: AgentState, response: ModelResponse, action: FinishAction, usage: Usage
) -> AgentState:
    step_number = len(state.steps) + 1
    step = AgentStep(
        step_number=step_number,
        status=StepStatus.COMPLETED,
        action=action,
        model_response=response,
        cumulative_usage=usage,
    )
    return state.model_copy(
        update={
            "steps": (*state.steps, step),
            "usage": usage,
            "termination": Termination(
                status=TerminationStatus.SUCCESS,
                reason=TerminationReason.COMPLETED,
                message="The model returned a valid finish action.",
                step_number=step_number,
            ),
            "final_answer": FinalAnswer(task_id=state.task.task_id, answer=action.answer),
        }
    )


def _terminate(state: AgentState, reason: TerminationReason, usage: Usage) -> AgentState:
    return state.model_copy(
        update={
            "usage": usage,
            "termination": Termination(
                status=TerminationStatus.FAILURE,
                reason=reason,
                message=f"Execution stopped: {reason.value}.",
                step_number=len(state.steps),
            ),
        }
    )


def _interrupt(state: AgentState, usage: Usage) -> AgentState:
    return state.model_copy(
        update={
            "usage": usage,
            "termination": Termination(
                status=TerminationStatus.INTERRUPTED,
                reason=TerminationReason.HUMAN_INTERRUPTION,
                message="Execution deliberately interrupted after a completed step.",
                step_number=len(state.steps),
            ),
        }
    )
