"""Canonical experiment and evaluation records shared by all implementations."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from agentic_tutorial.case_study import CaseStudyVariant


class EvaluationModel(BaseModel):
    """Strict, immutable base for versioned evaluation artefacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    evaluation_schema_version: Literal["1"] = "1"


class ExperimentConfig(EvaluationModel):
    """Matched inputs for deterministic repeated implementation runs."""

    experiment_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    implementation: str = Field(min_length=1)
    variants: tuple[CaseStudyVariant, ...]
    repetitions: int = Field(default=1, gt=0, le=100)
    task_specification_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_metadata: dict[str, JsonValue] = Field(default_factory=dict)
    local_model_metadata: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def validate_variants(self) -> ExperimentConfig:
        if not self.variants or len(set(self.variants)) != len(self.variants):
            raise ValueError("variants must be non-empty and unique")
        return self


class EvaluationMetrics(EvaluationModel):
    """Deterministic outcome, trajectory, safety and resource measurements."""

    task_completed: bool
    final_answer_schema_valid: bool
    evidence_precision: float = Field(ge=0.0, le=1.0)
    evidence_recall: float = Field(ge=0.0, le=1.0)
    provenance_valid: bool
    unsupported_claim_rate: float = Field(ge=0.0, le=1.0)
    tool_selection_valid_rate: float = Field(ge=0.0, le=1.0)
    routing_correct: bool
    trajectory_valid: bool
    unnecessary_actions: int = Field(ge=0)
    repeated_actions: int = Field(ge=0)
    recovered_from_failure: bool | None
    budget_adhered: bool
    human_interventions: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    latency_seconds: float | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    peak_memory_mb: float | None = Field(default=None, ge=0)
    structured_output_valid_rate: float | None = Field(default=None, ge=0.0, le=1.0)


class EvaluationRun(EvaluationModel):
    """One scored run linked to preserved canonical state and trace paths."""

    experiment_id: str
    run_id: str
    implementation: str
    variant: CaseStudyVariant
    repetition: int = Field(gt=0)
    metrics: EvaluationMetrics
    state_path: str
    trace_path: str
    final_answer_path: str | None = None
    provider_metadata: dict[str, JsonValue] = Field(default_factory=dict)
    local_model_metadata: dict[str, JsonValue] | None = None


class AggregateMetrics(EvaluationModel):
    """Means preserve unavailable optional measurements as ``None``."""

    run_count: int = Field(gt=0)
    task_completion_rate: float = Field(ge=0.0, le=1.0)
    final_answer_valid_rate: float = Field(ge=0.0, le=1.0)
    mean_evidence_precision: float = Field(ge=0.0, le=1.0)
    mean_evidence_recall: float = Field(ge=0.0, le=1.0)
    mean_unsupported_claim_rate: float = Field(ge=0.0, le=1.0)
    mean_tool_selection_valid_rate: float = Field(ge=0.0, le=1.0)
    trajectory_valid_rate: float = Field(ge=0.0, le=1.0)
    recovery_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_model_calls: float = Field(ge=0.0)
    mean_tool_calls: float = Field(ge=0.0)
    mean_total_tokens: float | None = Field(default=None, ge=0.0)
    mean_latency_seconds: float | None = Field(default=None, ge=0.0)
    mean_cost_usd: float | None = Field(default=None, ge=0.0)
    mean_peak_memory_mb: float | None = Field(default=None, ge=0.0)


class ExperimentResult(EvaluationModel):
    """Complete machine-readable experiment output."""

    configuration: ExperimentConfig
    configuration_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    runs: tuple[EvaluationRun, ...]
    aggregate: AggregateMetrics
