"""JevRoute FastAPI application — Phase 2 benchmark-aware shell."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from jevroute.api.logging_config import configure_logging, get_logger
from jevroute.api.models import (
    BenchmarkStatusResponse,
    DecideRequest,
    DecisionResponse,
    ErrorResponse,
    HealthResponse,
    StatusResponse,
)
from jevroute.config.settings import APPLICATION_VERSION, DECISION_SCHEMA_VERSION, get_settings
from jevroute.models.state import redact_state
from jevroute.policy.engine import PolicyEngine
from jevroute.routers.mock_jev import MockJevRouter

configure_logging()
log = get_logger("jevroute.api")

_router = MockJevRouter()


def _get_policy_engine() -> PolicyEngine:
    settings = get_settings()
    return PolicyEngine(hallucination_threshold=settings.hallucination_threshold)


# Eagerly initialize so the engine is available both in lifespan and ASGI test mode.
_policy_engine: PolicyEngine = _get_policy_engine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _policy_engine
    settings = get_settings()
    _policy_engine = PolicyEngine(hallucination_threshold=settings.hallucination_threshold)
    log.info(
        "JevRoute API starting | env=%s version=%s router=mock_jev",
        settings.environment,
        settings.app_version,
    )
    yield
    log.info("JevRoute API shutting down.")


app = FastAPI(
    title="JevRoute",
    description="System-One Control Plane Benchmark — Phase 1 Mock Shell",
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
    return StatusResponse(
        status="ok",
        environment=settings.environment,
        app_version=settings.app_version,
        schema_version=settings.decision_schema_version,
        policy_version=settings.policy_version,
        active_router="mock_jev",
        benchmark_results_available=False,
    )


@app.get("/api/v1/benchmarks", response_model=BenchmarkStatusResponse, tags=["benchmarks"])
async def benchmarks_status() -> BenchmarkStatusResponse:
    """Return available benchmark experiment status."""
    import json
    from pathlib import Path
    results_dir = Path("results")
    experiments: list[dict] = []
    meta_dir = results_dir / "metadata"
    if meta_dir.exists():
        for meta_file in sorted(meta_dir.glob("*.json")):
            try:
                data = json.loads(meta_file.read_text())
                experiments.append({
                    "experiment_id": meta_file.stem,
                    "runs": len(data.get("runs", [])),
                })
            except Exception:
                pass
    return BenchmarkStatusResponse(
        experiments=experiments,
        results_available=len(experiments) > 0,
    )


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
