"""Small structured decisions shared by model qualification probes."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import Field

from agentic_tutorial.schemas.models import CanonicalModel


class RouteDecision(CanonicalModel):
    schema_id: ClassVar[str] = "agentic_tutorial.qualification.route.v1"

    route: Literal["research", "data_analysis", "service", "clarify"]
    reason: str = Field(min_length=1)


class PlanStep(CanonicalModel):
    step_id: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    depends_on: tuple[str, ...] = ()


class PlanDecision(CanonicalModel):
    schema_id: ClassVar[str] = "agentic_tutorial.qualification.plan.v1"

    steps: tuple[PlanStep, ...] = Field(min_length=1)


class CriticDecision(CanonicalModel):
    schema_id: ClassVar[str] = "agentic_tutorial.qualification.critic.v1"

    accepted: bool
    issues: tuple[str, ...] = ()


class StopDecision(CanonicalModel):
    schema_id: ClassVar[str] = "agentic_tutorial.qualification.stop.v1"

    should_stop: bool
    reason: Literal["criteria_met", "insufficient_evidence", "budget_exhausted", "continue"]


class RecoveryDecision(CanonicalModel):
    schema_id: ClassVar[str] = "agentic_tutorial.qualification.recovery.v1"

    action: Literal["retry", "fallback", "escalate"]
    reason: str = Field(min_length=1)
