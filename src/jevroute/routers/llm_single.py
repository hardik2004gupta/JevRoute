"""LLMSingleRouter: one LLM call per ApplicationState.

Produces the complete structured DecisionResult from a single model request.
Prompt is versioned; any change requires a new version identifier.

Router version: llm-single-v1
Prompt version: llm-control-v1.0
"""

from __future__ import annotations

import asyncio
import json
import logging
from time import perf_counter

from pydantic import ValidationError

from jevroute.models.decision import (
    Action,
    Category,
    ConfidenceOutput,
    DecisionResult,
    Severity,
)
from jevroute.models.state import ApplicationState
from jevroute.routers.llm_provider import (
    ModelClient,
    RouterError,
    SchemaValidationError,
    extract_json_object,
)

logger = logging.getLogger(__name__)

ROUTER_NAME = "llm_single"
ROUTER_VERSION = "llm-single-v1"
PROMPT_VERSION = "llm-control-v1.0"

_SYSTEM_PROMPT = """\
You are a structured decision engine for an AI customer-support control plane.
Given a support ticket and AI-generated draft reply, output a JSON object with the following fields:

- "severity": one of "P1", "P2", "P3", "P4"
  P1 = critical (whole team affected, security breach, data loss)
  P2 = high (billing dispute, service degradation affecting one customer)
  P3 = medium (individual bug, account issue)
  P4 = low (feature request, cosmetic issue)

- "category": one of "Billing", "Bug", "Feature", "Account", "Other"

- "policy_violation": true if the draft reply is misleading, makes unauthorized promises, or violates guidelines; false otherwise

- "hallucination_risk": float 0.0-1.0, probability that draft reply contains unsupported claims

- "tone_risk": float 0.0-1.0, probability that draft reply has inappropriate tone

- "action": one of "SEND", "HOLD", "ESCALATE"
  SEND = reply is appropriate to send
  HOLD = reply needs review before sending
  ESCALATE = ticket needs human escalation

Respond with ONLY a JSON object. No explanation, no markdown.
"""

_USER_TEMPLATE = """\
CUSTOMER TIER: {customer_tier}
PRODUCT: {product}
REGION: {region}

TICKET SUBJECT: {ticket_subject}

TICKET BODY:
{ticket_body}

DRAFT REPLY:
{draft_reply}"""

_RETRY_BACKOFF_S = 0.25
_MAX_ATTEMPTS = 2


class LLMSingleRouter:
    """Single-call LLM router.

    One model request produces the complete structured decision.
    Prompt version is embedded in every result for reproducibility.
    """

    def __init__(
        self,
        client: ModelClient,
        model_input_price_per_1k: float = 0.0,
        model_output_price_per_1k: float = 0.0,
        temperature: float = 0.0,
        max_tokens: int = 512,
        request_timeout_s: float = 30.0,
    ) -> None:
        self._client = client
        self._input_price_per_1k = model_input_price_per_1k
        self._output_price_per_1k = model_output_price_per_1k
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = request_timeout_s

    def _estimate_cost(self, input_tokens: int | None, output_tokens: int | None) -> float | None:
        if input_tokens is None or output_tokens is None:
            return None
        return (
            (input_tokens / 1000) * self._input_price_per_1k
            + (output_tokens / 1000) * self._output_price_per_1k
        )

    def _build_messages(self, state: ApplicationState) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _USER_TEMPLATE.format(
                    customer_tier=state.customer_tier,
                    product=state.product,
                    region=state.region,
                    ticket_subject=state.ticket_subject,
                    ticket_body=state.ticket_body,
                    draft_reply=state.draft_reply,
                ),
            },
        ]

    def _parse_response(self, content: str) -> DecisionResult:
        raw = extract_json_object(content)

        # Validate with Pydantic — never silently repair invalid output
        try:
            severity = Severity(raw["severity"])
            category = Category(raw["category"])
            action = Action(raw["action"])
        except (KeyError, ValueError) as exc:
            raise SchemaValidationError(f"Enum field invalid: {exc}") from exc

        for field in ("policy_violation", "hallucination_risk", "tone_risk"):
            if field not in raw:
                raise SchemaValidationError(f"Required field missing: {field}")

        try:
            pv = bool(raw["policy_violation"])
            hr = float(raw["hallucination_risk"])
            tr = float(raw["tone_risk"])
        except (ValueError, TypeError) as exc:
            raise SchemaValidationError(f"Type coercion failed: {exc}") from exc

        if not (0.0 <= hr <= 1.0):
            raise SchemaValidationError(f"hallucination_risk out of range: {hr}")
        if not (0.0 <= tr <= 1.0):
            raise SchemaValidationError(f"tone_risk out of range: {tr}")

        # Build DecisionResult; schema_valid=True means parse succeeded.
        # Actual values are set after we receive tokens/latency so we return
        # a partial object here and caller will augment it.
        return DecisionResult(
            severity=severity,
            category=category,
            policy_violation=pv,
            hallucination_risk=hr,
            tone_risk=tr,
            action=action,
            confidence=ConfidenceOutput(),  # LLM single produces no explicit confidence
            router=ROUTER_NAME,
            router_version=ROUTER_VERSION,
            schema_valid=True,
            latency_ms=None,
            input_tokens=None,
            output_tokens=None,
            estimated_cost_usd=None,
        )

    async def decide(self, state: ApplicationState) -> DecisionResult:
        messages = self._build_messages(state)
        last_error: RouterError | None = None
        total_input_tokens = 0
        total_output_tokens = 0
        retry_count = 0

        t_start = perf_counter()

        for attempt in range(_MAX_ATTEMPTS):
            if attempt > 0:
                await asyncio.sleep(_RETRY_BACKOFF_S)
                retry_count += 1

            try:
                response = await self._client.complete(
                    messages=messages,
                    temperature=self._temperature,
                    max_tokens=self._max_tokens,
                    response_format={"type": "json_object"},
                )
            except RouterError as exc:
                last_error = exc
                # Do not retry auth or schema errors
                if exc.error_type in ("AUTHENTICATION", "SCHEMA_VALIDATION"):
                    break
                # Retry on timeout/rate_limit/network/provider
                continue

            # Accumulate token usage across retries
            total_input_tokens += response.input_tokens or 0
            total_output_tokens += response.output_tokens or 0

            try:
                result = self._parse_response(response.content)
            except SchemaValidationError as exc:
                last_error = exc
                break  # Schema errors are not retryable

            latency_ms = (perf_counter() - t_start) * 1000
            cost = self._estimate_cost(
                total_input_tokens or None,
                total_output_tokens or None,
            )

            # Return with full observability fields populated
            return result.model_copy(update={
                "latency_ms": round(latency_ms, 3),
                "input_tokens": total_input_tokens or None,
                "output_tokens": total_output_tokens or None,
                "estimated_cost_usd": cost,
            })

        # All attempts failed — re-raise the last classified error
        latency_ms = (perf_counter() - t_start) * 1000
        if last_error is not None:
            raise last_error
        raise RouterError("INTERNAL_ERROR", "Unknown failure after retries")
