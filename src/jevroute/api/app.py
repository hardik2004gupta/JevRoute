"""JevRoute FastAPI application — Phase 3 research observatory."""

from __future__ import annotations

import csv
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from jevroute.api.logging_config import configure_logging, get_logger
from jevroute.api.models import (
    BenchmarkStatusResponse,
    DatasetsResponse,
    DecideRequest,
    DecisionResponse,
    ErrorResponse,
    ExperimentDetailResponse,
    ExperimentSummary,
    ExperimentsResponse,
    HealthResponse,
    RouterAggregateRow,
    RunsResponse,
    StatusResponse,
)
from jevroute.config.settings import APPLICATION_VERSION, DECISION_SCHEMA_VERSION, get_settings
from jevroute.models.state import redact_state
from jevroute.policy.engine import PolicyEngine
from jevroute.routers.mock_jev import MockJevRouter

configure_logging()
log = get_logger("jevroute.api")

_router = MockJevRouter()
_RESULTS_DIR = Path("results")

_KNOWN_EXPERIMENTS = [
    "baseline-v1",
    "scaling-v1",
    "fastpath-v1",
    "context-v1",
    "dependency-v1",
    "e2e-v1",
]


def _get_policy_engine() -> PolicyEngine:
    settings = get_settings()
    return PolicyEngine(hallucination_threshold=settings.hallucination_threshold)


_policy_engine: PolicyEngine = _get_policy_engine()


def _read_metadata(experiment_id: str) -> dict[str, Any] | None:
    meta_path = _RESULTS_DIR / "metadata" / f"{experiment_id}.json"
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_aggregate(experiment_id: str) -> list[RouterAggregateRow]:
    agg_path = _RESULTS_DIR / "aggregate" / f"{experiment_id}.csv"
    if not agg_path.exists():
        return []
    rows = []
    try:
        with agg_path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                def _f(k: str) -> float | None:
                    v = row.get(k)
                    if v is None or v == "" or v == "None":
                        return None
                    try:
                        return float(v)
                    except (ValueError, TypeError):
                        return None

                def _i(k: str) -> int | None:
                    v = row.get(k)
                    if v is None or v == "" or v == "None":
                        return None
                    try:
                        return int(float(v))
                    except (ValueError, TypeError):
                        return None

                rows.append(RouterAggregateRow(
                    router=row.get("router", ""),
                    router_version=row.get("router_version"),
                    experiment_id=row.get("experiment_id", experiment_id),
                    examples=_i("examples"),
                    decisions=_i("decisions"),
                    correct_decisions=_i("correct_decisions"),
                    accuracy=_f("accuracy"),
                    macro_f1=_f("macro_f1"),
                    bad_send_rate=_f("bad_send_rate"),
                    over_escalation_rate=_f("over_escalation_rate"),
                    missed_policy_violation_rate=_f("missed_policy_violation_rate"),
                    schema_failure_rate=_f("schema_failure_rate"),
                    p50_latency_ms=_f("p50_latency_ms"),
                    p95_latency_ms=_f("p95_latency_ms"),
                    p99_latency_ms=_f("p99_latency_ms"),
                    mean_latency_ms=_f("mean_latency_ms"),
                    total_cost_usd=_f("total_cost_usd"),
                    cost_per_1k_decisions_usd=_f("cost_per_1k_decisions_usd"),
                    cost_per_correct_decision_usd=_f("cost_per_correct_decision_usd"),
                    decision_throughput_per_s=_f("decision_throughput_per_s"),
                    brier_score=_f("brier_score"),
                    ece=_f("ece"),
                ))
    except Exception as exc:
        log.warning("Failed to read aggregate CSV for %s: %s", experiment_id, exc)
    return rows


def _experiment_status(experiment_id: str) -> str:
    meta = _read_metadata(experiment_id)
    if meta is None:
        return "NOT_RUN"
    runs = meta.get("runs", [])
    if not runs:
        return "NOT_RUN"
    last_run = runs[-1]
    if last_run.get("error"):
        return "FAILED"
    return "COMPLETE"


def _build_experiment_summary(experiment_id: str) -> ExperimentSummary:
    meta = _read_metadata(experiment_id)
    status = _experiment_status(experiment_id)
    if meta is None:
        return ExperimentSummary(experiment_id=experiment_id, status=status)
    runs = meta.get("runs", [])
    routers = list({r.get("router", "") for r in runs if r.get("router")})
    last_run = runs[-1] if runs else {}
    # Read experiment config from first run
    exp_config = (runs[0].get("experiment_config") or {}).get("experiment", {}) if runs else {}
    return ExperimentSummary(
        experiment_id=experiment_id,
        status=status,
        dataset=exp_config.get("dataset"),
        split=exp_config.get("split"),
        num_runs=len(runs),
        routers=sorted(routers),
        last_run_at=last_run.get("timestamp"),
        aggregate_path=f"results/aggregate/{experiment_id}.csv",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _policy_engine
    settings = get_settings()
    _policy_engine = PolicyEngine(hallucination_threshold=settings.hallucination_threshold)
    log.info(
        "JevRoute API starting | env=%s version=%s",
        settings.environment,
        settings.app_version,
    )
    yield
    log.info("JevRoute API shutting down.")


app = FastAPI(
    title="JevRoute",
    description="System-One Control Plane Benchmark — Research Observatory",
    version=APPLICATION_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("Unhandled error | path=%s error=%s", request.url.path, str(exc))
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="internal_error",
            detail="An unexpected error occurred.",
            code="INTERNAL_ERROR",
        ).model_dump(),
    )


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/v1/status", response_model=StatusResponse, tags=["system"])
async def status() -> StatusResponse:
    settings = get_settings()
    any_results = any(
        (_RESULTS_DIR / "metadata" / f"{eid}.json").exists()
        for eid in _KNOWN_EXPERIMENTS
    )
    return StatusResponse(
        status="ok",
        environment=settings.environment,
        app_version=settings.app_version,
        schema_version=settings.decision_schema_version,
        policy_version=settings.policy_version,
        active_router="mock_jev",
        benchmark_results_available=any_results,
    )


