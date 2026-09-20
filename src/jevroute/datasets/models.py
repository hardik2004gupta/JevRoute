"""Dataset domain models: typed representations of examples, ground truth, and manifests."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class SourceType(str, Enum):
    REAL_EXTERNAL = "REAL_EXTERNAL"
    AUTHORIZED_INTERNAL = "AUTHORIZED_INTERNAL"
    SYNTHETIC = "SYNTHETIC"
    IMPORTED = "IMPORTED"
    GENERATED_FOR_TESTING = "GENERATED_FOR_TESTING"


class GroundTruth(BaseModel):
    """Labeled ground-truth annotations for one benchmark example."""

    severity: str
    category: str
    policy_violation: bool
    hallucination_risk: float = Field(ge=0.0, le=1.0)
    tone_risk: float = Field(ge=0.0, le=1.0)
    action: str

    @field_validator("severity")
    @classmethod
    def _valid_severity(cls, v: str) -> str:
        if v not in ("P1", "P2", "P3", "P4"):
            raise ValueError(f"Invalid severity: {v!r}")
        return v

    @field_validator("category")
    @classmethod
    def _valid_category(cls, v: str) -> str:
        if v not in ("Billing", "Bug", "Feature", "Account", "Other"):
            raise ValueError(f"Invalid category: {v!r}")
        return v

    @field_validator("action")
    @classmethod
    def _valid_action(cls, v: str) -> str:
        if v not in ("SEND", "HOLD", "ESCALATE"):
            raise ValueError(f"Invalid action: {v!r}")
        return v


class DatasetExample(BaseModel):
    """One labeled example in a benchmark dataset.

    The `state` fields map 1:1 to ApplicationState.
    Ground truth is carried separately and must never be passed to a router.
    """

    example_id: str
    customer_tier: str
    product: str
    region: str
    ticket_subject: str
    ticket_body: str
    draft_reply: str
    ground_truth: GroundTruth
    metadata: dict[str, Any] = Field(default_factory=dict)


class DatasetManifest(BaseModel):
    """Provenance and identity record for a versioned dataset."""

    dataset_name: str
    dataset_version: str
    created_at: str  # ISO-8601
    source_type: SourceType
    source_description: str
    dataset_hash: str  # SHA-256 of the full dataset file(s)
    record_count: int
    train_count: int
    validation_count: int
    test_count: int
    label_schema_version: str = "1.0"
    annotation_protocol_version: str | None = None
    privacy_status: str = "UNKNOWN"
    license_status: str = "UNKNOWN"
    split_seed: int | None = None
    split_algorithm: str | None = None
    generator_version: str | None = None  # Only for SYNTHETIC/GENERATED_FOR_TESTING
    generation_seed: int | None = None
    generation_config: dict[str, Any] | None = None
    notes: str | None = None


class FrozenTestManifest(BaseModel):
    """Identity record for a frozen test split.

    Must be verified before benchmark execution to prevent test-set contamination.
    """

    dataset_version: str
    test_hash: str  # SHA-256 of test split file
    example_count: int
    example_ids_hash: str  # SHA-256 of sorted example_ids joined by newline
    freeze_timestamp: str  # ISO-8601
    frozen_by: str | None = None


class ValidationReport(BaseModel):
    """Result of running the dataset validator."""

    dataset_path: str
    record_count: int
    missing_field_count: int
    invalid_enum_count: int
    probability_out_of_range_count: int
    empty_text_count: int
    duplicate_id_count: int
    duplicate_record_count: int
    missing_ground_truth_count: int
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    gate_passed: bool = False
