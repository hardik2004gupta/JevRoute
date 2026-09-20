"""Throughput metrics: decisions per second.

Decision throughput = correct decisions / total wall-clock time.
Concurrency level is passed through for documentation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from jevroute.benchmark.recorder import BenchmarkRecord


def compute_throughput_metrics(
    records: "list[BenchmarkRecord]",
    total_wall_clock_s: float,
) -> dict[str, Any]:
    """Compute decision throughput from run records.

    Args:
        records: All BenchmarkRecord objects from the run.
        total_wall_clock_s: Total elapsed seconds (monotonic wall clock).
    """
    correct = sum(
        1 for r in records
        if r.final_action is not None
        and r.ground_truth is not None
        and r.final_action == r.ground_truth.get("action")
    )
    total = len(records)

    if total_wall_clock_s <= 0:
        return {
            "decision_throughput_per_s": None,
            "total_wall_clock_s": None,
        }

    throughput = correct / total_wall_clock_s

    return {
        "decision_throughput_per_s": round(throughput, 4),
        "total_wall_clock_s": round(total_wall_clock_s, 3),
    }
