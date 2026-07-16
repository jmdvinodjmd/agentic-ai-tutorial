"""Central, versioned contract for the offline research-assistant case study."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from agentic_tutorial.schemas import Budget, TaskSpec, ToolSideEffect
from agentic_tutorial.tools import ToolRegistry

FIXTURE_ROOT = Path(__file__).parents[3] / "case_study" / "fixtures" / "v1"


class FixtureModel(BaseModel):
    """Strict immutable base for common case-study fixture records."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class CaseStudyVariant(StrEnum):
    STANDARD = "standard"
    INSUFFICIENT_EVIDENCE = "insufficient-evidence"
    CLARIFICATION_REQUIRED = "clarification-required"
    TOOL_FAILURE = "tool-failure"


class ExpectedOutcome(StrEnum):
    ANSWER = "answer"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CLARIFICATION = "clarification"
    RECOVERED_ANSWER = "recovered_answer"


class CatalogueEntry(FixtureModel):
    catalogue_version: Literal["1"] = "1"
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    year: int = Field(ge=1900, le=2100)
    topics: tuple[str, ...]
    abstract: str
    evidence_claim: str | None = None
    valid: bool = True
    conflicts_with: tuple[str, ...] = ()


class SafetyPolicy(FixtureModel):
    policy_version: Literal["1"] = "1"
    allowed_tools: tuple[str, ...]
    retrieved_content_is_untrusted: bool
    side_effects_permitted: bool
    require_source_provenance: bool


class EvaluationAnnotation(FixtureModel):
    expected_source_ids: tuple[str, ...]
    prohibited_source_ids: tuple[str, ...] = ()
    expected_outcome: ExpectedOutcome
    required_answer_terms: tuple[str, ...] = ()


class TaskVariant(FixtureModel):
    name: CaseStudyVariant
    question: str = Field(min_length=1)
    task: TaskSpec
    search_query: str
    annotation: EvaluationAnnotation
    expected_answer: str | None = None
    expected_limitations: tuple[str, ...] = ()
    inject_search_failures: int = Field(default=0, ge=0)


class CaseStudyDefinition(FixtureModel):
    specification_version: Literal["1"]
    dataset_version: Literal["1"]
    title: str
    system_prompt: str
    planning_prompt: str
    synthesis_prompt: str
    critique_prompt: str
    inclusion_criteria: tuple[str, ...]
    evidence_requirements: tuple[str, ...]
    stopping_rules: tuple[str, ...]
    budget: Budget
    safety: SafetyPolicy
    variants: tuple[TaskVariant, ...]
    dataset_licence_note: str

    def variant(self, name: CaseStudyVariant) -> TaskVariant:
        """Return one named task variant or fail explicitly."""
        for variant in self.variants:
            if variant.name is name:
                return variant
        raise ValueError(f"unknown case-study variant: {name}")


def load_definition(path: str | Path | None = None) -> CaseStudyDefinition:
    """Load and validate the common specification fixture."""
    target = Path(path) if path is not None else FIXTURE_ROOT / "specification.json"
    return CaseStudyDefinition.model_validate_json(target.read_text(encoding="utf-8"))


def load_catalogue(path: str | Path | None = None) -> tuple[CatalogueEntry, ...]:
    """Load the finite synthetic catalogue in stable source order."""
    target = Path(path) if path is not None else FIXTURE_ROOT / "catalogue.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    return tuple(CatalogueEntry.model_validate(item) for item in payload)


def case_study_hash(
    definition: CaseStudyDefinition | None = None,
    catalogue: tuple[CatalogueEntry, ...] | None = None,
) -> str:
    """Hash every common task input used for matched implementations."""
    specification = definition or load_definition()
    entries = catalogue or load_catalogue()
    payload = {
        "definition": specification.model_dump(mode="json"),
        "catalogue": [entry.model_dump(mode="json") for entry in entries],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_case_study_registry(
    *,
    catalogue: tuple[CatalogueEntry, ...] | None = None,
    fail_searches: int = 0,
) -> ToolRegistry:
    """Build shared deterministic read-only tools over the versioned catalogue."""
    entries = catalogue or load_catalogue()
    remaining_failures = fail_searches
    registry = ToolRegistry()

    @registry.tool(
        description="Search the versioned local research catalogue.",
        side_effect=ToolSideEffect.READ_ONLY,
    )
    def search_catalogue(query: str) -> list[dict[str, str | int | bool]]:
        nonlocal remaining_failures
        if remaining_failures:
            remaining_failures -= 1
            raise RuntimeError("controlled catalogue failure")
        terms = {term for term in query.casefold().split() if len(term) > 3}
        results: list[dict[str, str | int | bool]] = []
        for entry in entries:
            haystack = " ".join((entry.title, *entry.topics, entry.abstract)).casefold()
            score = sum(term.rstrip("?.,") in haystack for term in terms)
            if score:
                results.append(
                    {
                        "source_id": entry.source_id,
                        "title": entry.title,
                        "year": entry.year,
                        "score": score,
                        "valid": entry.valid,
                    }
                )
        return sorted(
            results,
            key=lambda item: (-cast(int, item["score"]), str(item["source_id"])),
        )

    @registry.tool(
        description="Extract structured claims from selected local catalogue sources.",
        side_effect=ToolSideEffect.READ_ONLY,
    )
    def extract_evidence(source_ids: list[str]) -> list[dict[str, str]]:
        selected = set(source_ids)
        return [
            {
                "source_id": entry.source_id,
                "claim": entry.evidence_claim,
                "excerpt": entry.abstract,
            }
            for entry in entries
            if entry.source_id in selected and entry.valid and entry.evidence_claim is not None
        ]

    @registry.tool(
        description="Critique a draft for known and explicit source provenance.",
        side_effect=ToolSideEffect.READ_ONLY,
    )
    def critique_draft(draft: str, source_ids: list[str]) -> dict[str, object]:
        known = {entry.source_id for entry in entries if entry.valid}
        unknown = sorted(set(source_ids) - known)
        missing_citations = sorted(source_id for source_id in source_ids if source_id not in draft)
        insufficient = "insufficient" in draft.casefold() and not source_ids
        return {
            "valid": (bool(source_ids) and not unknown and not missing_citations) or insufficient,
            "unknown_source_ids": unknown,
            "missing_citations": missing_citations,
        }

    return registry
