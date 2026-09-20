"""Latency metrics: p50, p95, p99, min, max, mean, std.

Uses raw observations, never rounded display values.
Percentile calculation uses numpy interpolation (linear) for consistency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from jevroute.benchmark.recorder import BenchmarkRecord


def compute_latency_metrics(records: "list[BenchmarkRecord]") -> dict[str, Any]:
    """Compute latency statistics from raw records.

    Uses total_latency_ms (router + policy). Returns None for all fields if no
    valid observations exist.
    """
    latencies = [
        r.total_latency_ms
        for r in records
        if r.total_latency_ms is not None
    ]

    if not latencies:
        return {
            "min_latency_ms": None,
            "max_latency_ms": None,
            "mean_latency_ms": None,
            "std_latency_ms": None,
            "p50_latency_ms": None,
            "p95_latency_ms": None,
            "p99_latency_ms": None,
        }

    arr = np.array(latencies, dtype=float)

    return {
        "min_latency_ms": round(float(np.min(arr)), 3),
        "max_latency_ms": round(float(np.max(arr)), 3),
        "mean_latency_ms": round(float(np.mean(arr)), 3),
        "std_latency_ms": round(float(np.std(arr)), 3),
        "p50_latency_ms": round(float(np.percentile(arr, 50, method="linear")), 3),
        "p95_latency_ms": round(float(np.percentile(arr, 95, method="linear")), 3),
        "p99_latency_ms": round(float(np.percentile(arr, 99, method="linear")), 3),
    }
