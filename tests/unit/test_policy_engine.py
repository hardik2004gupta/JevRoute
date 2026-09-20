"""Unit tests: PolicyEngine rules as specified in the architecture."""

from __future__ import annotations

import pytest

from jevroute.models.decision import Action, Category, DecisionResult, Severity
from jevroute.policy.engine import PolicyEngine


def _make_result(**kwargs) -> DecisionResult:
    defaults = dict(
        severity=Severity.P3,
        category=Category.Other,
        policy_violation=False,
        hallucination_risk=0.1,
        tone_risk=0.05,
        action=Action.SEND,
        router="mock_jev",
        router_version="mock-0.1.0",
    )
    defaults.update(kwargs)
    return DecisionResult(**defaults)


engine = PolicyEngine(hallucination_threshold=0.8)


def test_policy_violation_forces_hold():
    result = _make_result(policy_violation=True, action=Action.SEND)
    policy = engine.apply(result)
    assert policy.final_action == Action.HOLD
    assert policy.policy_applied is True
    assert policy.override_reason == "policy_violation=True"


def test_explicit_escalate_passes_through():
    result = _make_result(action=Action.ESCALATE, policy_violation=False, severity=Severity.P3)
    policy = engine.apply(result)
    assert policy.final_action == Action.ESCALATE
    assert policy.policy_applied is False


def test_p1_severity_escalates():
    result = _make_result(severity=Severity.P1, action=Action.SEND, policy_violation=False)
    policy = engine.apply(result)
    assert policy.final_action == Action.ESCALATE
    assert policy.policy_applied is True
    assert policy.override_reason == "severity=P1"


def test_high_hallucination_risk_holds():
    result = _make_result(hallucination_risk=0.85, action=Action.SEND, policy_violation=False)
    policy = engine.apply(result)
    assert policy.final_action == Action.HOLD
    assert policy.policy_applied is True


def test_hallucination_exactly_at_threshold_holds():
    result = _make_result(hallucination_risk=0.8, action=Action.SEND, policy_violation=False)
    policy = engine.apply(result)
    assert policy.final_action == Action.HOLD


def test_hallucination_below_threshold_does_not_hold():
    result = _make_result(hallucination_risk=0.79, action=Action.SEND, policy_violation=False)
    policy = engine.apply(result)
    assert policy.final_action == Action.SEND


def test_normal_send_passes_through():
    result = _make_result(action=Action.SEND, policy_violation=False, severity=Severity.P3)
    policy = engine.apply(result)
    assert policy.final_action == Action.SEND
    assert policy.policy_applied is False
    assert policy.override_reason is None


def test_policy_version_is_set():
    result = _make_result()
    policy = engine.apply(result)
    assert policy.policy_version == "support-policy-1.0"


def test_policy_violation_overrides_p1_severity():
    """policy_violation takes priority over severity=P1 (both would produce non-SEND)."""
    result = _make_result(policy_violation=True, severity=Severity.P1, action=Action.SEND)
    policy = engine.apply(result)
    # Both result in a non-SEND; policy_violation rule fires first → HOLD
    assert policy.final_action == Action.HOLD
    assert "policy_violation" in (policy.override_reason or "")
