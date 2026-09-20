"""Cost metrics: total cost, cost per 1K decisions, cost per correct decision.

Costs are never rounded in internal calculations.
Cost per correct decision handles zero-correct-decisions explicitly.
(JevRoute_MVP_Technical_Architecture.md §16)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from jevroute.benchmark.recorder import BenchmarkRecord


def compute_cost_metrics(records: "list[BenchmarkRecord]") -> dict[str, Any]:
    """Compute aggregate cost metrics from raw records.

    A record with None estimated_cost_usd is excluded from cost calculations
    (e.g. RulesRouter with zero cost is recorded as 0.0, not None).
    """
    cost_records = [
        r for r in records
        if r.estimated_cost_usd is not None
    ]

    if not cost_records:
        return {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "total_cost_usd": None,
            "cost_per_1k_decisions_usd": None,
            "cost_per_correct_decision_usd": None,
        }

    total_input = sum(r.input_tokens or 0 for r in records)
    total_output = sum(r.output_tokens or 0 for r in records)
    total_cost: float = sum(r.estimated_cost_usd for r in cost_records)  # type: ignore[misc]

    n_decisions = len(records)
    cost_per_1k = (total_cost / n_decisions * 1000) if n_decisions > 0 else None

    correct_decisions = sum(
        1 for r in records
        if r.final_action is not None
        and r.ground_truth is not None
        and r.final_action == r.ground_truth.get("action")
    )

    if correct_decisions > 0:
        cost_per_correct = total_cost / correct_decisions
    else:
        cost_per_correct = None  # Explicitly None — not zero — to avoid misleading metrics

    return {
        "input_tokens": total_input or None,
        "output_tokens": total_output or None,
        "total_tokens": (total_input + total_output) or None,
        "total_cost_usd": total_cost,
        "cost_per_1k_decisions_usd": cost_per_1k,
        "cost_per_correct_decision_usd": cost_per_correct,
    }
