"""Quality metrics: accuracy, precision, recall, F1, safety-sensitive rates.

Evaluation is read-only: this module must never modify prediction values.
(JevRoute Invariant 4)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score

if TYPE_CHECKING:
    from jevroute.benchmark.recorder import BenchmarkRecord


def compute_quality_metrics(records: "list[BenchmarkRecord]") -> dict[str, Any]:
    """Compute quality metrics from raw benchmark records.

    Evaluation is read-only: records and predictions are never modified here.
    """
    total = len(records)
    schema_failures = sum(1 for r in records if not r.schema_valid)
    valid_records = [r for r in records if r.schema_valid and r.prediction and r.ground_truth]

    n_valid = len(valid_records)
    schema_failure_rate = schema_failures / total if total > 0 else None

    if n_valid == 0:
        return {
            "decisions": n_valid,
            "correct_decisions": 0,
            "accuracy": None,
            "macro_f1": None,
            "send_accuracy": None,
            "hold_accuracy": None,
            "escalate_accuracy": None,
            "bad_send_rate": None,
            "over_escalation_rate": None,
            "missed_policy_violation_rate": None,
            "schema_failure_rate": schema_failure_rate,
        }

    # Final action comparison (after policy engine)
    y_pred = [r.final_action for r in valid_records if r.final_action]
    y_true = [r.ground_truth["action"] for r in valid_records if r.final_action]  # type: ignore[index]

    n = len(y_true)
    correct = sum(1 for p, t in zip(y_pred, y_true) if p == t)
    accuracy = correct / n if n > 0 else None

    actions = ["SEND", "HOLD", "ESCALATE"]
    macro_f1: float | None = None
    send_acc: float | None = None
    hold_acc: float | None = None
    esc_acc: float | None = None

    if n > 1:
        try:
            macro_f1 = float(
                f1_score(y_true, y_pred, labels=actions, average="macro", zero_division=0)
            )
        except Exception:
            macro_f1 = None

        for label, attr in [("SEND", "send_accuracy"), ("HOLD", "hold_accuracy"), ("ESCALATE", "escalate_accuracy")]:
            label_indices = [i for i, t in enumerate(y_true) if t == label]
            if label_indices:
                label_correct = sum(1 for i in label_indices if y_pred[i] == y_true[i])
                val = label_correct / len(label_indices)
                if label == "SEND":
                    send_acc = val
                elif label == "HOLD":
                    hold_acc = val
                else:
                    esc_acc = val

    # Safety-sensitive metrics
    # bad-send rate: predicted SEND but ground truth is HOLD or ESCALATE
    bad_send = sum(1 for p, t in zip(y_pred, y_true) if p == "SEND" and t in ("HOLD", "ESCALATE"))
    bad_send_rate = bad_send / n if n > 0 else None

    # over-escalation rate: predicted ESCALATE but ground truth is SEND or HOLD
    over_esc = sum(1 for p, t in zip(y_pred, y_true) if p == "ESCALATE" and t in ("SEND", "HOLD"))
    over_escalation_rate = over_esc / n if n > 0 else None

    # missed policy violation rate: ground truth policy_violation=True but predicted policy_violation=False
    pv_true = [r for r in valid_records if r.ground_truth and r.ground_truth.get("policy_violation")]  # type: ignore[union-attr]
    pv_missed = sum(
        1 for r in pv_true
        if r.prediction and not r.prediction.get("policy_violation")
    )
    missed_policy_violation_rate = pv_missed / len(pv_true) if pv_true else None

    return {
        "decisions": n,
        "correct_decisions": correct,
        "accuracy": round(accuracy, 4) if accuracy is not None else None,
        "macro_f1": round(macro_f1, 4) if macro_f1 is not None else None,
        "send_accuracy": round(send_acc, 4) if send_acc is not None else None,
        "hold_accuracy": round(hold_acc, 4) if hold_acc is not None else None,
        "escalate_accuracy": round(esc_acc, 4) if esc_acc is not None else None,
        "bad_send_rate": round(bad_send_rate, 4) if bad_send_rate is not None else None,
        "over_escalation_rate": round(over_escalation_rate, 4) if over_escalation_rate is not None else None,
        "missed_policy_violation_rate": round(missed_policy_violation_rate, 4) if missed_policy_violation_rate is not None else None,
        "schema_failure_rate": round(schema_failure_rate, 4) if schema_failure_rate is not None else None,
    }
