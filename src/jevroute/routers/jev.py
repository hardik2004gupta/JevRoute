"""JevRouter: isolated adapter around the Jev decision API.

Architecture:
    ApplicationState
        ↓ _build_payload()
    dict (routing state — no ground truth, no benchmark metadata)
        ↓ JevClient.decide()
    JevResponse
        ↓ _normalize()
    DecisionResult

No policy logic, benchmark aggregation, or evaluation code belongs here.
All Jev-specific transport and serialization stays inside JevClient.

Versioning:
    ROUTER_NAME     = "jev"
    ROUTER_VERSION  = "jev-adapter-0.1"
    JEV_SCHEMA_VERSION  = "jev-support-v1"   (question/context definition version)
"""

from __future__ import annotations

import asyncio
import logging
from time import perf_counter

from jevroute.models.decision import (
    Action,
    Category,
    ConfidenceOutput,
    DecisionResult,
    Severity,
)
from jevroute.models.state import ApplicationState
from jevroute.routers.jev_client import (
    JEV_SCHEMA_VERSION,
    FakeJevClient,
    JevClient,
    JevResponse,
    _parse_jev_json,
)
from jevroute.routers.llm_provider import (
    RateLimitError,
    RouterError,
    SchemaValidationError,
)

logger = logging.getLogger(__name__)

ROUTER_NAME = "jev"
ROUTER_VERSION = "jev-adapter-0.1"

_MAX_ATTEMPTS = 2
_RETRY_BACKOFF_S = 0.25

# OQ-002: pricing model unknown — configurable per-token defaults (0.0 = no charge measured).
# Update when real Jev pricing is confirmed.
_DEFAULT_INPUT_PRICE_PER_1K: float = 0.0
_DEFAULT_OUTPUT_PRICE_PER_1K: float = 0.0


def _build_payload(state: ApplicationState) -> dict:
    """Transform ApplicationState into the Jev request payload.

    Only application-level routing context is included.
    No ground truth labels, benchmark IDs, or evaluation metadata.
    """
    return {
        "example_id": state.example_id,
        "customer_tier": state.customer_tier,
        "product": state.product,
        "region": state.region,
        "ticket_subject": state.ticket_subject,
        "ticket_body": state.ticket_body,
        "draft_reply": state.draft_reply,
        "jev_schema_version": JEV_SCHEMA_VERSION,
    }


def _normalize(resp: JevResponse, input_tokens: int, output_tokens: int, cost_usd: float) -> DecisionResult:
    """Normalize a JevResponse into a DecisionResult."""
    return DecisionResult(
        severity=Severity(resp.severity),
        category=Category(resp.category),
        policy_violation=resp.policy_violation,
        hallucination_risk=resp.hallucination_risk,
        tone_risk=resp.tone_risk,
        action=Action(resp.action),
        confidence=ConfidenceOutput(
            severity_confidence=resp.severity_confidence,
            category_confidence=resp.category_confidence,
            action_confidence=resp.action_confidence,
        ),
        router=ROUTER_NAME,
        router_version=ROUTER_VERSION,
        schema_valid=True,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=cost_usd,
    )


