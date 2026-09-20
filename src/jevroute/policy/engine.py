"""PolicyEngine: shared, router-independent policy layer.

Every router's output passes through this identical policy engine.
No router receives custom downstream treatment.
(JevRoute_MVP_Technical_Architecture.md §11, Invariant 2)
"""

from __future__ import annotations

from pydantic import BaseModel

from jevroute.models.decision import Action, DecisionResult, Severity

POLICY_VERSION = "support-policy-1.0"

# Threshold above which hallucination risk triggers HOLD.
# Frozen before final benchmark execution; changing this requires a new policy version.
DEFAULT_HALLUCINATION_THRESHOLD: float = 0.8


class PolicyResult(BaseModel):
    """Output of the policy engine: final action plus audit fields."""

    final_action: Action
    policy_version: str
    policy_applied: bool
    override_reason: str | None = None


class PolicyEngine:
    """Applies the shared support-control policy to a DecisionResult.

    Rules (in priority order):
    1. policy_violation         → HOLD
    2. action == ESCALATE       → ESCALATE
    3. severity == P1           → ESCALATE
    4. hallucination_risk >= threshold → HOLD
    5. otherwise                → decision.action

    The policy must be frozen before final benchmark execution.
    Modifying the policy invalidates historical comparisons.
    """

    def __init__(self, hallucination_threshold: float = DEFAULT_HALLUCINATION_THRESHOLD) -> None:
        self.hallucination_threshold = hallucination_threshold
        self.policy_version = POLICY_VERSION

    def apply(self, decision: DecisionResult) -> PolicyResult:
        """Apply policy rules and return the final action."""
        if decision.policy_violation:
            return PolicyResult(
                final_action=Action.HOLD,
                policy_version=self.policy_version,
                policy_applied=True,
                override_reason="policy_violation=True",
            )

        if decision.action == Action.ESCALATE:
            return PolicyResult(
                final_action=Action.ESCALATE,
                policy_version=self.policy_version,
                policy_applied=False,
                override_reason=None,
            )

        if decision.severity == Severity.P1:
            return PolicyResult(
                final_action=Action.ESCALATE,
                policy_version=self.policy_version,
                policy_applied=True,
                override_reason="severity=P1",
            )

        if decision.hallucination_risk >= self.hallucination_threshold:
            return PolicyResult(
                final_action=Action.HOLD,
                policy_version=self.policy_version,
                policy_applied=True,
                override_reason=f"hallucination_risk>={self.hallucination_threshold}",
            )

        return PolicyResult(
            final_action=decision.action,
            policy_version=self.policy_version,
            policy_applied=False,
            override_reason=None,
        )
