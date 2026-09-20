"""Unit tests: evaluation modules (quality, latency, cost, throughput, calibration)."""

from __future__ import annotations

import pytest

from jevroute.benchmark.recorder import BenchmarkRecord
from jevroute.evaluation.quality import compute_quality_metrics
from jevroute.evaluation.latency import compute_latency_metrics
from jevroute.evaluation.cost import compute_cost_metrics
from jevroute.evaluation.throughput import compute_throughput_metrics
from jevroute.evaluation.calibration import compute_calibration_metrics


def _record(
    example_id: str = "test-001",
    prediction: dict | None = None,
    ground_truth: dict | None = None,
    final_action: str = "SEND",
    schema_valid: bool = True,
    router_latency_ms: float | None = 10.0,
    total_latency_ms: float | None = 12.0,
    input_tokens: int | None = 100,
    output_tokens: int | None = 30,
    estimated_cost_usd: float | None = 0.0005,
    error_type: str | None = None,
    policy_applied: bool = False,
) -> BenchmarkRecord:
    pred = prediction or {
        "severity": "P2",
        "category": "Billing",
        "policy_violation": False,
        "hallucination_risk": 0.05,
        "tone_risk": 0.02,
        "action": "SEND",
    }
    gt = ground_truth or {
        "severity": "P2",
        "category": "Billing",
        "policy_violation": False,
        "hallucination_risk": 0.05,
        "tone_risk": 0.02,
        "action": "SEND",
    }
    return BenchmarkRecord(
        experiment_id="test",
        run_id="test-run",
        example_id=example_id,
        router="test_router",
        router_version="test-v1",
        started_at="2026-01-01T00:00:00+00:00",
        router_latency_ms=router_latency_ms,
        total_latency_ms=total_latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimated_cost_usd,
        schema_valid=schema_valid,
        error_type=error_type,
        prediction=pred if schema_valid else None,
        ground_truth=gt,
        final_action=final_action if schema_valid else None,
        policy_applied=policy_applied,
    )


# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

def test_quality_all_correct():
    records = [_record(final_action="SEND")] * 5
    q = compute_quality_metrics(records)
    assert q["accuracy"] == 1.0
    assert q["correct_decisions"] == 5
    assert q["schema_failure_rate"] == 0.0


def test_quality_all_wrong():
    records = [_record(final_action="HOLD")] * 3  # gt is SEND
    q = compute_quality_metrics(records)
    assert q["accuracy"] == 0.0
    assert q["correct_decisions"] == 0


def test_quality_schema_failure_counted():
    records = [
        _record(final_action="SEND"),
        _record(schema_valid=False, error_type="TIMEOUT"),
    ]
    q = compute_quality_metrics(records)
    assert q["schema_failure_rate"] == 0.5


def test_quality_bad_send_rate():
    # One correct SEND, one wrong SEND (gt=ESCALATE)
    r_correct = _record(final_action="SEND")
    r_wrong = _record(
        final_action="SEND",
        ground_truth={"severity": "P1", "category": "Account", "policy_violation": False,
                      "hallucination_risk": 0.2, "tone_risk": 0.05, "action": "ESCALATE"},
    )
    q = compute_quality_metrics([r_correct, r_wrong])
    assert q["bad_send_rate"] == 0.5


def test_quality_missed_policy_violation():
    r = _record(
        prediction={"severity": "P2", "category": "Billing", "policy_violation": False,
                    "hallucination_risk": 0.05, "tone_risk": 0.02, "action": "SEND"},
        ground_truth={"severity": "P2", "category": "Billing", "policy_violation": True,
                      "hallucination_risk": 0.05, "tone_risk": 0.02, "action": "HOLD"},
    )
    q = compute_quality_metrics([r])
    assert q["missed_policy_violation_rate"] == 1.0


def test_quality_empty_returns_nulls():
    q = compute_quality_metrics([])
    assert q["accuracy"] is None
    assert q["macro_f1"] is None


# ---------------------------------------------------------------------------
# Latency
# ---------------------------------------------------------------------------

def test_latency_percentiles():
    records = [_record(total_latency_ms=float(v)) for v in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]]
    m = compute_latency_metrics(records)
    assert m["p50_latency_ms"] == 55.0
    assert m["min_latency_ms"] == 10.0
    assert m["max_latency_ms"] == 100.0


def test_latency_empty_returns_nulls():
    m = compute_latency_metrics([])
    assert m["p50_latency_ms"] is None


# ---------------------------------------------------------------------------
# Cost
# ---------------------------------------------------------------------------

def test_cost_aggregates_correctly():
    records = [_record(estimated_cost_usd=0.001, input_tokens=100, output_tokens=30)] * 5
    c = compute_cost_metrics(records)
    assert abs(c["total_cost_usd"] - 0.005) < 1e-9
    assert c["input_tokens"] == 500
    assert c["output_tokens"] == 150


