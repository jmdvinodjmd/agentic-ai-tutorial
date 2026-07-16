"""Shared deterministic model fixture construction for matched implementations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter

from agentic_tutorial.case_study.specification import FIXTURE_ROOT, CaseStudyVariant
from agentic_tutorial.models.interface import ModelClient
from agentic_tutorial.models.providers import DeterministicMockClient
from agentic_tutorial.models.providers.fixtures import FixtureProvenance, ScriptedScenarioFixture
from agentic_tutorial.schemas import (
    FinishReason,
    Message,
    MessageRole,
    ModelResponse,
    ToolCall,
    Usage,
)


class ScriptedToolAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    action_type: Literal["tool"]
    call_id: str
    name: str
    arguments: dict[str, JsonValue]


class ScriptedFinishAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    action_type: Literal["finish"]
    answer: str


ScriptedAction = Annotated[
    ScriptedToolAction | ScriptedFinishAction, Field(discriminator="action_type")
]
CaseStudyModelFactory = Callable[[CaseStudyVariant, int], ModelClient]


class ModelScripts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    fixture_version: Literal["1"]
    standard: tuple[ScriptedAction, ...]
    insufficient_evidence: tuple[ScriptedAction, ...] = Field(alias="insufficient-evidence")
    clarification_required: tuple[ScriptedAction, ...] = Field(alias="clarification-required")
    tool_failure: tuple[ScriptedAction, ...] = Field(alias="tool-failure")

    def for_variant(self, variant: CaseStudyVariant) -> tuple[ScriptedAction, ...]:
        return {
            CaseStudyVariant.STANDARD: self.standard,
            CaseStudyVariant.INSUFFICIENT_EVIDENCE: self.insufficient_evidence,
            CaseStudyVariant.CLARIFICATION_REQUIRED: self.clarification_required,
            CaseStudyVariant.TOOL_FAILURE: self.tool_failure,
        }[variant]


def load_model_scripts() -> ModelScripts:
    return ModelScripts.model_validate_json(
        (FIXTURE_ROOT / "model_scripts.json").read_text(encoding="utf-8")
    )


def build_offline_case_study_model(
    variant: CaseStudyVariant,
    offset: int = 0,
) -> DeterministicMockClient:
    actions = load_model_scripts().for_variant(variant)[offset:]
    responses = tuple(
        _response(variant, index + offset + 1, action) for index, action in enumerate(actions)
    )
    return DeterministicMockClient(
        ScriptedScenarioFixture(
            fixture_version="1",
            scenario=f"case-study-{variant.value}-v1",
            provenance=FixtureProvenance(
                source="case_study/fixtures/v1/model_scripts.json",
                description="Deterministic actions for the common case study.",
                recorded_by="repository maintainers",
            ),
            responses=responses,
        )
    )


def _response(variant: CaseStudyVariant, step: int, action: ScriptedAction) -> ModelResponse:
    calls: tuple[ToolCall, ...]
    if isinstance(action, ScriptedToolAction):
        call = ToolCall(call_id=action.call_id, name=action.name, arguments=action.arguments)
        structured = TypeAdapter(dict[str, JsonValue]).validate_python(
            {"action": {"action_type": "tool", "tool_call": call.model_dump(mode="json")}}
        )
        calls = (call,)
        finish_reason = FinishReason.TOOL_CALLS
    else:
        structured = TypeAdapter(dict[str, JsonValue]).validate_python(
            {"action": {"action_type": "finish", "answer": action.answer}}
        )
        calls = ()
        finish_reason = FinishReason.STOP
    return ModelResponse(
        response_id=f"{variant.value}-response-{step}",
        provider="deterministic-mock",
        model="case-study-script-v1",
        message=Message(role=MessageRole.ASSISTANT, content=f"Completed decision {step}."),
        tool_calls=calls,
        structured_output=structured,
        usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15),
        finish_reason=finish_reason,
    )
