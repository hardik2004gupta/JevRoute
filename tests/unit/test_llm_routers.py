"""Unit tests: LLMSingleRouter and LLMParallelRouter with mocked provider.

All tests run without network access using FakeModelClient.
"""

from __future__ import annotations

import pytest

from jevroute.models.decision import Action, Category, Severity
from jevroute.models.state import ApplicationState
from jevroute.routers.base import DecisionRouter
from jevroute.routers.llm_provider import (
    FakeModelClient,
    InvalidResponseError,
    ModelResponse,
    RateLimitError,
    RouterError,
    SchemaValidationError,
    TimeoutError,
)
from jevroute.routers.llm_single import LLMSingleRouter
from jevroute.routers.llm_parallel import LLMParallelRouter


_VALID_JSON = (
    '{"severity":"P2","category":"Billing","policy_violation":false,'
    '"hallucination_risk":0.05,"tone_risk":0.02,"action":"SEND"}'
)

_VALID_RESPONSE = ModelResponse(
    content=_VALID_JSON,
    input_tokens=200,
    output_tokens=40,
    model="fake-model",
)


def _state(example_id: str = "test-001") -> ApplicationState:
    return ApplicationState(
        example_id=example_id,
        customer_tier="enterprise",
        product="billing",
        region="EU",
        ticket_subject="Duplicate charge",
        ticket_body="I was charged twice.",
        draft_reply="We are reviewing your transaction.",
    )


# ---------------------------------------------------------------------------
# LLMSingleRouter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_single_valid_response():
    client = FakeModelClient(default_response=_VALID_RESPONSE)
    router = LLMSingleRouter(client=client)
    result = await router.decide(_state())
    assert result.severity == Severity.P2
    assert result.category == Category.Billing
    assert result.action == Action.SEND
    assert result.schema_valid is True
    assert result.router == "llm_single"


@pytest.mark.asyncio
async def test_llm_single_records_tokens_and_cost():
    client = FakeModelClient(default_response=_VALID_RESPONSE)
    router = LLMSingleRouter(
        client=client,
        model_input_price_per_1k=0.001,
        model_output_price_per_1k=0.002,
    )
    result = await router.decide(_state())
    assert result.input_tokens == 200
    assert result.output_tokens == 40
    assert result.estimated_cost_usd is not None
    assert result.estimated_cost_usd > 0


@pytest.mark.asyncio
async def test_llm_single_malformed_json_raises():
    bad = ModelResponse(content="not json at all", input_tokens=10, output_tokens=5)
    client = FakeModelClient(responses=[bad])
    router = LLMSingleRouter(client=client)
    with pytest.raises(RouterError):  # InvalidResponseError is a RouterError
        await router.decide(_state())


@pytest.mark.asyncio
async def test_llm_single_missing_field_raises():
    bad = ModelResponse(content='{"severity":"P2","category":"Billing"}', input_tokens=10, output_tokens=5)
    client = FakeModelClient(responses=[bad])
    router = LLMSingleRouter(client=client)
    with pytest.raises(SchemaValidationError):
        await router.decide(_state())


@pytest.mark.asyncio
async def test_llm_single_invalid_enum_raises():
    bad = ModelResponse(
        content='{"severity":"INVALID","category":"Billing","policy_violation":false,'
                '"hallucination_risk":0.1,"tone_risk":0.1,"action":"SEND"}',
        input_tokens=10,
        output_tokens=5,
    )
    client = FakeModelClient(responses=[bad])
    router = LLMSingleRouter(client=client)
    with pytest.raises(SchemaValidationError):
        await router.decide(_state())


@pytest.mark.asyncio
async def test_llm_single_timeout_propagates():
    client = FakeModelClient(responses=[TimeoutError("timed out"), TimeoutError("timed out again")])
    router = LLMSingleRouter(client=client)
    from jevroute.routers.llm_provider import RouterError
    with pytest.raises(RouterError) as exc_info:
        await router.decide(_state())
    assert exc_info.value.error_type == "TIMEOUT"


