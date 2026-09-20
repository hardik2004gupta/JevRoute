"""Typed API request/response models — never expose raw domain models directly."""

from __future__ import annotations

from pydantic import BaseModel

from jevroute.models.decision import Action, Category, ConfidenceOutput, DecisionResult, Severity
from jevroute.models.state import ApplicationState


class DecideRequest(BaseModel):
    state: ApplicationState


class DecisionResponse(BaseModel):
    status: str
    router: str
    decision: DecisionResult
    final_action: Action
    policy_version: str
    schema_version: str
    policy_applied: bool
    override_reason: str | None


class StatusResponse(BaseModel):
    status: str
    environment: str
    app_version: str
    schema_version: str
    policy_version: str
    active_router: str
    benchmark_results_available: bool


class HealthResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    code: str | None = None


class BenchmarkStatusResponse(BaseModel):
    experiments: list[dict]
    results_available: bool
