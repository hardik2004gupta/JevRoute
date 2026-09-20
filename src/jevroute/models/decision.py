"""DecisionResult and related types: the normalized output of every router."""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field


class Severity(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class Category(str, Enum):
    Billing = "Billing"
    Bug = "Bug"
    Feature = "Feature"
    Account = "Account"
    Other = "Other"


class Action(str, Enum):
    SEND = "SEND"
    HOLD = "HOLD"
    ESCALATE = "ESCALATE"


Probability = Annotated[float, Field(ge=0.0, le=1.0)]


class ConfidenceOutput(BaseModel):
    """Optional confidence/probability fields.

    All fields are nullable. Systems that do not natively produce probabilities
    must leave these as None rather than manufacturing confidence values.
    (JevRoute_MVP_Technical_Architecture.md §9)
    """

    severity_confidence: float | None = Field(None, ge=0.0, le=1.0)
    category_confidence: float | None = Field(None, ge=0.0, le=1.0)
    policy_violation_probability: float | None = Field(None, ge=0.0, le=1.0)
    hallucination_probability: float | None = Field(None, ge=0.0, le=1.0)
    tone_risk_probability: float | None = Field(None, ge=0.0, le=1.0)
    action_confidence: float | None = Field(None, ge=0.0, le=1.0)


class DecisionResult(BaseModel):
    """Normalized output of every router.

    One input state produces exactly one DecisionResult (Invariant 1).
    All routers produce the same schema regardless of internal implementation.
    (JevRoute_MVP_Technical_Architecture.md §8)
    """

    severity: Severity
    category: Category
    policy_violation: bool
    hallucination_risk: Probability
    tone_risk: Probability
    action: Action
    confidence: ConfidenceOutput = Field(default_factory=ConfidenceOutput)

    # Metadata for observability and reproducibility
    router: str = Field(..., description="Router that produced this result (e.g. mock_jev, rules).")
    router_version: str = Field(..., description="Version string for this router implementation.")
    schema_valid: bool = Field(True, description="Whether the output passed schema validation.")
    latency_ms: float | None = Field(None, description="Router latency in milliseconds (perf_counter).")
    input_tokens: int | None = Field(None, description="Input tokens consumed (if applicable).")
    output_tokens: int | None = Field(None, description="Output tokens consumed (if applicable).")
    estimated_cost_usd: float | None = Field(None, description="Estimated router cost in USD.")
    retry_count: int = Field(0, description="Number of retries before this result was produced (0 = no retries).")