# ── Benchmarks ─────────────────────────────────────────────────────────────────

@app.get("/api/v1/benchmarks", response_model=BenchmarkStatusResponse, tags=["benchmarks"])
async def benchmarks_status() -> BenchmarkStatusResponse:
    """Return experiment status for all known experiments."""
    experiments = []
    meta_dir = _RESULTS_DIR / "metadata"
    seen = set()
    if meta_dir.exists():
        for meta_file in sorted(meta_dir.glob("*.json")):
            eid = meta_file.stem
            seen.add(eid)
            meta = _read_metadata(eid)
            runs = meta.get("runs", []) if meta else []
            experiments.append({
                "experiment_id": eid,
                "status": _experiment_status(eid),
                "runs": len(runs),
            })
    for eid in _KNOWN_EXPERIMENTS:
        if eid not in seen:
            experiments.append({"experiment_id": eid, "status": "NOT_RUN", "runs": 0})
    return BenchmarkStatusResponse(
        experiments=experiments,
        results_available=len(seen) > 0,
    )


@app.get("/api/v1/experiments", response_model=ExperimentsResponse, tags=["experiments"])
async def list_experiments() -> ExperimentsResponse:
    """List all known experiments with their status and summary."""
    summaries = [_build_experiment_summary(eid) for eid in _KNOWN_EXPERIMENTS]
    return ExperimentsResponse(experiments=summaries)


@app.get("/api/v1/experiments/{experiment_id}", response_model=ExperimentDetailResponse, tags=["experiments"])
async def get_experiment(experiment_id: str) -> ExperimentDetailResponse:
    """Return detailed information for one experiment."""
    if experiment_id not in _KNOWN_EXPERIMENTS:
        raise HTTPException(status_code=404, detail=f"Unknown experiment: {experiment_id}")
    status = _experiment_status(experiment_id)
    meta = _read_metadata(experiment_id) or {}
    aggregates = _read_aggregate(experiment_id)
    return ExperimentDetailResponse(
        experiment_id=experiment_id,
        status=status,
        metadata=meta,
        aggregates=aggregates,
    )


@app.get("/api/v1/experiments/{experiment_id}/metrics", response_model=list[RouterAggregateRow], tags=["experiments"])
async def get_experiment_metrics(experiment_id: str) -> list[RouterAggregateRow]:
    """Return aggregate metrics for all routers in one experiment."""
    if experiment_id not in _KNOWN_EXPERIMENTS:
        raise HTTPException(status_code=404, detail=f"Unknown experiment: {experiment_id}")
    return _read_aggregate(experiment_id)


@app.get("/api/v1/experiments/{experiment_id}/runs", response_model=RunsResponse, tags=["experiments"])
async def get_experiment_runs(experiment_id: str) -> RunsResponse:
    """Return run metadata for one experiment."""
    if experiment_id not in _KNOWN_EXPERIMENTS:
        raise HTTPException(status_code=404, detail=f"Unknown experiment: {experiment_id}")
    meta = _read_metadata(experiment_id) or {}
    return RunsResponse(experiment_id=experiment_id, runs=meta.get("runs", []))


@app.get("/api/v1/datasets", response_model=DatasetsResponse, tags=["datasets"])
async def list_datasets() -> DatasetsResponse:
    """List available datasets and their split sizes."""
    datasets_dir = Path("datasets")
    results = []
    for split in ("train", "validation", "test"):
        split_dir = datasets_dir / split
        if not split_dir.exists():
            continue
        for jsonl_file in sorted(split_dir.glob("*.jsonl")):
            lines = 0
            try:
                with jsonl_file.open(encoding="utf-8") as f:
                    lines = sum(1 for _ in f)
            except Exception:
                pass
            results.append({
                "name": jsonl_file.stem,
                "split": split,
                "path": str(jsonl_file).replace("\\", "/"),
                "examples": lines,
            })
    return DatasetsResponse(datasets=results)


# ── Decisions ──────────────────────────────────────────────────────────────────

@app.post("/api/v1/decide", response_model=DecisionResponse, tags=["decisions"])
async def decide(body: DecideRequest) -> DecisionResponse:
    """Run a mock decision for development and frontend integration.

    Uses MockJevRouter + shared PolicyEngine.
    This endpoint MUST NOT be used in real benchmark runs.
    """
    settings = get_settings()
    t0 = perf_counter()

    log.info("Decision request | example_id=%s router=mock_jev", body.state.example_id)

    decision = await _router.decide(body.state)
    policy_result = _policy_engine.apply(decision)

    elapsed_ms = round((perf_counter() - t0) * 1000, 3)
    log.info(
        "Decision complete | example_id=%s final_action=%s latency_ms=%.3f",
        body.state.example_id,
        policy_result.final_action.value,
        elapsed_ms,
    )

    return DecisionResponse(
        status="ok",
        router="mock_jev",
        decision=decision,
        final_action=policy_result.final_action,
        policy_version=policy_result.policy_version,
        schema_version=settings.decision_schema_version,
        policy_applied=policy_result.policy_applied,
        override_reason=policy_result.override_reason,
    )
