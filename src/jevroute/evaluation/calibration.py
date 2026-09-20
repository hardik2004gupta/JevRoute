"""Calibration metrics: Brier Score, Expected Calibration Error.

Only participates in calibration analysis when native probabilities exist.
Missing probabilities are represented as None, never as zero.
(JevRoute_MVP_Technical_Architecture.md §20)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from jevroute.benchmark.recorder import BenchmarkRecord


def _brier_score(probs: list[float], actuals: list[int]) -> float:
    """Mean squared error between predicted probabilities and binary outcomes."""
    p = np.array(probs, dtype=float)
    a = np.array(actuals, dtype=float)
    return float(np.mean((p - a) ** 2))


def _expected_calibration_error(
    probs: list[float], actuals: list[int], n_bins: int = 10
) -> float:
    """Expected Calibration Error via equal-width binning."""
    p = np.array(probs, dtype=float)
    a = np.array(actuals, dtype=float)
    n = len(p)
    if n == 0:
        return float("nan")

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (p >= lo) & (p < hi)
        if not np.any(mask):
            continue
        bin_p = p[mask]
        bin_a = a[mask]
        ece += (len(bin_p) / n) * abs(np.mean(bin_p) - np.mean(bin_a))
    return float(ece)


def compute_calibration_metrics(records: "list[BenchmarkRecord]") -> dict[str, Any]:
    """Compute calibration metrics for routers that produce native probabilities.

    Only records with non-None action probabilities are included.
    RulesRouter and other deterministic routers return brier_score=None, ece=None.
    """
    # Extract records where we have policy_violation_probability from the router
    # (this would come from ConfidenceOutput when a router provides it)
    # For Phase 2: only MockJevRouter provides these; LLM/Rules do not.
    # We look at the prediction field for explicit probability fields if present.

    brier_samples: list[tuple[float, int]] = []

    for r in records:
        if not r.schema_valid or not r.prediction or not r.ground_truth:
            continue
        # hallucination_risk as a probability prediction
        pred_hr = r.prediction.get("hallucination_risk")
        true_pv = int(r.ground_truth.get("policy_violation", False))
        if pred_hr is not None:
            brier_samples.append((float(pred_hr), true_pv))

    if not brier_samples:
        return {
            "brier_score": None,
            "ece": None,
        }

    probs = [s[0] for s in brier_samples]
    actuals = [s[1] for s in brier_samples]

    bs = _brier_score(probs, actuals)
    ece = _expected_calibration_error(probs, actuals)

    return {
        "brier_score": round(bs, 4),
        "ece": round(ece, 4),
    }
