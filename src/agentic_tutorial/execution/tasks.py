"""Narrow deterministic task specifications for execution-foundation tests."""

from agentic_tutorial.schemas import TaskSpec


def minimal_research_task() -> TaskSpec:
    """Return the small local-catalogue task used by the reference loop."""
    return TaskSpec(
        task_id="minimal-research-001",
        objective="Identify the local catalogue paper about agent evaluation.",
        instructions=("Use only the deterministic local catalogue.",),
        success_criteria=("Name the relevant paper identifier.",),
        metadata={"fixture_version": "1"},
    )
