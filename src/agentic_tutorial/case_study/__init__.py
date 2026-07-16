"""Versioned common case-study specification and plain-Python baseline."""

from agentic_tutorial.case_study.offline import (
    CaseStudyModelFactory,
    build_offline_case_study_model,
)
from agentic_tutorial.case_study.specification import (
    CASE_STUDY_PLAN,
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
    "CASE_STUDY_PLAN",
    "CaseStudyDefinition",
    "CaseStudyModelFactory",
    "CaseStudyVariant",
    "CatalogueEntry",
    "ExpectedOutcome",
    "TaskVariant",
    "build_case_study_registry",
    "build_offline_case_study_model",
    "case_study_hash",
    "load_catalogue",
    "load_definition",
]
