"""MockJevRouter: deterministic router for CI, local development, and testing.

This router must NEVER appear in published benchmark results.
It exists solely to allow the system to run without a real Jev API key.
(JevRoute_MVP_Technical_Architecture.md §37)
"""

from __future__ import annotations

import hashlib
from time import perf_counter

from jevroute.models.decision import (
    Action,
    Category,
    ConfidenceOutput,
    DecisionResult,
    Severity,
)
from jevroute.models.state import ApplicationState

ROUTER_NAME = "mock_jev"
ROUTER_VERSION = "mock-0.1.0"

# Deterministic fixture responses keyed by example_id prefix.
# Any example_id not in this table falls through to the hash-based path.
_FIXTURE_TABLE: dict[str, dict] = {
    "fixture-001": {
        "severity": Severity.P2,
        "category": Category.Billing,
        "policy_violation": False,
        "hallucination_risk": 0.05,
        "tone_risk": 0.02,
        "action": Action.SEND,
    },
    "fixture-002": {
        "severity": Severity.P1,
        "category": Category.Billing,
        "policy_violation": True,
        "hallucination_risk": 0.10,
        "tone_risk": 0.03,
        "action": Action.HOLD,
    },
    "fixture-003": {
        "severity": Severity.P3,
        "category": Category.Bug,
        "policy_violation": False,
        "hallucination_risk": 0.15,
        "tone_risk": 0.08,
        "action": Action.SEND,
    },
    "fixture-004": {
        "severity": Severity.P1,
        "category": Category.Account,
        "policy_violation": False,
        "hallucination_risk": 0.20,
        "tone_risk": 0.05,
        "action": Action.ESCALATE,
    },
    "fixture-005": {
        "severity": Severity.P4,
        "category": Category.Feature,
        "policy_violation": False,
        "hallucination_risk": 0.03,
        "tone_risk": 0.01,
        "action": Action.SEND,
    },
}

# Ordered pools for hash-based deterministic fallback
_SEVERITY_POOL = [Severity.P1, Severity.P2, Severity.P3, Severity.P4]
_CATEGORY_POOL = [Category.Billing, Category.Bug, Category.Feature, Category.Account, Category.Other]
_ACTION_POOL = [Action.SEND, Action.HOLD, Action.ESCALATE]


def _deterministic_fields(example_id: str) -> dict:
    """Produce a deterministic but varied result from example_id hash."""
    digest = int(hashlib.sha256(example_id.encode()).hexdigest(), 16)
    return {
        "severity": _SEVERITY_POOL[digest % len(_SEVERITY_POOL)],
        "category": _CATEGORY_POOL[(digest >> 8) % len(_CATEGORY_POOL)],
        "policy_violation": bool((digest >> 16) % 5 == 0),
        "hallucination_risk": round(((digest >> 24) % 100) / 1000, 3),
        "tone_risk": round(((digest >> 32) % 100) / 1000, 3),
        "action": _ACTION_POOL[(digest >> 40) % len(_ACTION_POOL)],
    }


class MockJevRouter:
    """Deterministic mock router for local development and CI.

    All responses are computed from the example_id without any randomness.
    This guarantees reproducible test results without a real Jev API call.

    IMPORTANT: This router must never be used in published benchmark results.
    """

    async def decide(self, state: ApplicationState) -> DecisionResult:
        t0 = perf_counter()

        fields = _FIXTURE_TABLE.get(state.example_id) or _deterministic_fields(state.example_id)

        elapsed_ms = (perf_counter() - t0) * 1000

        return DecisionResult(
            severity=fields["severity"],
            category=fields["category"],
            policy_violation=fields["policy_violation"],
            hallucination_risk=fields["hallucination_risk"],
            tone_risk=fields["tone_risk"],
            action=fields["action"],
            confidence=ConfidenceOutput(
                severity_confidence=0.90,
                category_confidence=0.92,
                policy_violation_probability=float(fields["policy_violation"]),
                hallucination_probability=fields["hallucination_risk"],
                tone_risk_probability=fields["tone_risk"],
                action_confidence=0.88,
            ),
            router=ROUTER_NAME,
            router_version=ROUTER_VERSION,
            schema_valid=True,
            latency_ms=round(elapsed_ms, 3),
            input_tokens=None,
            output_tokens=None,
            estimated_cost_usd=None,
        )