class JevRouter:
    """Isolated adapter for the Jev decision API.

    Conforms to the DecisionRouter protocol:
        async def decide(state: ApplicationState) -> DecisionResult

    The client dependency can be injected for testing (FakeJevClient).
    In production, use HttpxJevClient built from environment settings.
    """

    def __init__(
        self,
        client: JevClient,
        *,
        model_input_price_per_1k: float = _DEFAULT_INPUT_PRICE_PER_1K,
        model_output_price_per_1k: float = _DEFAULT_OUTPUT_PRICE_PER_1K,
        timeout_s: float = 10.0,
    ) -> None:
        self._client = client
        self._input_price = model_input_price_per_1k
        self._output_price = model_output_price_per_1k
        self._timeout_s = timeout_s

    async def decide(self, state: ApplicationState) -> DecisionResult:
        """Run the Jev decision API and return a normalized DecisionResult.

        Retries up to _MAX_ATTEMPTS times on transient failures (RATE_LIMIT only).
        Raises RouterError on exhaustion or non-retryable failures.
        Latency is recorded inside the returned DecisionResult.
        """
        payload = _build_payload(state)
        t_start = perf_counter()

        total_input_tokens = 0
        total_output_tokens = 0
        last_exc: RouterError | None = None

        for attempt in range(_MAX_ATTEMPTS):
            if attempt > 0:
                await asyncio.sleep(_RETRY_BACKOFF_S)

            try:
                resp: JevResponse = await self._client.decide(
                    payload, timeout_s=self._timeout_s
                )
            except RateLimitError as exc:
                logger.warning(
                    "Jev rate limit on attempt %d/%d: %s",
                    attempt + 1, _MAX_ATTEMPTS, exc,
                )
                last_exc = exc
                continue
            except RouterError:
                raise
            except Exception as exc:
                from jevroute.routers.llm_provider import RouterError as RE
                raise RE(f"Jev unexpected error: {exc}") from exc

            # Success path
            in_tok = resp.input_tokens or 0
            out_tok = resp.output_tokens or 0
            total_input_tokens += in_tok
            total_output_tokens += out_tok

            cost = (
                (total_input_tokens / 1000) * self._input_price
                + (total_output_tokens / 1000) * self._output_price
            )

            latency_ms = (perf_counter() - t_start) * 1000
            result = _normalize(resp, total_input_tokens, total_output_tokens, cost)
            result = result.model_copy(update={"latency_ms": round(latency_ms, 3), "retry_count": attempt})
            logger.debug(
                "Jev decision complete | router_version=%s latency_ms=%.1f tokens_in=%d tokens_out=%d cost=%.6f",
                ROUTER_VERSION, latency_ms, total_input_tokens, total_output_tokens, cost,
            )
            return result

        # All retries exhausted
        if last_exc is not None:
            raise last_exc
        raise RouterError("Jev: all attempts exhausted with no recoverable error")

    @classmethod
    def from_settings(cls) -> "JevRouter":
        """Build a JevRouter from application settings.

        Returns a FakeJevClient-based router if JEV_API_KEY is not configured.
        This allows local development and CI to proceed without real credentials.
        """
        from jevroute.config.settings import get_settings
        settings = get_settings()

        if not settings.jev_api_key:
            logger.warning(
                "JEV_API_KEY not configured — using FakeJevClient (mock mode). "
                "Results are NOT real Jev benchmark data."
            )
            from jevroute.routers.mock_jev import MockJevRouter
            # Return a thin wrapper that converts MockJevRouter output
            return _MockBackedJevRouter(
                input_price=settings.jev_input_price or 0.0,
                output_price=settings.jev_output_price or 0.0,
            )

        from jevroute.routers.jev_client import HttpxJevClient
        client = HttpxJevClient(
            api_key=settings.jev_api_key,
            base_url=settings.jev_base_url,
            model=settings.jev_model,
        )
        return cls(
            client=client,
            model_input_price_per_1k=settings.jev_input_price or 0.0,
            model_output_price_per_1k=settings.jev_output_price or 0.0,
            timeout_s=settings.jev_timeout_s,
        )


class _MockBackedJevRouter:
    """Fallback router used when JEV_API_KEY is absent.

    Delegates to MockJevRouter but sets router="jev" so CI pipelines can
    exercise the full benchmark path. Never appears in published results.
    """

    def __init__(self, input_price: float = 0.0, output_price: float = 0.0) -> None:
        from jevroute.routers.mock_jev import MockJevRouter
        self._mock = MockJevRouter()
        self._input_price = input_price
        self._output_price = output_price

    async def decide(self, state: ApplicationState) -> DecisionResult:
        result = await self._mock.decide(state)
        return result.model_copy(update={
            "router": ROUTER_NAME,
            "router_version": ROUTER_VERSION + "-mock",
        })
