"""Small deterministic read-only tools used by later examples."""

from __future__ import annotations

from agentic_tutorial.schemas import ToolSideEffect
from agentic_tutorial.tools.registry import ToolRegistry

EVIDENCE_RECORDS = (
    {
        "source_id": "food-waste-001",
        "title": "Plate-size intervention trial",
        "topic": "household food waste smaller plates",
    },
    {
        "source_id": "food-waste-002",
        "title": "Household meal-planning study",
        "topic": "household food waste meal planning",
    },
)


def build_tutorial_registry() -> ToolRegistry:
    """Build a fresh registry containing deterministic read-only tools."""
    registry = ToolRegistry()

    @registry.tool(description="Add two numbers.", side_effect=ToolSideEffect.READ_ONLY)
    def calculator_add(left: float, right: float) -> float:
        return left + right

    @registry.tool(
        description="Search the fixed household-food-waste evidence catalogue.",
        side_effect=ToolSideEffect.READ_ONLY,
    )
    def catalogue_search(query: str) -> list[dict[str, str]]:
        normalised = query.casefold()
        return [
            record
            for record in EVIDENCE_RECORDS
            if normalised in f"{record['title']} {record['topic']}".casefold()
        ]

    return registry
