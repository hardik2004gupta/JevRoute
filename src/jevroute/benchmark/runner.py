"""BenchmarkRunner: router-agnostic benchmark execution engine.

The runner does not contain any router-specific branching logic.
All router-specific behavior belongs behind the DecisionRouter protocol.

Usage pattern:
    runner = BenchmarkRunner(config, results_dir)
    await runner.run(router, router_name="rules")
"""

from __future__ import annotations

import asyncio
import json
import logging
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from jevroute.benchmark.config import BenchmarkConfig
from jevroute.benchmark.loader import WorkloadExample, WorkloadLoader
from jevroute.benchmark.recorder import (
    BenchmarkRecord,
    ResultRecorder,
    make_run_id,
    utc_now_iso,
)
from jevroute.config.settings import DECISION_SCHEMA_VERSION, get_settings
from jevroute.evaluation.quality import compute_quality_metrics
from jevroute.evaluation.latency import compute_latency_metrics
from jevroute.evaluation.cost import compute_cost_metrics
from jevroute.evaluation.throughput import compute_throughput_metrics
from jevroute.evaluation.calibration import compute_calibration_metrics
from jevroute.models.state import ApplicationState
from jevroute.policy.engine import POLICY_VERSION, PolicyEngine
from jevroute.routers.base import DecisionRouter
from jevroute.routers.llm_provider import RouterError
from jevroute.routers.llm_single import PROMPT_VERSION as LLM_SINGLE_PROMPT_VERSION
from jevroute.routers.llm_parallel import PROMPT_VERSION as LLM_PARALLEL_PROMPT_VERSION

logger = logging.getLogger(__name__)


def _get_prompt_version(router_name: str) -> str | None:
    if router_name == "llm_single":
        return LLM_SINGLE_PROMPT_VERSION
    if router_name == "llm_parallel":
        return LLM_PARALLEL_PROMPT_VERSION
    return None


def _get_git_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _get_environment_metadata() -> dict[str, Any]:
    return {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "git_sha": _get_git_sha(),
    }