@pytest.mark.asyncio
async def test_llm_single_rate_limit_retried():
    # First call rate limited, second succeeds
    client = FakeModelClient(responses=[RateLimitError(), _VALID_RESPONSE])
    router = LLMSingleRouter(client=client)
    result = await router.decide(_state())
    assert result.schema_valid is True


@pytest.mark.asyncio
async def test_llm_single_satisfies_protocol():
    router = LLMSingleRouter(client=FakeModelClient())
    assert isinstance(router, DecisionRouter)


# ---------------------------------------------------------------------------
# LLMParallelRouter
# ---------------------------------------------------------------------------

def _parallel_fake_client() -> FakeModelClient:
    """Returns a fake client with separate valid responses for each dimension."""
    responses = [
        ModelResponse(content='{"severity":"P2"}', input_tokens=50, output_tokens=5, model="fake"),
        ModelResponse(content='{"category":"Billing"}', input_tokens=50, output_tokens=5, model="fake"),
        ModelResponse(content='{"policy_violation":false}', input_tokens=50, output_tokens=5, model="fake"),
        ModelResponse(content='{"hallucination_risk":0.05}', input_tokens=50, output_tokens=5, model="fake"),
        ModelResponse(content='{"tone_risk":0.02}', input_tokens=50, output_tokens=5, model="fake"),
        ModelResponse(content='{"action":"SEND"}', input_tokens=50, output_tokens=5, model="fake"),
    ]
    return FakeModelClient(responses=responses)


@pytest.mark.asyncio
async def test_llm_parallel_valid_responses():
    client = _parallel_fake_client()
    router = LLMParallelRouter(client=client)
    result = await router.decide(_state())
    assert result.severity == Severity.P2
    assert result.category == Category.Billing
    assert result.action == Action.SEND
    assert result.schema_valid is True
    assert result.router == "llm_parallel"


@pytest.mark.asyncio
async def test_llm_parallel_aggregates_all_tokens():
    """Parallel cost is the SUM across all 6 calls, not just the most expensive."""
    client = _parallel_fake_client()
    router = LLMParallelRouter(
        client=client,
        model_input_price_per_1k=0.001,
        model_output_price_per_1k=0.002,
    )
    result = await router.decide(_state())
    # 6 calls × (50 input + 5 output) = 300 input, 30 output
    assert result.input_tokens == 300
    assert result.output_tokens == 30
    assert result.estimated_cost_usd is not None
    assert result.estimated_cost_usd > 0


@pytest.mark.asyncio
async def test_llm_parallel_one_failed_call_raises():
    """A failure in any parallel call must raise — not silently produce partial results.

    Queue ordering: severity(0), category-attempt1(1), policy(2), hallucination(3),
    tone(4), action(5), category-retry(6). After all other tasks complete, the category
    retry fires and also fails, causing the router to raise.
    """
    responses: list = [
        ModelResponse(content='{"severity":"P2"}', input_tokens=50, output_tokens=5),
        TimeoutError("category call first attempt"),  # attempt 0 fails
        ModelResponse(content='{"policy_violation":false}', input_tokens=50, output_tokens=5),
        ModelResponse(content='{"hallucination_risk":0.05}', input_tokens=50, output_tokens=5),
        ModelResponse(content='{"tone_risk":0.02}', input_tokens=50, output_tokens=5),
        ModelResponse(content='{"action":"SEND"}', input_tokens=50, output_tokens=5),
        TimeoutError("category call retry"),  # attempt 1 also fails
    ]
    client = FakeModelClient(responses=responses)
    router = LLMParallelRouter(client=client)
    with pytest.raises(RouterError):  # SchemaValidationError wrapping the dimension failure
        await router.decide(_state())


@pytest.mark.asyncio
async def test_llm_parallel_satisfies_protocol():
    router = LLMParallelRouter(client=FakeModelClient())
    assert isinstance(router, DecisionRouter)
