"""Typed API request/response models — never expose raw domain models directly."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from jevroute.models.decision import Action, DecisionResult
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


class RouterAggregateRow(BaseModel):
    """One router's aggregate metrics from a benchmark run."""
    router: str
    router_version: str | None = None
    experiment_id: str
    examples: int | None = None
    decisions: int | None = None
    correct_decisions: int | None = None
    accuracy: float | None = None
    macro_f1: float | None = None
    bad_send_rate: float | None = None
    over_escalation_rate: float | None = None
    missed_policy_violation_rate: float | None = None
    schema_failure_rate: float | None = None
    p50_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    p99_latency_ms: float | None = None
    mean_latency_ms: float | None = None
    total_cost_usd: float | None = None
    cost_per_1k_decisions_usd: float | None = None
    cost_per_correct_decision_usd: float | None = None
    decision_throughput_per_s: float | None = None
    brier_score: float | None = None
    ece: float | None = None


class ExperimentSummary(BaseModel):
    experiment_id: str
    status: str  # NOT_RUN | RUNNING | COMPLETE | FAILED
    dataset: str | None = None
    split: str | None = None
    num_runs: int = 0
    routers: list[str] = []
    last_run_at: str | None = None
    aggregate_path: str | None = None


class ExperimentsResponse(BaseModel):
    experiments: list[ExperimentSummary]


class ExperimentDetailResponse(BaseModel):
    experiment_id: str
    status: str
    metadata: dict[str, Any] = {}
    aggregates: list[RouterAggregateRow] = []


class RunsResponse(BaseModel):
    experiment_id: str
    runs: list[dict[str, Any]]


class DatasetsResponse(BaseModel):
    datasets: list[dict[str, Any]]
