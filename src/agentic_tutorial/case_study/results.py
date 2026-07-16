"""Shared final-answer assembly for every matched case-study implementation."""

from __future__ import annotations

from pydantic import TypeAdapter

from agentic_tutorial.case_study.specification import TaskVariant
from agentic_tutorial.schemas import AgentState, EvidenceItem, FinalAnswer


def finalise_case_study_state(state: AgentState, variant: TaskVariant) -> AgentState:
    """Attach canonical evidence and limitations to a successful model answer."""
    evidence: list[EvidenceItem] = []
    for step in state.steps:
        if step.tool_result is None or step.tool_result.name != "extract_evidence":
            continue
        records = TypeAdapter(list[dict[str, str]]).validate_python(step.tool_result.content)
        evidence.extend(EvidenceItem.model_validate(record) for record in records)
    answer = FinalAnswer(
        task_id=variant.task.task_id,
        answer=(
            state.final_answer.answer
            if state.final_answer is not None
            else variant.expected_answer or "No final answer is available."
        ),
        evidence=tuple(evidence),
        limitations=variant.expected_limitations,
    )
    return AgentState.model_validate(
        {**state.model_dump(mode="json"), "final_answer": answer.model_dump(mode="json")}
    )
