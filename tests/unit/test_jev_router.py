"""Unit tests: JevRouter with injected FakeJevClient.

All tests run without network access.
"""

from __future__ import annotations

import pytest

from jevroute.models.decision import Action, Category, Severity
from jevroute.models.state import ApplicationState
from jevroute.routers.base import DecisionRouter
from jevroute.routers.jev import ROUTER_NAME, ROUTER_VERSION, JevRouter
from jevroute.routers.jev_client import (
    FakeJevClient,
    JevResponse,
    _parse_jev_json,
)
from jevroute.routers.llm_provider import (
    AuthenticationError,
    InvalidResponseError,
    NetworkError,
    ProviderError,
    RateLimitError,
    RouterError,
    SchemaValidationError,
    TimeoutError,
)


_VALID_RESPONSE = JevResponse(
    severity="P2",
    category="Billing",
    policy_violation=False,
    hallucination_risk=0.08,
    tone_risk=0.03,
    action="SEND",
    severity_confidence=0.91,
    category_confidence=0.96,
    action_confidence=0.88,
    input_tokens=150,
    output_tokens=0,
    model="jev-support-v1",
)


def _state(example_id: str = "test-001") -> ApplicationState:
    return ApplicationState(
        example_id=example_id,
        customer_tier="enterprise",
        product="billing",
        region="EU",
        ticket_subject="Duplicate charge on invoice",
        ticket_body="I was charged twice for the same item.",
        draft_reply="We are reviewing your transaction history.",
    )


# ── JevRouter — happy path ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_jev_router_valid_response():
    client = FakeJevClient(default_response=_VALID_RESPONSE)
    router = JevRouter(client=client)
    result = await router.decide(_state())
    assert result.severity == Severity.P2
    assert result.category == Category.Billing
    assert result.action == Action.SEND
    assert result.schema_valid is True
    assert result.router == ROUTER_NAME
    assert result.router_version == ROUTER_VERSION


@pytest.mark.asyncio
async def test_jev_router_normalizes_confidence():
    client = FakeJevClient(default_response=_VALID_RESPONSE)
    router = JevRouter(client=client)
    result = await router.decide(_state())
    assert result.confidence.severity_confidence == pytest.approx(0.91)
    assert result.confidence.category_confidence == pytest.approx(0.96)
    assert result.confidence.action_confidence == pytest.approx(0.88)


@pytest.mark.asyncio
async def test_jev_router_records_latency():
    client = FakeJevClient(default_response=_VALID_RESPONSE)
    router = JevRouter(client=client)
    result = await router.decide(_state())
    assert result.latency_ms is not None
    assert result.latency_ms >= 0.0


@pytest.mark.asyncio
async def test_jev_router_records_tokens():
    client = FakeJevClient(default_response=_VALID_RESPONSE)
    router = JevRouter(client=client)
    result = await router.decide(_state())
    assert result.input_tokens == 150
    assert result.output_tokens == 0


@pytest.mark.asyncio
async def test_jev_router_computes_cost():
    client = FakeJevClient(default_response=_VALID_RESPONSE)
    router = JevRouter(
        client=client,
        model_input_price_per_1k=0.001,
        model_output_price_per_1k=0.002,
    )
    result = await router.decide(_state())
    assert result.estimated_cost_usd is not None
    # 150 input tokens at $0.001/1k = $0.00015
    assert result.estimated_cost_usd == pytest.approx(0.00015, abs=1e-9)


@pytest.mark.asyncio
async def test_jev_router_zero_cost_when_price_not_set():
    client = FakeJevClient(default_response=_VALID_RESPONSE)
    router = JevRouter(client=client)  # prices default to 0.0
    result = await router.decide(_state())
    assert result.estimated_cost_usd == pytest.approx(0.0)


# ── JevRouter — error handling ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_jev_router_timeout_raises():
    client = FakeJevClient(responses=[TimeoutError("request timed out"), TimeoutError("retry timed out")])
    router = JevRouter(client=client)
    with pytest.raises(RouterError) as exc_info:
        await router.decide(_state())
    assert exc_info.value.error_type == "TIMEOUT"


@pytest.mark.asyncio
async def test_jev_router_rate_limit_retried():
    client = FakeJevClient(responses=[RateLimitError("rate limited"), _VALID_RESPONSE])
    router = JevRouter(client=client)
    result = await router.decide(_state())
    assert result.schema_valid is True


@pytest.mark.asyncio
async def test_jev_router_rate_limit_exhausted():
    client = FakeJevClient(responses=[RateLimitError(), RateLimitError()])
    router = JevRouter(client=client)
    with pytest.raises(RouterError) as exc_info:
        await router.decide(_state())
    assert exc_info.value.error_type == "RATE_LIMIT"


@pytest.mark.asyncio
async def test_jev_router_authentication_failure_not_retried():
    client = FakeJevClient(responses=[AuthenticationError("invalid key")])
    router = JevRouter(client=client)
    with pytest.raises(RouterError) as exc_info:
        await router.decide(_state())
    assert exc_info.value.error_type == "AUTHENTICATION"


@pytest.mark.asyncio
async def test_jev_router_network_error_propagates():
    client = FakeJevClient(responses=[NetworkError("connection refused")])
    router = JevRouter(client=client)
    with pytest.raises(RouterError) as exc_info:
        await router.decide(_state())
    assert exc_info.value.error_type == "NETWORK"


@pytest.mark.asyncio
async def test_jev_router_invalid_response_propagates():
    client = FakeJevClient(responses=[InvalidResponseError("not JSON")])
    router = JevRouter(client=client)
    with pytest.raises(RouterError):
        await router.decide(_state())


# ── JevRouter — normalization ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_jev_router_all_actions():
    for action_str, action_enum in [("SEND", Action.SEND), ("HOLD", Action.HOLD), ("ESCALATE", Action.ESCALATE)]:
        resp = JevResponse(
            severity="P3", category="Bug", policy_violation=False,
            hallucination_risk=0.1, tone_risk=0.1, action=action_str,
        )
        client = FakeJevClient(responses=[resp])
        router = JevRouter(client=client)
        result = await router.decide(_state())
        assert result.action == action_enum


# ── JevClient — response parsing ──────────────────────────────────────────────

def test_parse_jev_json_valid():
    payload = (
        '{"severity":"P1","category":"Bug","policy_violation":true,'
        '"hallucination_risk":0.75,"tone_risk":0.3,"action":"ESCALATE"}'
    )
    resp = _parse_jev_json(payload)
    assert resp.severity == "P1"
    assert resp.policy_violation is True
    assert resp.action == "ESCALATE"


def test_parse_jev_json_missing_field():
    from jevroute.routers.llm_provider import SchemaValidationError
    payload = '{"severity":"P2","category":"Billing"}'
    with pytest.raises(SchemaValidationError):
        _parse_jev_json(payload)


def test_parse_jev_json_invalid_severity():
    from jevroute.routers.llm_provider import SchemaValidationError
    payload = (
        '{"severity":"P0","category":"Billing","policy_violation":false,'
        '"hallucination_risk":0.1,"tone_risk":0.1,"action":"SEND"}'
    )
    with pytest.raises(SchemaValidationError):
        _parse_jev_json(payload)


def test_parse_jev_json_non_json():
    from jevroute.routers.llm_provider import InvalidResponseError
    with pytest.raises(InvalidResponseError):
        _parse_jev_json("not valid json")


# ── Protocol satisfaction ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_jev_router_satisfies_protocol():
    router = JevRouter(client=FakeJevClient(default_response=_VALID_RESPONSE))
    assert isinstance(router, DecisionRouter)
