"""LLMParallelRouter: independent async LLM calls per decision dimension.

Each of the 6 decision dimensions is asked in a separate, concurrent LLM call.
Aggregate cost, aggregate tokens, and total wall-clock latency are all measured.
Parallelism does NOT hide cost — the full aggregate is recorded.

Router version: llm-parallel-v1
Prompt version: llm-control-v1.0
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
from jevroute.routers.llm_provider import (
    ModelClient,
    ModelResponse,
    RouterError,
    SchemaValidationError,
    extract_json_object,
)

logger = logging.getLogger(__name__)

ROUTER_NAME = "llm_parallel"
ROUTER_VERSION = "llm-parallel-v1"
PROMPT_VERSION = "llm-control-v1.0"

_RETRY_BACKOFF_S = 0.25
_MAX_ATTEMPTS = 2
NUM_CALLS = 6  # One per decision dimension

_SYSTEM = "You are a structured decision engine. Respond with ONLY a JSON object; no explanation."

# ---------------------------------------------------------------------------
# Per-dimension prompt templates
# All calls receive the same ApplicationState; none receive ground truth.
# ---------------------------------------------------------------------------

def _severity_messages(state: ApplicationState) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": (
            f"Classify the severity of this support ticket.\n"
            f"Customer tier: {state.customer_tier}\n"
            f"Product: {state.product}\n"
            f"Subject: {state.ticket_subject}\n"
            f"Body: {state.ticket_body}\n\n"
            'Output: {"severity": "P1"|"P2"|"P3"|"P4"}\n'
            "P1=critical, P2=high, P3=medium, P4=low"
        )},
    ]


def _category_messages(state: ApplicationState) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": (
            f"Classify the category of this support ticket.\n"
            f"Subject: {state.ticket_subject}\n"
            f"Body: {state.ticket_body}\n\n"
            'Output: {"category": "Billing"|"Bug"|"Feature"|"Account"|"Other"}'
        )},
    ]


def _policy_violation_messages(state: ApplicationState) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": (
            f"Does this draft reply violate policy (misleading, unauthorized promises, guideline breach)?\n"
            f"Subject: {state.ticket_subject}\n"
            f"Body: {state.ticket_body}\n"
            f"Draft reply: {state.draft_reply}\n\n"
            'Output: {"policy_violation": true|false}'
        )},
    ]


def _hallucination_risk_messages(state: ApplicationState) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": (
            f"Estimate probability (0.0-1.0) that the draft reply contains hallucinated or unsupported claims.\n"
            f"Body: {state.ticket_body}\n"
            f"Draft reply: {state.draft_reply}\n\n"
            'Output: {"hallucination_risk": <float 0.0-1.0>}'
        )},
    ]


def _tone_risk_messages(state: ApplicationState) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": (
            f"Estimate probability (0.0-1.0) that the draft reply has inappropriate tone.\n"
            f"Body: {state.ticket_body}\n"
            f"Draft reply: {state.draft_reply}\n\n"
            'Output: {"tone_risk": <float 0.0-1.0>}'
        )},
    ]


def _action_messages(state: ApplicationState) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": (
            f"Determine the appropriate action for this support ticket and draft reply.\n"
            f"Customer tier: {state.customer_tier}\n"
            f"Subject: {state.ticket_subject}\n"
            f"Body: {state.ticket_body}\n"
            f"Draft reply: {state.draft_reply}\n\n"
            'Output: {"action": "SEND"|"HOLD"|"ESCALATE"}\n'
            "SEND=appropriate to send, HOLD=needs review, ESCALATE=needs human escalation"
        )},
    ]


_DIMENSION_BUILDERS = [
    _severity_messages,
    _category_messages,
    _policy_violation_messages,
    _hallucination_risk_messages,
    _tone_risk_messages,
    _action_messages,
]

_DIMENSION_NAMES = [
    "severity",
    "category",
    "policy_violation",
    "hallucination_risk",
    "tone_risk",
    "action",
]


# ---------------------------------------------------------------------------
# Per-call execution with retry
# ---------------------------------------------------------------------------

async def _execute_one_call(
    client: ModelClient,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    dimension: str,
) -> tuple[ModelResponse, int]:
    """Execute one call with bounded retry; return (response, retry_count)."""
    last_error: RouterError | None = None

    for attempt in range(_MAX_ATTEMPTS):
        if attempt > 0:
            await asyncio.sleep(_RETRY_BACKOFF_S)

        try:
            response = await client.complete(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            return response, attempt
        except RouterError as exc:
            last_error = exc
            if exc.error_type in ("AUTHENTICATION", "SCHEMA_VALIDATION"):
                break

    if last_error is not None:
        raise last_error
    raise RouterError("INTERNAL_ERROR", f"Unknown failure on dimension {dimension}")


# ---------------------------------------------------------------------------
# LLMParallelRouter
# ---------------------------------------------------------------------------

class LLMParallelRouter:
    """Concurrent per-dimension LLM router.

    Makes NUM_CALLS=6 independent concurrent calls. Aggregate cost, aggregate
    tokens, and total wall-clock latency are all recorded.
    Parallelism does not make the aggregate cost free.
    """

    def __init__(
        self,
        client: ModelClient,
        model_input_price_per_1k: float = 0.0,
        model_output_price_per_1k: float = 0.0,
        temperature: float = 0.0,
        max_tokens: int = 64,
    ) -> None:
        self._client = client
        self._input_price_per_1k = model_input_price_per_1k
        self._output_price_per_1k = model_output_price_per_1k
        self._temperature = temperature
        self._max_tokens = max_tokens

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            (input_tokens / 1000) * self._input_price_per_1k
            + (output_tokens / 1000) * self._output_price_per_1k
        )

    async def decide(self, state: ApplicationState) -> DecisionResult:
        messages_list = [builder(state) for builder in _DIMENSION_BUILDERS]

        t_start = perf_counter()

        # All 6 calls execute concurrently
        tasks = [
            asyncio.create_task(
                _execute_one_call(
                    self._client,
                    messages,
                    self._temperature,
                    self._max_tokens,
                    _DIMENSION_NAMES[i],
                )
            )
            for i, messages in enumerate(messages_list)
        ]

        results: list[tuple[ModelResponse, int] | BaseException] = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        total_latency_ms = (perf_counter() - t_start) * 1000

        # Aggregate tokens from all successful calls
        total_input = 0
        total_output = 0
        total_retries = 0
        parsed: dict[str, object] = {}
        errors: dict[str, str] = {}

        for i, res in enumerate(results):
            dim = _DIMENSION_NAMES[i]
            if isinstance(res, BaseException):
                errors[dim] = str(res)
                continue
            response, attempt = res
            total_input += response.input_tokens or 0
            total_output += response.output_tokens or 0
            total_retries += attempt

            try:
                raw = extract_json_object(response.content)
                parsed[dim] = raw.get(dim)
            except Exception as exc:
                errors[dim] = str(exc)

        if errors:
            # Raise the first error encountered; caller records it as a failure
            first_dim = next(iter(errors))
            raise SchemaValidationError(
                f"Parallel call failed on dimension '{first_dim}': {errors[first_dim]}"
            )

        # Validate all parsed values
        try:
            severity = Severity(parsed["severity"])
            category = Category(parsed["category"])
            action = Action(parsed["action"])
            pv = bool(parsed["policy_violation"])
            hr = float(parsed["hallucination_risk"])  # type: ignore[arg-type]
            tr = float(parsed["tone_risk"])  # type: ignore[arg-type]
        except (KeyError, ValueError, TypeError) as exc:
            raise SchemaValidationError(f"Parallel result assembly failed: {exc}") from exc

        if not (0.0 <= hr <= 1.0):
            raise SchemaValidationError(f"hallucination_risk out of range: {hr}")
        if not (0.0 <= tr <= 1.0):
            raise SchemaValidationError(f"tone_risk out of range: {tr}")

        cost = self._estimate_cost(total_input, total_output)

        return DecisionResult(
            severity=severity,
            category=category,
            policy_violation=pv,
            hallucination_risk=round(hr, 4),
            tone_risk=round(tr, 4),
            action=action,
            confidence=ConfidenceOutput(),  # Parallel calls produce no explicit confidence
            router=ROUTER_NAME,
            router_version=ROUTER_VERSION,
            schema_valid=True,
            latency_ms=round(total_latency_ms, 3),
            input_tokens=total_input or None,
            output_tokens=total_output or None,
            estimated_cost_usd=cost,
            retry_count=total_retries,
        )
