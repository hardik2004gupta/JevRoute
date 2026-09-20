"""Unit tests: RulesRouter determinism and interface conformance."""

from __future__ import annotations

import pytest

from jevroute.models.decision import Action, Category, Severity
from jevroute.models.state import ApplicationState
from jevroute.routers.base import DecisionRouter
from jevroute.routers.rules import RulesRouter


def _state(
    example_id: str = "test-001",
    tier: str = "enterprise",
    product: str = "billing",
    region: str = "EU",
    subject: str = "Test subject",
    body: str = "Test body.",
    reply: str = "Test reply.",
) -> ApplicationState:
    return ApplicationState(
        example_id=example_id,
        customer_tier=tier,
        product=product,
        region=region,
        ticket_subject=subject,
        ticket_body=body,
        draft_reply=reply,
    )


@pytest.mark.asyncio
async def test_rules_router_returns_valid_result():
    router = RulesRouter()
    result = await router.decide(_state())
    assert result.schema_valid is True
    assert result.router == "rules"
    assert result.router_version == "rules-v1"
    assert 0.0 <= result.hallucination_risk <= 1.0
    assert 0.0 <= result.tone_risk <= 1.0


@pytest.mark.asyncio
async def test_rules_router_is_deterministic():
    router = RulesRouter()
    state = _state(subject="Duplicate charge", body="I was charged twice.")
    r1 = await router.decide(state)
    r2 = await router.decide(state)
    assert r1.severity == r2.severity
    assert r1.category == r2.category
    assert r1.action == r2.action


@pytest.mark.asyncio
async def test_rules_router_billing_classification():
    router = RulesRouter()
    result = await router.decide(_state(subject="Duplicate charge", body="Charged twice for subscription."))
    assert result.category == Category.Billing


@pytest.mark.asyncio
async def test_rules_router_bug_classification():
    router = RulesRouter()
    result = await router.decide(_state(subject="API 500 error", body="Getting 500 errors from API."))
    assert result.category == Category.Bug


@pytest.mark.asyncio
async def test_rules_router_feature_classification():
    router = RulesRouter()
    result = await router.decide(_state(subject="Feature request: dark mode", body="Would love a dark mode option."))
    assert result.category == Category.Feature


@pytest.mark.asyncio
async def test_rules_router_account_classification():
    router = RulesRouter()
    result = await router.decide(_state(subject="Account locked", body="Cannot login to my account."))
    assert result.category == Category.Account


@pytest.mark.asyncio
async def test_rules_router_p1_severity_team_lockout():
    router = RulesRouter()
    result = await router.decide(_state(
        subject="Team locked out",
        body="My entire team cannot access the platform.",
    ))
    assert result.severity == Severity.P1


@pytest.mark.asyncio
async def test_rules_router_policy_violation_unauthorized():
    router = RulesRouter()
    result = await router.decide(_state(
        subject="Unauthorized charge",
        body="There is a charge I did not authorize.",
        reply="We will issue a refund immediately.",
    ))
    assert result.policy_violation is True


@pytest.mark.asyncio
async def test_rules_router_feature_request_p4():
    router = RulesRouter()
    result = await router.decide(_state(
        subject="Feature request: dark mode",
        body="Would love a dark mode option.",
    ))
    assert result.severity == Severity.P4


@pytest.mark.asyncio
async def test_rules_router_no_input_output_tokens():
    router = RulesRouter()
    result = await router.decide(_state())
    # Rules router has no API cost
    assert result.input_tokens is None
    assert result.output_tokens is None
    assert result.estimated_cost_usd == 0.0


@pytest.mark.asyncio
async def test_rules_router_records_latency():
    router = RulesRouter()
    result = await router.decide(_state())
    assert result.latency_ms is not None
    assert result.latency_ms >= 0.0


def test_rules_router_satisfies_protocol():
    router = RulesRouter()
    assert isinstance(router, DecisionRouter)
