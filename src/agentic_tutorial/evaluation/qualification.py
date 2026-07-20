"""Provider-independent model qualification used before notebook execution."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence

from pydantic import BaseModel, ConfigDict, Field

from agentic_tutorial.models import InvalidModelResponseError, ModelClient
from agentic_tutorial.schemas import (
    CriticDecision,
    Message,
    MessageRole,
    PlanDecision,
    RecoveryDecision,
    RouteDecision,
    StopDecision,
    ToolDefinition,
)


class QualificationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class QualificationCheck(QualificationModel):
    name: str = Field(min_length=1)
    passed: bool
    detail: str = Field(min_length=1)


class QualificationReport(QualificationModel):
    provider: str
    model: str
    checks: tuple[QualificationCheck, ...]
    required_passes: int = 8

    @property
    def passed_count(self) -> int:
        return sum(check.passed for check in self.checks)

    @property
    def qualified(self) -> bool:
        return (
            len(self.checks) == self.required_passes and self.passed_count == self.required_passes
        )


class ModelCandidate(QualificationModel):
    model: str
    parameter_count_billions: float = Field(gt=0)
    metadata_path: str


async def qualify_model(client: ModelClient) -> QualificationReport:
    """Run the eight required probes against one fresh client instance."""

    checks: list[QualificationCheck] = []
    route = await _structured(
        client,
        "Route a request to synthesise household food-waste evidence.",
        RouteDecision,
    )
    checks.append(_check("schema_valid", route is not None, "route output satisfies its schema"))
    checks.append(
        _check(
            "routing",
            isinstance(route, RouteDecision) and route.route == "research",
            "food-waste evidence requests route to research",
        )
    )

    search = ToolDefinition(
        name="search_catalogue",
        description="Search the bounded evidence catalogue.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 5},
            },
            "required": ["query", "max_results"],
            "additionalProperties": False,
        },
    )
    tool_response = await client.generate(
        [_user("Select the catalogue search tool for household food-waste interventions.")],
        tools=[search],
    )
    call = tool_response.tool_calls[0] if len(tool_response.tool_calls) == 1 else None
    checks.append(
        _check(
            "tool_selection", call is not None and call.name == search.name, "search tool selected"
        )
    )
    query = call.arguments.get("query") if call else None
    max_results = call.arguments.get("max_results") if call else None
    arguments_valid = (
        isinstance(query, str)
        and bool(query.strip())
        and isinstance(max_results, int)
        and not isinstance(max_results, bool)
        and 1 <= max_results <= 5
    )
    checks.append(
        _check("tool_arguments", arguments_valid, "tool arguments satisfy semantic limits")
    )

    plan = await _structured(
        client,
        "Plan search, evidence validation, then synthesis; preserve dependencies.",
        PlanDecision,
    )
    checks.append(
        _check(
            "planning",
            isinstance(plan, PlanDecision) and _valid_plan(plan),
            "plan is ordered and dependency-valid",
        )
    )

    critic = await _structured(
        client,
        "Critique this unsupported answer and reject it: 'All interventions always work.'",
        CriticDecision,
    )
    checks.append(
        _check(
            "critic",
            isinstance(critic, CriticDecision) and not critic.accepted and bool(critic.issues),
            "unsupported answer is rejected with an issue",
        )
    )

    stop = await _structured(
        client,
        "Evidence and citations are validated. Decide whether execution should stop.",
        StopDecision,
    )
    checks.append(
        _check(
            "stopping",
            isinstance(stop, StopDecision) and stop.should_stop and stop.reason == "criteria_met",
            "validated completion stops explicitly",
        )
    )

    malformed_detected = False
    try:
        await client.generate(
            [_user("Recover after a malformed structured model response.")],
            response_schema=RecoveryDecision,
        )
    except InvalidModelResponseError:
        malformed_detected = True
    recovered = await _structured(
        client,
        "The previous response was malformed. Select a bounded recovery action.",
        RecoveryDecision,
    )
    checks.append(
        _check(
            "malformed_recovery",
            malformed_detected
            and isinstance(recovered, RecoveryDecision)
            and recovered.action == "retry",
            "malformed output is rejected then retried",
        )
    )

    return QualificationReport(provider=client.provider, model=client.model, checks=tuple(checks))


async def select_first_qualified(
    candidates: Sequence[ModelCandidate],
    client_factory: Callable[[ModelCandidate], Awaitable[ModelClient]],
) -> tuple[ModelCandidate | None, tuple[QualificationReport, ...]]:
    """Test candidates from smallest to largest and stop on the first 8/8 pass."""

    reports: list[QualificationReport] = []
    for candidate in sorted(candidates, key=lambda item: item.parameter_count_billions):
        client = await client_factory(candidate)
        report = await qualify_model(client)
        reports.append(report)
        if report.qualified:
            return candidate, tuple(reports)
    return None, tuple(reports)


async def _structured(
    client: ModelClient,
    prompt: str,
    schema: type[BaseModel],
) -> BaseModel | None:
    try:
        response = await client.generate([_user(prompt)], response_schema=schema)
        if response.structured_output is None:
            return None
        return schema.model_validate(response.structured_output)
    except InvalidModelResponseError:
        return None


def _valid_plan(plan: PlanDecision) -> bool:
    completed: set[str] = set()
    for step in plan.steps:
        if step.step_id in completed or not set(step.depends_on).issubset(completed):
            return False
        completed.add(step.step_id)
    return len(completed) >= 3


def _user(content: str) -> Message:
    return Message(role=MessageRole.USER, content=content)


def _check(name: str, passed: bool, detail: str) -> QualificationCheck:
    return QualificationCheck(name=name, passed=passed, detail=detail)
