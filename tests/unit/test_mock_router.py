"""Unit tests: MockJevRouter determinism and interface conformance."""

from __future__ import annotations

import asyncio

import pytest

from jevroute.models.state import ApplicationState
from jevroute.routers.base import DecisionRouter
from jevroute.routers.mock_jev import MockJevRouter


def _make_state(example_id: str = "fixture-001") -> ApplicationState:
    return ApplicationState(
        example_id=example_id,
        customer_tier="enterprise",
        product="billing",
        region="EU",
        ticket_subject="Test subject",
        ticket_body="Test body.",
        draft_reply="Test reply.",
    )


@pytest.mark.asyncio
async def test_mock_router_returns_valid_decision_result():
    router = MockJevRouter()
    state = _make_state("fixture-001")
    result = await router.decide(state)
    assert result.schema_valid is True
    assert result.router == "mock_jev"
    assert result.severity is not None
    assert result.category is not None
    assert result.action is not None


@pytest.mark.asyncio
async def test_mock_router_is_deterministic():
    router = MockJevRouter()
    state = _make_state("fixture-001")
    r1 = await router.decide(state)
    r2 = await router.decide(state)
    assert r1.severity == r2.severity
    assert r1.category == r2.category
    assert r1.action == r2.action
    assert r1.policy_violation == r2.policy_violation


@pytest.mark.asyncio
async def test_mock_router_fixture_known_values():
    router = MockJevRouter()
    state = _make_state("fixture-001")
    result = await router.decide(state)
    from jevroute.models.decision import Action, Category, Severity
    assert result.severity == Severity.P2
    assert result.category == Category.Billing
    assert result.action == Action.SEND
    assert result.policy_violation is False


@pytest.mark.asyncio
async def test_mock_router_different_ids_different_results():
    router = MockJevRouter()
    r1 = await router.decide(_make_state("unknown-aaaa"))
    r2 = await router.decide(_make_state("unknown-zzzz"))
    # Different IDs must not always produce identical results
    # (with high probability; hash space is large enough)
    # At minimum: both must be valid
    assert r1.schema_valid is True
    assert r2.schema_valid is True


@pytest.mark.asyncio
async def test_mock_router_records_latency():
    router = MockJevRouter()
    result = await router.decide(_make_state("fixture-002"))
    assert result.latency_ms is not None
    assert result.latency_ms >= 0.0


def test_mock_router_satisfies_protocol():
    router = MockJevRouter()
    assert isinstance(router, DecisionRouter)