class BenchmarkRunner:
    """Router-agnostic benchmark execution engine.

    Iterates examples, executes router decisions, applies policy, records
    observations, and produces aggregate metrics.
    """

    def __init__(
        self,
        config: BenchmarkConfig,
        results_dir: Path | str,
        datasets_dir: Path | str,
        policy_engine: PolicyEngine | None = None,
        force: bool = False,
    ) -> None:
        self._config = config
        self._results_dir = Path(results_dir)
        self._datasets_dir = Path(datasets_dir)
        self._policy_engine = policy_engine or PolicyEngine()
        self._force = force

    async def run(
        self,
        router: DecisionRouter,
        router_name: str,
        router_version: str,
        examples: list[WorkloadExample] | None = None,
    ) -> dict[str, Any]:
        """Execute a benchmark run for one router.

        Args:
            router: Any object conforming to DecisionRouter Protocol.
            router_name: Stable identifier (e.g. 'rules', 'llm_single').
            router_version: Semver-style version string.
            examples: Pre-loaded examples; loaded from disk if None.

        Returns:
            Aggregate metrics dictionary.
        """
        cfg = self._config
        experiment_id = cfg.experiment.name

        if examples is None:
            loader = WorkloadLoader(self._datasets_dir)
            examples = loader.load(cfg.experiment.dataset, cfg.experiment.split)

        if cfg.experiment.max_examples is not None:
            examples = examples[: cfg.experiment.max_examples]

        if not examples:
            raise ValueError("No examples loaded for benchmark run")

        run_id = make_run_id(experiment_id, router_name)
        prompt_version = _get_prompt_version(router_name)

        logger.info(
            "Starting run %s: router=%s version=%s examples=%d concurrency=%d",
            run_id,
            router_name,
            router_version,
            len(examples),
            cfg.experiment.concurrency,
        )

        recorder = ResultRecorder(self._results_dir, force=self._force)
        records: list[BenchmarkRecord] = []
        semaphore = asyncio.Semaphore(cfg.experiment.concurrency)

        t_wall_start = perf_counter()

        async def _execute_one(example: WorkloadExample) -> BenchmarkRecord:
            async with semaphore:
                return await self._execute_example(
                    example=example,
                    router=router,
                    router_name=router_name,
                    router_version=router_version,
                    experiment_id=experiment_id,
                    run_id=run_id,
                    prompt_version=prompt_version,
                )

        tasks = [asyncio.create_task(_execute_one(ex)) for ex in examples]
        completed = await asyncio.gather(*tasks, return_exceptions=False)

        t_wall_end = perf_counter()
        total_wall_clock_s = t_wall_end - t_wall_start

        for record in completed:
            records.append(record)
            recorder.write(experiment_id, router_name, record)
        recorder.close_all()

        # Aggregate metrics
        aggregate = self._compute_aggregate(
            records=records,
            router_name=router_name,
            router_version=router_version,
            total_wall_clock_s=total_wall_clock_s,
            concurrency=cfg.experiment.concurrency,
        )

        # Persist aggregate and metadata
        self._persist_aggregate(experiment_id, router_name, aggregate)
        self._persist_metadata(
            experiment_id=experiment_id,
            router_name=router_name,
            run_id=run_id,
            router_version=router_version,
            prompt_version=prompt_version,
            num_examples=len(examples),
            total_wall_clock_s=total_wall_clock_s,
        )

        logger.info(
            "Run complete: router=%s accuracy=%.3f cost=%.6f records=%d",
            router_name,
            aggregate.get("accuracy") or 0.0,
            aggregate.get("total_cost_usd") or 0.0,
            len(records),
        )

        return aggregate

    async def _execute_example(
        self,
        example: WorkloadExample,
        router: DecisionRouter,
        router_name: str,
        router_version: str,
        experiment_id: str,
        run_id: str,
        prompt_version: str | None,
    ) -> BenchmarkRecord:
        started_at = utc_now_iso()
        t_start = perf_counter()
        error_type: str | None = None
        error_message: str | None = None
        prediction_dict: dict[str, Any] | None = None
        final_action: str | None = None
        policy_applied = False
        policy_override_reason: str | None = None
        router_latency_ms: float | None = None
        total_latency_ms: float | None = None
        input_tokens: int | None = None
        output_tokens: int | None = None
        cost: float | None = None
        schema_valid = False
        retry_count = 0

        try:
            t_router_start = perf_counter()
            result = await router.decide(example.state)
            t_router_end = perf_counter()
            router_latency_ms = (t_router_end - t_router_start) * 1000

            input_tokens = result.input_tokens
            output_tokens = result.output_tokens
            cost = result.estimated_cost_usd
            schema_valid = result.schema_valid
            retry_count = result.retry_count

            prediction_dict = {
                "severity": result.severity.value,
                "category": result.category.value,
                "policy_violation": result.policy_violation,
                "hallucination_risk": result.hallucination_risk,
                "tone_risk": result.tone_risk,
                "action": result.action.value,
            }

            # Apply shared policy engine (router-independent)
            t_policy_start = perf_counter()
            policy_result = self._policy_engine.apply(result)
            t_policy_end = perf_counter()

            final_action = policy_result.final_action.value
            policy_applied = policy_result.policy_applied
            policy_override_reason = policy_result.override_reason

        except RouterError as exc:
            error_type = exc.error_type
            error_message = str(exc)
            schema_valid = False
        except Exception as exc:
            error_type = "INTERNAL_ERROR"
            error_message = f"{type(exc).__name__}: {exc}"
            schema_valid = False

        total_latency_ms = (perf_counter() - t_start) * 1000

        gt = example.ground_truth
        ground_truth_dict = {
            "severity": gt.severity,
            "category": gt.category,
            "policy_violation": gt.policy_violation,
            "hallucination_risk": gt.hallucination_risk,
            "tone_risk": gt.tone_risk,
            "action": gt.action,
        }

        return BenchmarkRecord(
            experiment_id=experiment_id,
            run_id=run_id,
            example_id=example.example_id,
            router=router_name,
            router_version=router_version,
            decision_schema_version=DECISION_SCHEMA_VERSION,
            policy_version=POLICY_VERSION,
            prompt_version=prompt_version,
            started_at=started_at,
            router_latency_ms=round(router_latency_ms, 3) if router_latency_ms is not None else None,
            total_latency_ms=round(total_latency_ms, 3),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost,
            schema_valid=schema_valid,
            retry_count=retry_count,
            error_type=error_type,
            error_message=error_message,
            prediction=prediction_dict,
            ground_truth=ground_truth_dict,
            final_action=final_action,
            policy_applied=policy_applied,
            policy_override_reason=policy_override_reason,
        )

    def _compute_aggregate(
        self,
        records: list[BenchmarkRecord],
        router_name: str,
        router_version: str,
        total_wall_clock_s: float,
        concurrency: int,
    ) -> dict[str, Any]:
        quality = compute_quality_metrics(records)
        latency = compute_latency_metrics(records)
        cost = compute_cost_metrics(records)
        throughput = compute_throughput_metrics(records, total_wall_clock_s)
        calibration = compute_calibration_metrics(records)

        return {
            "router": router_name,
            "router_version": router_version,
            "experiment_id": self._config.experiment.name,
            "concurrency": concurrency,
            "examples": len(records),
            "decisions": quality["decisions"],
            "correct_decisions": quality["correct_decisions"],
            "accuracy": quality["accuracy"],
            "macro_f1": quality["macro_f1"],
            "bad_send_rate": quality["bad_send_rate"],
            "over_escalation_rate": quality["over_escalation_rate"],
            "missed_policy_violation_rate": quality["missed_policy_violation_rate"],
            "send_accuracy": quality["send_accuracy"],
            "hold_accuracy": quality["hold_accuracy"],
            "escalate_accuracy": quality["escalate_accuracy"],
            "schema_failure_rate": quality["schema_failure_rate"],
            **latency,
            **cost,
            **throughput,
            **calibration,
        }

    def _persist_aggregate(
        self,
        experiment_id: str,
        router_name: str,
        aggregate: dict[str, Any],
    ) -> None:
        import csv

        agg_dir = self._results_dir / "aggregate"
        agg_dir.mkdir(parents=True, exist_ok=True)
        path = agg_dir / f"{experiment_id}.csv"

        write_header = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(aggregate.keys()))
            if write_header:
                writer.writeheader()
            writer.writerow(aggregate)
        logger.info("Aggregate written to %s", path)

    def _persist_metadata(
        self,
        experiment_id: str,
        router_name: str,
        run_id: str,
        router_version: str,
        prompt_version: str | None,
        num_examples: int,
        total_wall_clock_s: float,
    ) -> None:
        meta_dir = self._results_dir / "metadata"
        meta_dir.mkdir(parents=True, exist_ok=True)
        path = meta_dir / f"{experiment_id}.json"

        existing: dict[str, Any] = {}
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = {}

        runs = existing.get("runs", [])
        runs.append({
            "run_id": run_id,
            "router": router_name,
            "router_version": router_version,
            "prompt_version": prompt_version,
            "decision_schema_version": DECISION_SCHEMA_VERSION,
            "policy_version": POLICY_VERSION,
            "num_examples": num_examples,
            "total_wall_clock_s": round(total_wall_clock_s, 3),
            "timestamp": utc_now_iso(),
            "experiment_config": self._config.to_dict(),
            "environment": _get_environment_metadata(),
        })
        existing["runs"] = runs

        with path.open("w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
        logger.info("Metadata written to %s", path)
