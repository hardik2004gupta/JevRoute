"""Benchmark preflight: check all requirements before starting a benchmark run."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jevroute.readiness.providers import (
    ProviderReadiness,
    ReadinessStatus,
    check_dataset_readiness,
    check_generation_readiness,
    check_jev_readiness,
    check_llm_readiness,
)


@dataclass
class PreflightResult:
    dataset: ProviderReadiness
    jev: ProviderReadiness
    llm: ProviderReadiness
    generation: ProviderReadiness
    policy_ready: bool
    schema_ready: bool
    output_dirs_writable: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return (
            self.dataset.status == ReadinessStatus.READY
            and self.jev.status == ReadinessStatus.READY
            and self.llm.status == ReadinessStatus.READY
            and self.policy_ready
            and self.schema_ready
            and self.output_dirs_writable
            and not self.errors
        )

    def experiment_ready(self, experiment_id: str) -> tuple[bool, str]:
        """Return (ready, reason) for a specific experiment."""
        if experiment_id == "e2e-v1":
            if self.generation.status != ReadinessStatus.READY:
                return False, f"Generation provider: {self.generation.reason}"
        base_ok = (
            self.dataset.status == ReadinessStatus.READY
            and self.jev.status == ReadinessStatus.READY
            and self.llm.status == ReadinessStatus.READY
        )
        if not base_ok:
            blockers = []
            if self.dataset.status != ReadinessStatus.READY:
                blockers.append(f"dataset: {self.dataset.reason}")
            if self.jev.status != ReadinessStatus.READY:
                blockers.append(f"jev: {self.jev.reason}")
            if self.llm.status != ReadinessStatus.READY:
                blockers.append(f"llm: {self.llm.reason}")
            return False, "; ".join(blockers)
        return True, "READY"

    def to_dict(self) -> dict[str, Any]:
        def _r(r: ProviderReadiness) -> dict[str, Any]:
            return {"status": r.status.value, "reason": r.reason}

        experiments: dict[str, Any] = {}
        for exp_id in ("baseline-v1", "scaling-v1", "fastpath-v1", "context-v1", "dependency-v1", "e2e-v1"):
            ok, reason = self.experiment_ready(exp_id)
            experiments[exp_id] = {"status": "READY" if ok else "BLOCKED", "reason": reason}

        return {
            "_schema": "jevroute-preflight-v1",
            "overall": "READY" if self.ready else "BLOCKED",
            "dataset": _r(self.dataset),
            "jev": _r(self.jev),
            "llm": _r(self.llm),
            "generation": _r(self.generation),
            "policy": {"status": "READY" if self.policy_ready else "BLOCKED"},
            "schema": {"status": "READY" if self.schema_ready else "BLOCKED"},
            "output_dirs": {"writable": self.output_dirs_writable},
            "experiments": experiments,
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def print_summary(self) -> None:
        print("\n=== BENCHMARK PREFLIGHT ===\n")
        items = [
            ("Dataset", self.dataset.status.value, self.dataset.reason),
            ("Jev", self.jev.status.value, self.jev.reason),
            ("LLM", self.llm.status.value, self.llm.reason),
            ("Generation", self.generation.status.value, self.generation.reason),
            ("Policy", "READY" if self.policy_ready else "BLOCKED", ""),
            ("Schema", "READY" if self.schema_ready else "BLOCKED", ""),
            ("Output dirs", "WRITABLE" if self.output_dirs_writable else "NOT WRITABLE", ""),
        ]
        for name, status, reason in items:
            indicator = "✓" if status in ("READY", "WRITABLE") else "✗"
            suffix = f" — {reason}" if reason else ""
            print(f"  {indicator} {name:<14} {status}{suffix}")

        print()
        for exp_id in ("baseline-v1", "scaling-v1", "fastpath-v1", "context-v1", "dependency-v1", "e2e-v1"):
            ok, reason = self.experiment_ready(exp_id)
            status = "READY" if ok else "BLOCKED"
            print(f"  {exp_id:<18} {status}")

        print()
        if self.ready:
            print("  RESULT: READY — benchmark can proceed")
        else:
            print("  RESULT: BENCHMARK NOT READY")
            if self.errors:
                for e in self.errors:
                    print(f"    - {e}")
        print()


def run_preflight(
    results_dir: Path | str = "results",
    datasets_dir: Path | str = "datasets",
    research_dataset_stem: str | None = None,
    settings: Any = None,
) -> PreflightResult:
    """Run all preflight checks and return a structured result."""
    from jevroute.config.settings import get_settings

    if settings is None:
        settings = get_settings()

    results_dir = Path(results_dir)
    datasets_dir = Path(datasets_dir)

    # Dataset check
    research_dataset_path = None
    frozen_manifest_exists = False
    if research_dataset_stem:
        test_path = datasets_dir / "test" / f"{research_dataset_stem}.jsonl"
        if test_path.exists():
            research_dataset_path = str(test_path)
        manifest_path = datasets_dir / "manifests" / f"frozen_test_{research_dataset_stem}.json"
        frozen_manifest_exists = manifest_path.exists()

    ci_count = 0
    ci_path = datasets_dir / "test" / "benchmark_fixture.jsonl"
    if ci_path.exists():
        ci_count = sum(1 for l in ci_path.read_text().splitlines() if l.strip())

    dataset_readiness = check_dataset_readiness(
        research_dataset_path=research_dataset_path,
        frozen_manifest_exists=frozen_manifest_exists,
        ci_fixture_count=ci_count,
    )
    jev_readiness = check_jev_readiness(settings)
    llm_readiness = check_llm_readiness(settings)
    gen_readiness = check_generation_readiness(settings)

    # Output dir write check
    output_dirs_writable = True
    errors: list[str] = []
    warnings: list[str] = []

    raw_dir = results_dir / "raw"
    try:
        raw_dir.mkdir(parents=True, exist_ok=True)
        test_file = raw_dir / ".preflight_write_test"
        test_file.write_text("ok")
        test_file.unlink()
    except OSError as exc:
        output_dirs_writable = False
        errors.append(f"Cannot write to results directory: {exc}")

    return PreflightResult(
        dataset=dataset_readiness,
        jev=jev_readiness,
        llm=llm_readiness,
        generation=gen_readiness,
        policy_ready=True,  # PolicyEngine has no external dependency
        schema_ready=True,  # Decision schema is compiled into the codebase
        output_dirs_writable=output_dirs_writable,
        errors=errors,
        warnings=warnings,
    )
