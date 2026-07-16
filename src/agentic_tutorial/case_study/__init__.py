"""Versioned common case-study specification and plain-Python baseline."""

from agentic_tutorial.case_study.specification import (
    CaseStudyDefinition,
    CaseStudyVariant,
    CatalogueEntry,
    ExpectedOutcome,
    TaskVariant,
    build_case_study_registry,
    case_study_hash,
    load_catalogue,
    load_definition,
)

__all__ = [
    "CaseStudyDefinition",
    "CaseStudyVariant",
    "CatalogueEntry",
    "ExpectedOutcome",
    "TaskVariant",
    "build_case_study_registry",
    "case_study_hash",
    "load_catalogue",
    "load_definition",
]