def test_cost_per_correct_decision_zero_correct():
    """When no decisions are correct, cost_per_correct is None (not inf or 0)."""
    r = _record(final_action="HOLD", estimated_cost_usd=0.001)  # gt is SEND
    c = compute_cost_metrics([r])
    assert c["cost_per_correct_decision_usd"] is None


def test_cost_empty_returns_nulls():
    c = compute_cost_metrics([])
    assert c["total_cost_usd"] is None


# ---------------------------------------------------------------------------
# Throughput
# ---------------------------------------------------------------------------

def test_throughput_correct_per_second():
    records = [_record(final_action="SEND")] * 4  # all correct
    t = compute_throughput_metrics(records, total_wall_clock_s=2.0)
    assert abs(t["decision_throughput_per_s"] - 2.0) < 0.01


def test_throughput_zero_wall_clock():
    t = compute_throughput_metrics([], total_wall_clock_s=0.0)
    assert t["decision_throughput_per_s"] is None


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------

def test_calibration_brier_score_perfect():
    # Perfect calibration: policy_violation_probability=0.0 for non-violation examples
    r_safe = _record(
        prediction={"severity": "P2", "category": "Billing", "policy_violation": False,
                    "hallucination_risk": 0.0, "tone_risk": 0.01, "action": "SEND",
                    "policy_violation_probability": 0.0},
        ground_truth={"severity": "P2", "category": "Billing", "policy_violation": False,
                      "hallucination_risk": 0.0, "tone_risk": 0.01, "action": "SEND"},
    )
    cal = compute_calibration_metrics([r_safe])
    # brier_score = (0.0 - 0)^2 = 0.0
    assert cal["brier_score"] == 0.0


def test_calibration_null_without_probability_estimates():
    """Routers that do not produce policy_violation_probability return None for calibration."""
    r = _record()  # default prediction has no policy_violation_probability
    cal = compute_calibration_metrics([r])
    assert cal["brier_score"] is None
    assert cal["ece"] is None


def test_calibration_empty_returns_null():
    cal = compute_calibration_metrics([])
    assert cal["brier_score"] is None
    assert cal["ece"] is None


# ---------------------------------------------------------------------------
# Evaluation read-only invariant
# ---------------------------------------------------------------------------

def test_evaluation_does_not_mutate_prediction():
    """Invariant 4: evaluation code must never modify predictions."""
    pred_before = {
        "severity": "P2",
        "category": "Billing",
        "policy_violation": False,
        "hallucination_risk": 0.05,
        "tone_risk": 0.02,
        "action": "SEND",
    }
    import copy
    pred_snapshot = copy.deepcopy(pred_before)

    record = _record(prediction=pred_before)
    compute_quality_metrics([record])
    compute_cost_metrics([record])
    compute_latency_metrics([record])
    compute_calibration_metrics([record])

    assert record.prediction == pred_snapshot, "Evaluation mutated prediction dict!"


# ---------------------------------------------------------------------------
# Phase 5: missed_policy_violation_rate definition regression
# ---------------------------------------------------------------------------

def test_missed_policy_violation_rate_uses_final_action():
    """missed_policy_violation_rate = (GT pv=True AND final_action=SEND) / total GT pv=True.

    This tests the correct routing-outcome definition (not the detection definition).
    A violation that was held/escalated is NOT a miss even if the router didn't flag pv=True.
    A violation that was sent IS a miss regardless of pv flag in prediction.
    """
    # GT pv=True, final_action=SEND → miss
    miss = _record(
        final_action="SEND",
        ground_truth={"severity": "P2", "category": "Billing", "policy_violation": True,
                      "hallucination_risk": 0.0, "tone_risk": 0.0, "action": "SEND"},
    )
    # GT pv=True, final_action=HOLD → NOT a miss (correctly held)
    held = _record(
        final_action="HOLD",
        ground_truth={"severity": "P2", "category": "Billing", "policy_violation": True,
                      "hallucination_risk": 0.0, "tone_risk": 0.0, "action": "HOLD"},
    )
    # GT pv=False, final_action=SEND → not in denominator
    no_pv = _record(final_action="SEND")

    q = compute_quality_metrics([miss, held, no_pv])
    # 1 miss out of 2 GT pv=True examples = 0.5
    assert q["missed_policy_violation_rate"] == 0.5, (
        f"Expected 0.5, got {q['missed_policy_violation_rate']}"
    )


def test_missed_policy_violation_rate_none_when_no_violations():
    """When no GT examples have policy_violation=True, rate must be None (not 0.0 or NaN)."""
    records = [_record(final_action="SEND")] * 5
    q = compute_quality_metrics(records)
    assert q["missed_policy_violation_rate"] is None
