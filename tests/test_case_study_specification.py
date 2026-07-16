"""Integrity tests for the common versioned research-assistant task."""

from agentic_tutorial.case_study import (
    CaseStudyVariant,
    build_case_study_registry,
    case_study_hash,
    load_catalogue,
    load_definition,
)


def test_catalogue_is_versioned_synthetic_and_contains_edge_cases() -> None:
    catalogue = load_catalogue()
    assert len({entry.source_id for entry in catalogue}) == len(catalogue)
    assert {entry.catalogue_version for entry in catalogue} == {"1"}
    assert any(not entry.valid for entry in catalogue)
    assert any(entry.conflicts_with for entry in catalogue)
    assert load_definition().dataset_licence_note


def test_ground_truth_references_known_sources_only() -> None:
    definition = load_definition()
    known = {entry.source_id for entry in load_catalogue()}
    for variant in definition.variants:
        assert set(variant.annotation.expected_source_ids) <= known
        assert set(variant.annotation.prohibited_source_ids) <= known
        assert not (
            set(variant.annotation.expected_source_ids)
            & set(variant.annotation.prohibited_source_ids)
        )


def test_all_variants_and_common_tool_definitions_load() -> None:
    definition = load_definition()
    assert {variant.name for variant in definition.variants} == set(CaseStudyVariant)
    definitions = build_case_study_registry().definitions()
    assert tuple(item.name for item in definitions) == tuple(
        sorted(definition.safety.allowed_tools)
    )
    assert all(item.side_effect.value == "read_only" for item in definitions)
    assert case_study_hash() == case_study_hash(definition, load_catalogue())
