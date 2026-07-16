"""Versioned schemas shared by every provider and orchestration implementation."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, ClassVar, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

SCHEMA_VERSION: Literal["1"] = "1"


class CanonicalModel(BaseModel):
    """Base for strict, versioned canonical contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"] = SCHEMA_VERSION


class ToolSideEffect(StrEnum):
    """Operational effect classification used by shared permissions."""

    READ_ONLY = "read_only"
    SIMULATED = "simulated"
    SIDE_EFFECTING = "side_effecting"


class MessageRole(StrEnum):
    """Roles supported by the provider-independent message contract."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ActionType(StrEnum):
    """Actions that a model may request from an agent loop."""

    TOOL = "tool"
    FINISH = "finish"


class ErrorClass(StrEnum):
    """Recovery classifications required by the repository contract."""

    RETRYABLE = "retryable"
    RECOVERABLE = "recoverable_by_fallback"
    HUMAN_ESCALATION = "requires_human_escalation"
    TERMINAL = "terminal"


class ToolResultStatus(StrEnum):
    """Canonical tool execution outcomes."""

    SUCCESS = "success"
    ERROR = "error"
    DENIED = "denied"
    TIMEOUT = "timeout"


class FinishReason(StrEnum):
    """Provider-independent reasons for ending model generation."""

    STOP = "stop"
    TOOL_CALLS = "tool_calls"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"


class StepStatus(StrEnum):
    """Outcome of an individual agent step."""

    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class TerminationStatus(StrEnum):
    """Top-level outcome of a bounded run."""

    SUCCESS = "success"
    FAILURE = "failure"
    INTERRUPTED = "interrupted"


class TerminationReason(StrEnum):
    """Canonical reasons why execution stopped."""

    COMPLETED = "completed"
    MAX_MODEL_CALLS = "max_model_calls"
    MAX_STEPS = "max_steps"
    MAX_ELAPSED_TIME = "max_elapsed_time"
    MAX_TOKENS = "max_tokens"
    MAX_TOOL_CALLS = "max_tool_calls"
    MAX_FAILURES = "max_failures"
    MAX_COST = "max_cost"
    REPEATED_ACTION = "repeated_action"
    ERROR = "error"
    HUMAN_INTERRUPTION = "human_interruption"


class TaskSpec(CanonicalModel):
    """A stable task definition independent of models and frameworks."""

    task_id: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    instructions: tuple[str, ...] = ()
    success_criteria: tuple[str, ...] = ()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class Message(CanonicalModel):
    """A canonical conversational message."""

    role: MessageRole
    content: str
    name: str | None = None
    tool_call_id: str | None = None

    @model_validator(mode="after")
    def validate_tool_message(self) -> Message:
        if self.role is MessageRole.TOOL and not self.tool_call_id:
            raise ValueError("tool messages require tool_call_id")
        if self.role is not MessageRole.TOOL and self.tool_call_id is not None:
            raise ValueError("tool_call_id is valid only for tool messages")
        return self


class ToolDefinition(CanonicalModel):
    """A portable tool description using JSON Schema for arguments."""

    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    description: str = Field(min_length=1)
    parameters: dict[str, JsonValue]
    version: str = Field(default="1", min_length=1)
    side_effect: ToolSideEffect = ToolSideEffect.READ_ONLY


class ToolCall(CanonicalModel):
    """A validated request to invoke a named tool."""

    call_id: str = Field(min_length=1)
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    arguments: dict[str, JsonValue] = Field(default_factory=dict)


class AgentError(CanonicalModel):
    """A sanitised failure recorded in canonical state."""

    error_class: ErrorClass
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    source: str | None = None


class ToolResult(CanonicalModel):
    """A canonical tool result that never exposes implementation exceptions."""

    call_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: ToolResultStatus
    content: JsonValue = None
    elapsed_ms: int = Field(default=0, ge=0)
    error: AgentError | None = None

    @model_validator(mode="after")
    def validate_error_status(self) -> ToolResult:
        if self.status is ToolResultStatus.SUCCESS and self.error is not None:
            raise ValueError("successful tool results cannot contain an error")
        if self.status is not ToolResultStatus.SUCCESS and self.error is None:
            raise ValueError("non-successful tool results require an error")
        return self


class Usage(CanonicalModel):
    """Usage accounting; unavailable token fields are represented by ``None``."""

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    model_calls: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    elapsed_seconds: float = Field(default=0.0, ge=0)
    monetary_cost_usd: float | None = Field(default=None, ge=0)
    failures: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_token_total(self) -> Usage:
        if (
            self.input_tokens is not None
            and self.output_tokens is not None
            and self.total_tokens is not None
            and self.total_tokens != self.input_tokens + self.output_tokens
        ):
            raise ValueError("total_tokens must equal input_tokens plus output_tokens")
        return self


class ModelResponse(CanonicalModel):
    """A provider-normalised model response."""

    response_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    message: Message | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    structured_output: dict[str, JsonValue] | None = None
    usage: Usage = Field(default_factory=Usage)
    finish_reason: FinishReason

    @model_validator(mode="after")
    def validate_payload(self) -> ModelResponse:
        if self.message is None and not self.tool_calls and self.structured_output is None:
            raise ValueError("model responses require a message, tool call, or structured output")
        if self.finish_reason is FinishReason.TOOL_CALLS and not self.tool_calls:
            raise ValueError("tool_calls finish reason requires at least one tool call")
        return self


class ToolAction(CanonicalModel):
    """An action requesting environmental interaction."""

    action_type: Literal[ActionType.TOOL] = ActionType.TOOL
    tool_call: ToolCall


class FinishAction(CanonicalModel):
    """An action requesting successful completion."""

    action_type: Literal[ActionType.FINISH] = ActionType.FINISH
    answer: str = Field(min_length=1)


Action: TypeAlias = Annotated[ToolAction | FinishAction, Field(discriminator="action_type")]


class Budget(CanonicalModel):
    """Conservative finite limits applied to every iterative workflow."""

    max_model_calls: int = Field(default=10, gt=0)
    max_steps: int = Field(default=10, gt=0)
    max_elapsed_seconds: float = Field(default=300.0, gt=0)
    max_tokens: int = Field(default=100_000, gt=0)
    max_tool_calls: int = Field(default=20, gt=0)
    max_repeated_actions: int = Field(default=2, gt=0)
    max_failures: int = Field(default=3, gt=0)
    max_cost_usd: float | None = Field(default=None, gt=0)


class Termination(CanonicalModel):
    """An explicit terminal or interrupted run outcome."""

    status: TerminationStatus
    reason: TerminationReason
    message: str = Field(min_length=1)
    step_number: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_status_reason(self) -> Termination:
        if (
            self.status is TerminationStatus.SUCCESS
            and self.reason is not TerminationReason.COMPLETED
        ):
            raise ValueError("successful termination requires the completed reason")
        if (
            self.status is not TerminationStatus.SUCCESS
            and self.reason is TerminationReason.COMPLETED
        ):
            raise ValueError("completed termination requires success status")
        return self


class EvidenceItem(CanonicalModel):
    """A source-grounded item supporting a final answer."""

    source_id: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    excerpt: str | None = None


class FinalAnswer(CanonicalModel):
    """The common structured output returned by every implementation."""

    schema_id: ClassVar[str] = "agentic_tutorial.final_answer.v1"

    task_id: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    evidence: tuple[EvidenceItem, ...] = ()
    limitations: tuple[str, ...] = ()


class AgentStep(CanonicalModel):
    """One ordered transition in an agent trajectory."""

    step_number: int = Field(gt=0)
    status: StepStatus
    action: Action | None = None
    model_response: ModelResponse
    tool_result: ToolResult | None = None
    errors: tuple[AgentError, ...] = ()
    cumulative_usage: Usage = Field(default_factory=Usage)

    @model_validator(mode="after")
    def validate_action_result(self) -> AgentStep:
        if self.action is None and self.status is not StepStatus.FAILED:
            raise ValueError("only failed steps may omit an action")
        if isinstance(self.action, ToolAction) and self.tool_result is None:
            raise ValueError("tool actions require a tool result")
        if isinstance(self.action, FinishAction) and self.tool_result is not None:
            raise ValueError("finish actions cannot contain a tool result")
        return self


class AgentState(CanonicalModel):
    """Serializable run state with ordered steps and monotonic usage."""

    run_id: str = Field(min_length=1)
    task: TaskSpec
    messages: tuple[Message, ...] = ()
    steps: tuple[AgentStep, ...] = ()
    usage: Usage = Field(default_factory=Usage)
    errors: tuple[AgentError, ...] = ()
    budget: Budget = Field(default_factory=Budget)
    termination: Termination | None = None
    final_answer: FinalAnswer | None = None

    @model_validator(mode="after")
    def validate_trajectory(self) -> AgentState:
        expected_numbers = list(range(1, len(self.steps) + 1))
        actual_numbers = [step.step_number for step in self.steps]
        if actual_numbers != expected_numbers:
            raise ValueError("step numbers must be unique and consecutive from one")

        previous = Usage()
        for step in self.steps:
            if not _usage_is_monotonic(previous, step.cumulative_usage):
                raise ValueError("cumulative usage must be monotonic")
            previous = step.cumulative_usage
        if self.steps and not _usage_is_monotonic(self.steps[-1].cumulative_usage, self.usage):
            raise ValueError("state usage cannot be lower than final step cumulative usage")
        if not self.steps and self.usage != Usage():
            raise ValueError("state without steps cannot contain consumed usage")

        if self.final_answer is not None:
            if self.final_answer.task_id != self.task.task_id:
                raise ValueError("final answer task_id must match the state task")
            if self.termination is None or self.termination.status is not TerminationStatus.SUCCESS:
                raise ValueError("final answers require successful termination")
        if self.termination is not None and self.termination.step_number != len(self.steps):
            raise ValueError("termination step_number must match the trajectory length")
        return self


class EvaluationRecord(CanonicalModel):
    """Minimal canonical envelope for deterministic evaluation results."""

    run_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    implementation: str = Field(min_length=1)
    metrics: dict[str, int | float | bool | None] = Field(default_factory=dict)


def _usage_is_monotonic(previous: Usage, current: Usage) -> bool:
    for field in ("input_tokens", "output_tokens", "total_tokens"):
        old = getattr(previous, field)
        new = getattr(current, field)
        if old is not None and (new is None or new < old):
            return False
    if previous.monetary_cost_usd is not None and (
        current.monetary_cost_usd is None or current.monetary_cost_usd < previous.monetary_cost_usd
    ):
        return False
    return (
        current.model_calls >= previous.model_calls
        and current.tool_calls >= previous.tool_calls
        and current.elapsed_seconds >= previous.elapsed_seconds
        and current.failures >= previous.failures
    )
