"""Framework-independent policy decisions over canonical actions and outputs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Collection
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agentic_tutorial.schemas import (
    AgentError,
    ErrorClass,
    FinalAnswer,
    ToolCall,
    ToolDefinition,
    ToolResult,
    ToolResultStatus,
    ToolSideEffect,
)
from agentic_tutorial.tools.registry import ToolRegistry
from agentic_tutorial.tools.runtime import ApprovalToken, ToolExecutor
from agentic_tutorial.tracing import TraceEventType, TraceWriter


class SafetyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PolicyOutcome(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    TRANSFORM = "transform"
    ESCALATE = "escalate"


class SafetyPolicy(SafetyModel):
    policy_version: str = Field(default="1", min_length=1)
    allowed_tools: tuple[str, ...] = ()
    retrieved_content_is_untrusted: bool = True
    side_effects_permitted: bool = False
    require_source_provenance: bool = True
    enforce_execution_budgets: bool = True
    injection_indicators: tuple[str, ...] = (
        "ignore previous",
        "ignore the task",
        "system message",
        "call filesystem",
        "reveal secret",
    )


class PolicyDecision(SafetyModel):
    policy_version: str
    outcome: PolicyOutcome
    reason: str = Field(min_length=1)
    tool_call: ToolCall | None = None
    error: AgentError | None = None


class UntrustedContent(SafetyModel):
    source_id: str = Field(min_length=1)
    text: str


class ContentAssessment(SafetyModel):
    content: UntrustedContent
    decision: PolicyDecision
    indicators: tuple[str, ...] = ()


def policy_hash(policy: SafetyPolicy) -> str:
    encoded = json.dumps(
        policy.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


class SafetyEngine:
    """Issue auditable deterministic decisions without executing actions."""

    def __init__(self, policy: SafetyPolicy, *, trace_writer: TraceWriter | None = None) -> None:
        self.policy = policy
        self.trace_writer = trace_writer

    def evaluate_tool(
        self,
        call: ToolCall,
        definition: ToolDefinition | None,
        arguments_model: type[BaseModel] | None,
        *,
        approval: ApprovalToken | None = None,
        allowed_tools: Collection[str] | None = None,
    ) -> PolicyDecision:
        effective = set(self.policy.allowed_tools)
        if allowed_tools is not None:
            effective &= set(allowed_tools)
        if definition is None or arguments_model is None:
            return self._decision(
                PolicyOutcome.DENY,
                "Tool is not registered.",
                call,
                "unknown_tool",
                ErrorClass.TERMINAL,
            )
        if call.name not in effective:
            return self._decision(
                PolicyOutcome.DENY,
                "Tool is outside the effective allowlist.",
                call,
                "unauthorised_tool",
                ErrorClass.TERMINAL,
            )
        try:
            arguments_model.model_validate(call.arguments)
        except ValidationError:
            return self._decision(
                PolicyOutcome.DENY,
                "Tool arguments failed canonical validation.",
                call,
                "invalid_tool_arguments",
                ErrorClass.TERMINAL,
            )
        if definition.side_effect is ToolSideEffect.SIDE_EFFECTING:
            if not self.policy.side_effects_permitted:
                return self._decision(
                    PolicyOutcome.DENY,
                    "Policy prohibits side-effecting tools.",
                    call,
                    "side_effect_prohibited",
                    ErrorClass.TERMINAL,
                )
            if approval is None or not approval.matches(call):
                return self._decision(
                    PolicyOutcome.REQUIRE_APPROVAL,
                    "An exact-action approval token is required.",
                    call,
                    "approval_required",
                    ErrorClass.HUMAN_ESCALATION,
                )
        return self._decision(PolicyOutcome.ALLOW, "Tool action satisfies policy.", call)

    def inspect_retrieved_content(self, content: UntrustedContent) -> ContentAssessment:
        normalised = content.text.casefold()
        indicators = tuple(
            indicator for indicator in self.policy.injection_indicators if indicator in normalised
        )
        if indicators:
            decision = self._decision(
                PolicyOutcome.TRANSFORM,
                "Potential instructions remain isolated as untrusted data.",
                error_code="untrusted_instruction_detected",
                error_class=ErrorClass.RECOVERABLE,
            )
        else:
            decision = self._decision(
                PolicyOutcome.ALLOW, "Retrieved content remains isolated as untrusted data."
            )
        return ContentAssessment(content=content, decision=decision, indicators=indicators)

    def validate_output(
        self, answer: FinalAnswer, *, allowed_source_ids: Collection[str]
    ) -> PolicyDecision:
        evidence_ids = [item.source_id for item in answer.evidence]
        unknown = set(evidence_ids) - set(allowed_source_ids)
        if unknown or len(evidence_ids) != len(set(evidence_ids)):
            return self._decision(
                PolicyOutcome.DENY,
                "Final answer contains unknown or duplicated evidence provenance.",
                error_code="invalid_evidence_provenance",
                error_class=ErrorClass.TERMINAL,
            )
        if self.policy.require_source_provenance and not answer.evidence:
            return self._decision(
                PolicyOutcome.ESCALATE,
                "Evidence provenance is required for a substantive answer.",
                error_code="missing_evidence_provenance",
                error_class=ErrorClass.HUMAN_ESCALATION,
            )
        return self._decision(PolicyOutcome.ALLOW, "Final answer satisfies output policy.")

    def _decision(
        self,
        outcome: PolicyOutcome,
        reason: str,
        call: ToolCall | None = None,
        error_code: str | None = None,
        error_class: ErrorClass = ErrorClass.TERMINAL,
    ) -> PolicyDecision:
        error = (
            AgentError(
                error_class=error_class,
                code=error_code,
                message=reason,
                source="safety_policy",
            )
            if error_code
            else None
        )
        decision = PolicyDecision(
            policy_version=self.policy.policy_version,
            outcome=outcome,
            reason=reason,
            tool_call=call,
            error=error,
        )
        if self.trace_writer is not None:
            self.trace_writer.emit(
                TraceEventType.POLICY_DECISION,
                {"decision": decision.model_dump(mode="json")},
            )
        return decision


class PolicyToolExecutor(ToolExecutor):
    """Apply one shared policy before delegating to the canonical executor."""

    def __init__(
        self,
        registry: ToolRegistry,
        engine: SafetyEngine,
        *,
        timeout_seconds: float = 10.0,
    ) -> None:
        super().__init__(registry, timeout_seconds=timeout_seconds)
        self.engine = engine

    async def execute(
        self,
        call: ToolCall,
        *,
        allowed_tools: Collection[str] | None = None,
        approval: ApprovalToken | None = None,
    ) -> ToolResult:
        registered = self.registry.get(call.name)
        decision = self.engine.evaluate_tool(
            call,
            registered.definition if registered else None,
            registered.arguments_model if registered else None,
            approval=approval,
            allowed_tools=allowed_tools,
        )
        if decision.outcome is not PolicyOutcome.ALLOW:
            error = decision.error or AgentError(
                error_class=ErrorClass.TERMINAL,
                code="policy_denied",
                message=decision.reason,
                source="safety_policy",
            )
            return ToolResult(
                call_id=call.call_id,
                name=call.name,
                status=ToolResultStatus.DENIED,
                error=error,
            )
        return await super().execute(call, allowed_tools=allowed_tools, approval=approval)
