"""Jev API client boundary.

OQ-001 STATUS: The Jev API's exact interface (REST, gRPC, SDK, auth scheme) is not
documented in the project specification. This file encodes the assumption that Jev
exposes a REST endpoint accepting JSON application state and returning a JSON
decision payload. If the real Jev API uses a different transport or schema, only
HttpxJevClient needs to change — JevRouter's interface remains stable.

See: docs/OPEN_QUESTIONS.md OQ-001, OQ-002.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol, runtime_checkable

import httpx

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

logger = logging.getLogger(__name__)

JEV_SCHEMA_VERSION = "jev-support-v1"


class JevResponse:
    """Parsed Jev API response payload."""

    __slots__ = (
        "severity",
        "category",
        "policy_violation",
        "hallucination_risk",
        "tone_risk",
        "action",
        "severity_confidence",
        "category_confidence",
        "action_confidence",
        "input_tokens",
        "output_tokens",
        "model",
    )

    def __init__(
        self,
        severity: str,
        category: str,
        policy_violation: bool,
        hallucination_risk: float,
        tone_risk: float,
        action: str,
        severity_confidence: float | None = None,
        category_confidence: float | None = None,
        action_confidence: float | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        model: str | None = None,
    ) -> None:
        self.severity = severity
        self.category = category
        self.policy_violation = policy_violation
        self.hallucination_risk = hallucination_risk
        self.tone_risk = tone_risk
        self.action = action
        self.severity_confidence = severity_confidence
        self.category_confidence = category_confidence
        self.action_confidence = action_confidence
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.model = model


@runtime_checkable
class JevClient(Protocol):
    """Protocol boundary for the Jev API client.

    Jev-specific transport, auth, and serialization stay inside implementations.
    JevRouter depends only on this protocol, making it testable without network access.
    """

    async def decide(
        self,
        payload: dict[str, Any],
        *,
        timeout_s: float = 10.0,
    ) -> JevResponse:
        """Submit a decision request to Jev.

        Args:
            payload: Application state dictionary (no ground truth labels).
            timeout_s: Maximum seconds to wait.

        Returns:
            Parsed JevResponse.

        Raises:
            RouterError subclass on any failure.
        """
        ...


def _map_http_status(status_code: int, detail: str) -> RouterError:
    if status_code == 401 or status_code == 403:
        return AuthenticationError(f"Jev API authentication failure: HTTP {status_code} — {detail}")
    if status_code == 429:
        return RateLimitError(f"Jev API rate limit: HTTP {status_code} — {detail}")
    return ProviderError(f"Jev API error: HTTP {status_code} — {detail}")


def _parse_jev_json(content: str) -> JevResponse:
    """Parse Jev JSON response into a JevResponse.

    Raises:
        InvalidResponseError: content is not valid JSON.
        SchemaValidationError: required fields missing or invalid values.
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise InvalidResponseError(f"Jev returned non-JSON: {exc}") from exc

    required = {"severity", "category", "policy_violation", "hallucination_risk", "tone_risk", "action"}
    missing = required - set(data.keys())
    if missing:
        raise SchemaValidationError(f"Jev response missing fields: {missing}")

    valid_severities = {"P1", "P2", "P3", "P4"}
    valid_categories = {"Billing", "Bug", "Feature", "Account", "Other"}
    valid_actions = {"SEND", "HOLD", "ESCALATE"}

    severity = str(data["severity"])
    if severity not in valid_severities:
        raise SchemaValidationError(f"Jev returned invalid severity: {severity!r}")

    category = str(data["category"])
    if category not in valid_categories:
        raise SchemaValidationError(f"Jev returned invalid category: {category!r}")

    action = str(data["action"])
    if action not in valid_actions:
        raise SchemaValidationError(f"Jev returned invalid action: {action!r}")

    for prob_field in ("hallucination_risk", "tone_risk"):
        val = data[prob_field]
        if not isinstance(val, (int, float)) or not (0.0 <= float(val) <= 1.0):
            raise SchemaValidationError(f"Jev returned invalid {prob_field}: {val!r}")

    usage = data.get("usage", {})
    return JevResponse(
        severity=severity,
        category=category,
        policy_violation=bool(data["policy_violation"]),
        hallucination_risk=float(data["hallucination_risk"]),
        tone_risk=float(data["tone_risk"]),
        action=action,
        severity_confidence=data.get("severity_confidence"),
        category_confidence=data.get("category_confidence"),
        action_confidence=data.get("action_confidence"),
        input_tokens=usage.get("input_tokens") if usage else data.get("input_tokens"),
        output_tokens=usage.get("output_tokens") if usage else data.get("output_tokens"),
        model=data.get("model"),
    )


class HttpxJevClient:
    """Real Jev API client using httpx.

    ASSUMPTION (OQ-001): Jev exposes a REST endpoint at {base_url}/v1/decide
    accepting POST JSON with the application state payload and returning
    a JSON decision. Adjust the URL path and request/response schema once
    the actual Jev API specification is available.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.jev.ai",
        *,
        model: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def decide(
        self,
        payload: dict[str, Any],
        *,
        timeout_s: float = 10.0,
    ) -> JevResponse:
        request_body: dict[str, Any] = {"state": payload}
        if self._model:
            request_body["model"] = self._model

        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.post(
                    f"{self._base_url}/v1/decide",
                    json=request_body,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                )
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"Jev API timeout after {timeout_s}s") from exc
        except httpx.NetworkError as exc:
            raise NetworkError(f"Jev API network error: {exc}") from exc

        if not resp.is_success:
            raise _map_http_status(resp.status_code, resp.text[:200])

        return _parse_jev_json(resp.text)


class FakeJevClient:
    """In-process fake Jev client for tests and CI.

    Uses a FIFO queue of pre-configured responses. When the queue is empty,
    returns default_response if set, otherwise raises RouterError.
    If a queue item is an Exception instance, it is raised instead.
    """

    def __init__(
        self,
        responses: list[JevResponse | Exception] | None = None,
        default_response: JevResponse | None = None,
    ) -> None:
        self._queue: list[JevResponse | Exception] = list(responses or [])
        self._default = default_response

    async def decide(
        self,
        payload: dict[str, Any],
        *,
        timeout_s: float = 10.0,
    ) -> JevResponse:
        if self._queue:
            item = self._queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        if self._default is not None:
            return self._default
        raise ProviderError("FakeJevClient: queue exhausted and no default_response configured")
