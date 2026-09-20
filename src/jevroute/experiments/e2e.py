"""End-to-end experiment runner.

Extends the baseline benchmark with simulated generation cost to compute:
    control_plane_tax     = control_cost / (control_cost + generation_cost)
    control_latency_share = control_latency / (control_latency + generation_latency)

Generation is simulated by default (no real LLM generation calls) to avoid
coupling the control-plane benchmark to an external generation model.

If generation.real_calls = true in the YAML config, a real LLM call is made.
That mode requires LLM_API_KEY and MODEL_NAME to be configured.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SimulatedGeneration:
    """Simulates a downstream generation step for e2e cost accounting.

    Uses configurable token counts and pricing to represent a typical
    support-reply generation call (e.g., GPT-4o-mini).
    """

    def __init__(
        self,
        input_tokens: int = 400,
        output_tokens: int = 180,
        input_price_per_1k: float = 0.00015,
        output_price_per_1k: float = 0.0006,
        latency_ms: float = 1200.0,
    ) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cost_usd = (
            (input_tokens / 1000) * input_price_per_1k
            + (output_tokens / 1000) * output_price_per_1k
        )
        self.latency_ms = latency_ms

    def as_dict(self) -> dict[str, Any]:
        return {
            "gen_input_tokens": self.input_tokens,
            "gen_output_tokens": self.output_tokens,
            "gen_cost_usd": self.cost_usd,
            "gen_latency_ms": self.latency_ms,
        }


def compute_e2e_metrics(
    control_cost_usd: float | None,
    control_latency_ms: float | None,
    generation: SimulatedGeneration,
) -> dict[str, Any]:
    """Compute end-to-end economics metrics.

    Returns a dict with:
        total_cost_usd
        control_plane_tax           (None if control_cost is None)
        control_latency_share_pct   (None if either latency is None)
    """
    gen_cost = generation.cost_usd
    gen_latency = generation.latency_ms

    total_cost: float | None = None
    cp_tax: float | None = None
    latency_share: float | None = None

    if control_cost_usd is not None:
        total_cost = control_cost_usd + gen_cost
        if total_cost > 0:
            cp_tax = control_cost_usd / total_cost
        else:
            cp_tax = None

    if control_latency_ms is not None:
        total_latency = control_latency_ms + gen_latency
        if total_latency > 0:
            latency_share = control_latency_ms / total_latency
        else:
            latency_share = None

    return {
        "gen_cost_usd": gen_cost,
        "gen_latency_ms": gen_latency,
        "total_cost_usd": total_cost,
        "control_plane_tax": cp_tax,
        "control_latency_share": latency_share,
    }
