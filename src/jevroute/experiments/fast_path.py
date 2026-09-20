"""Fast-path gate: deterministic pre-gate for the fastpath-v1 experiment.

Compares:
    Always Jev  — every request routed to Jev
vs
    Fast Gate + Jev — deterministic bypass for unambiguous requests

The gate itself must be deterministic and its latency must be recorded separately.
Its contribution must not be attributed to Jev's performance.
"""

from __future__ import annotations

import hashlib
import logging
from time import perf_counter
from typing import Any

from jevroute.models.state import ApplicationState

logger = logging.getLogger(__name__)

# Exact-match bypass cache: {normalized_hash → fixed_decision}
# Only populated for fixed-format/known-good templates.
_EXACT_MATCH_CACHE: dict[str, dict[str, Any]] = {}

# Customer tier × product combinations with fixed policy outcomes
_FIXED_POLICY_MAP: dict[tuple[str, str], str] = {
    ("free", "feature"): "HOLD",  # Free-tier feature requests always held
}


def _normalize_subject(subject: str) -> str:
    return subject.strip().lower()


def _state_hash(state: ApplicationState) -> str:
    canonical = f"{state.customer_tier}|{state.product}|{_normalize_subject(state.ticket_subject)}"
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


class FastGateResult:
    """Result from the fast gate evaluation."""

    __slots__ = ("bypassed", "bypass_reason", "bypass_action", "gate_latency_ms")

    def __init__(
        self,
        bypassed: bool,
        bypass_reason: str | None,
        bypass_action: str | None,
        gate_latency_ms: float,
    ) -> None:
        self.bypassed = bypassed
        self.bypass_reason = bypass_reason
        self.bypass_action = bypass_action
        self.gate_latency_ms = gate_latency_ms


class FastGate:
    """Deterministic pre-gate for the fast-path experiment.

    The gate NEVER uses semantic inference or ML. It is a pure function of
    structured metadata. Its own latency is measured and reported separately.

    Rule types (from fast_path.yaml):
        1. exact_match:     deterministic hash matches a known template
        2. empty_request:   ticket body is empty or minimal
        3. explicit_action: tier × product pair maps to a fixed action
    """

    def evaluate(self, state: ApplicationState) -> FastGateResult:
        t_start = perf_counter()

        # Rule 1: exact match
        state_key = _state_hash(state)
        if state_key in _EXACT_MATCH_CACHE:
            return FastGateResult(
                bypassed=True,
                bypass_reason="exact_match",
                bypass_action=_EXACT_MATCH_CACHE[state_key].get("action", "HOLD"),
                gate_latency_ms=(perf_counter() - t_start) * 1000,
            )

        # Rule 2: empty/minimal request
        body = (state.ticket_body or "").strip()
        if len(body) < 5:
            return FastGateResult(
                bypassed=True,
                bypass_reason="empty_request",
                bypass_action="HOLD",
                gate_latency_ms=(perf_counter() - t_start) * 1000,
            )

        # Rule 3: explicit policy mapping
        policy_key = (state.customer_tier.lower(), state.product.lower())
        if policy_key in _FIXED_POLICY_MAP:
            return FastGateResult(
                bypassed=True,
                bypass_reason="explicit_action",
                bypass_action=_FIXED_POLICY_MAP[policy_key],
                gate_latency_ms=(perf_counter() - t_start) * 1000,
            )

        # Not bypassed — route to Jev
        return FastGateResult(
            bypassed=False,
            bypass_reason=None,
            bypass_action=None,
            gate_latency_ms=(perf_counter() - t_start) * 1000,
        )

    def register_template(self, state_hash: str, action: str) -> None:
        """Register a deterministic hash → action mapping (for testing)."""
        _EXACT_MATCH_CACHE[state_hash] = {"action": action}
