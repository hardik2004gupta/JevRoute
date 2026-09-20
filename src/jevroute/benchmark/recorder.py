"""ResultRecorder: immutable append-only JSONL result persistence.

Raw observations are written after each execution.
Completed records are never modified (Invariant 5).
Overwrites are rejected by default; explicit force is required.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from jevroute.config.settings import DECISION_SCHEMA_VERSION
from jevroute.policy.engine import POLICY_VERSION

logger = logging.getLogger(__name__)


class BenchmarkRecord(BaseModel):
    """Immutable raw observation from one router execution.

    Must contain everything needed to reproduce or audit the result.
    Fields follow the architecture schema (§14).
    """

    # Identity
    experiment_id: str
    run_id: str
    example_id: str
    router: str
    router_version: str

    # Versioning
    decision_schema_version: str = DECISION_SCHEMA_VERSION
    policy_version: str = POLICY_VERSION
    prompt_version: str | None = None  # None for routers that do not use prompts

    # Timing
    started_at: str  # ISO-8601 UTC timestamp
    router_latency_ms: float | None = None
    total_latency_ms: float | None = None

    # Token / cost accounting
    input_tokens: int | None = None
    output_tokens: int | None = None
    num_model_calls: int | None = None  # > 1 for parallel routers
    estimated_cost_usd: float | None = None

    # Outcome
    schema_valid: bool = True
    retry_count: int = 0
    error_type: str | None = None
    error_message: str | None = None

    # Predictions (None when the router failed to produce a result)
    prediction: dict[str, Any] | None = None

    # Ground truth (set by the benchmark runner; never passed to the router)
    ground_truth: dict[str, Any] | None = None

    # Final action after shared policy engine
    final_action: str | None = None
    policy_applied: bool = False
    policy_override_reason: str | None = None


class ResultRecorder:
    """Writes BenchmarkRecord objects to append-only JSONL files.

    Directory layout (per architecture §38):
      results/raw/<experiment_id>/<router>.jsonl

    Overwrites are blocked by default. Use force=True to allow.
    """

    def __init__(self, results_dir: Path | str, force: bool = False) -> None:
        self._results_dir = Path(results_dir)
        self._force = force
        self._handles: dict[str, Any] = {}  # router -> open file handle

    def open(self, experiment_id: str, router: str) -> None:
        """Prepare the output file for an experiment/router pair."""
        raw_dir = self._results_dir / "raw" / experiment_id
        raw_dir.mkdir(parents=True, exist_ok=True)
        path = raw_dir / f"{router}.jsonl"

        if path.exists() and not self._force:
            raise FileExistsError(
                f"Result file already exists: {path}. "
                "Use force=True to overwrite (this will append to the existing file)."
            )

        key = f"{experiment_id}/{router}"
        self._handles[key] = path.open("a", encoding="utf-8")
        logger.info("Recording to %s", path)

    def write(self, experiment_id: str, router: str, record: BenchmarkRecord) -> None:
        """Append one record to the JSONL file.

        Records are serialized immediately to prevent data loss on crash.
        """
        key = f"{experiment_id}/{router}"
        if key not in self._handles:
            self.open(experiment_id, router)
        handle = self._handles[key]
        handle.write(record.model_dump_json() + "\n")
        handle.flush()  # Crash-safe: flush after each record

    def close_all(self) -> None:
        """Flush and close all open file handles."""
        for handle in self._handles.values():
            handle.flush()
            handle.close()
        self._handles.clear()

    def __enter__(self) -> "ResultRecorder":
        return self

    def __exit__(self, *_: object) -> None:
        self.close_all()


def make_run_id(experiment_id: str, router: str) -> str:
    """Generate a stable run identifier from experiment + router + timestamp."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{experiment_id}__{router}__{ts}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
