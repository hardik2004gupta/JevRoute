"""Unit tests: ApplicationState and DecisionResult domain models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from jevroute.models.decision import (
    Action,
    Category,
    ConfidenceOutput,
    DecisionResult,
    Severity,
)
from jevroute.models.state import ApplicationState, redact_state


# ---------------------------------------------------------------------------
# ApplicationState
# ---------------------------------------------------------------------------

def test_valid_application_state():
    state = ApplicationState(
        example_id="test-001",
        customer_tier="enterprise",
        product="billing",
        region="EU",
        ticket_subject="Duplicate charge",
        ticket_body="I was charged twice.",
        draft_reply="We are reviewing your account.",
    )
    assert state.example_id == "test-001"
    assert state.customer_tier == "enterprise"


def test_application_state_strips_whitespace():
    state = ApplicationState(
        example_id="  test-002  ",
        customer_tier=" standard ",
        product=" api ",
        region=" US ",
        ticket_subject=" Subject ",
        ticket_body=" Body ",
        draft_reply=" Reply ",
    )
    assert state.example_id == "test-002"
    assert state.customer_tier == "standard"


def test_application_state_missing_required_field():
    with pytest.raises(ValidationError):
        ApplicationState(
            customer_tier="enterprise",
            product="billing",
            region="EU",
            ticket_subject="Subject",
            ticket_body="Body",
            draft_reply="Reply",
        )


def test_redact_state_removes_freetext():
    state = ApplicationState(
        example_id="test-003",
        customer_tier="free",
        product="api",
        region="US",
        ticket_subject="My actual subject",
        ticket_body="Sensitive customer data here",
        draft_reply="Sensitive draft here",
    )
    redacted = redact_state(state)
    assert redacted["example_id"] == "test-003"
    assert redacted["customer_tier"] == "free"
    assert redacted["ticket_subject"] == "[REDACTED]"
    assert redacted["ticket_body"] == "[REDACTED]"
    assert redacted["draft_reply"] == "[REDACTED]"


# ---------------------------------------------------------------------------
# DecisionResult
# ---------------------------------------------------------------------------

def test_valid_decision_result():
    result = DecisionResult(
        severity=Severity.P2,
        category=Category.Billing,
        policy_violation=False,
        hallucination_risk=0.12,
        tone_risk=0.04,
        action=Action.SEND,
        router="mock_jev",
        router_version="mock-0.1.0",
    )
    assert result.severity == Severity.P2
    assert result.action == Action.SEND
    assert result.schema_valid is True


def test_decision_result_invalid_enum():
    with pytest.raises(ValidationError):
        DecisionResult(
            severity="P5",  # invalid
            category=Category.Billing,
            policy_violation=False,
            hallucination_risk=0.1,
            tone_risk=0.0,
            action=Action.SEND,
            router="mock_jev",
            router_version="mock-0.1.0",
        )


def test_decision_result_probability_out_of_range():
    with pytest.raises(ValidationError):
        DecisionResult(
            severity=Severity.P1,
            category=Category.Bug,
            policy_violation=False,
            hallucination_risk=1.5,  # > 1.0, invalid
            tone_risk=0.0,
            action=Action.SEND,
            router="mock_jev",
            router_version="mock-0.1.0",
        )


def test_decision_result_nullable_confidence():
    result = DecisionResult(
        severity=Severity.P3,
        category=Category.Other,
        policy_violation=False,
        hallucination_risk=0.0,
        tone_risk=0.0,
        action=Action.SEND,
        confidence=ConfidenceOutput(),  # all None
        router="rules",
        router_version="rules-1.0",
    )
    assert result.confidence.severity_confidence is None
    assert result.confidence.action_confidence is None


def test_confidence_probability_range():
    with pytest.raises(ValidationError):
        ConfidenceOutput(severity_confidence=1.5)  # > 1.0
