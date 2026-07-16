"""Small deterministic read-only tools used by later examples."""

from __future__ import annotations

from agentic_tutorial.schemas import ToolSideEffect
from agentic_tutorial.tools.registry import ToolRegistry

PAPERS = (
    {
        "paper_id": "paper-001",
        "title": "Evaluating Agent Trajectories",
        "topic": "agent evaluation",
    },
    {"paper_id": "paper-002", "title": "Deterministic Workflow Testing", "topic": "testing"},
)


def build_tutorial_registry() -> ToolRegistry:
    """Build a fresh registry containing deterministic read-only tools."""
    registry = ToolRegistry()

    @registry.tool(description="Add two numbers.", side_effect=ToolSideEffect.READ_ONLY)
    def calculator_add(left: float, right: float) -> float:
        return left + right

    @registry.tool(
        description="Search the fixed tutorial paper catalogue.",
        side_effect=ToolSideEffect.READ_ONLY,
    )
    def catalogue_search(query: str) -> list[dict[str, str]]:
        normalised = query.casefold()
        return [
            paper
            for paper in PAPERS
            if normalised in f"{paper['title']} {paper['topic']}".casefold()
        ]

    return registry
