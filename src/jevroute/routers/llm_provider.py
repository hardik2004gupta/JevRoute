"""Generic async LLM provider boundary.

Isolates provider-specific API details from benchmark logic.
Any OpenAI-compatible endpoint is supported via configuration.

Design goals:
- No provider-specific logic leaks into benchmark/evaluation code.
- Supports mocking for tests (no network access required in CI).
- Complete token accounting; never fabricates missing values.
- Explicit error classification per the architecture.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Protocol, runtime_checkable

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Error classification (JevRoute_MVP_Technical_Architecture.md §31)
# ---------------------------------------------------------------------------

class RouterError(Exception):
    """Base class for all classifiable router failures."""

    def __init__(self, error_type: str, message: str) -> None:
        self.error_type = error_type
        super().__init__(message)


class TimeoutError(RouterError):
    def __init__(self, message: str = "Request timed out") -> None:
        super().__init__("TIMEOUT", message)


class RateLimitError(RouterError):
    def __init__(self, message: str = "Rate limit exceeded") -> None:
        super().__init__("RATE_LIMIT", message)


class AuthenticationError(RouterError):
    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__("AUTHENTICATION", message)


class NetworkError(RouterError):
    def __init__(self, message: str = "Network error") -> None:
        super().__init__("NETWORK", message)


class SchemaValidationError(RouterError):
    def __init__(self, message: str = "Response schema validation failed") -> None:
        super().__init__("SCHEMA_VALIDATION", message)


class ProviderError(RouterError):
    def __init__(self, message: str = "Provider returned an error") -> None:
        super().__init__("PROVIDER_ERROR", message)


class InvalidResponseError(RouterError):
    def __init__(self, message: str = "Response was not valid JSON or unexpected format") -> None:
        super().__init__("INVALID_RESPONSE", message)


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

class ModelResponse(BaseModel):
    """Typed response from a model client."""
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    model: str | None = None


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class ModelClient(Protocol):
    """Generic async model client interface.

    Implementations must be provider-agnostic at the call site.
    Provider-specific logic (authentication, retry headers, response parsing)
    belongs inside the implementation, not in the router.
    """

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 512,
        response_format: dict[str, Any] | None = None,
    ) -> ModelResponse:
        ...


# ---------------------------------------------------------------------------
# HTTP implementation (OpenAI-compatible)
# ---------------------------------------------------------------------------

class HttpxModelClient:
    """Async model client for any OpenAI-compatible endpoint.

    Uses httpx for async HTTP. Never logs secrets.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 512,
        response_format: dict[str, Any] | None = None,
    ) -> ModelResponse:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=self._headers,
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"Request timed out after {self._timeout}s") from exc
        except httpx.ConnectError as exc:
            raise NetworkError(f"Connection failed: {exc}") from exc
        except httpx.RequestError as exc:
            raise NetworkError(f"HTTP request error: {exc}") from exc

        if resp.status_code == 401:
            raise AuthenticationError("Invalid API key or unauthorized")
        if resp.status_code == 429:
            raise RateLimitError("Provider rate limit exceeded")
        if resp.status_code >= 500:
            raise ProviderError(f"Provider returned HTTP {resp.status_code}")
        if resp.status_code >= 400:
            raise ProviderError(f"Client error HTTP {resp.status_code}: {resp.text[:200]}")

        try:
            data = resp.json()
        except Exception as exc:
            raise InvalidResponseError("Response was not valid JSON") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise InvalidResponseError(f"Unexpected response shape: {exc}") from exc

        usage = data.get("usage", {})
        return ModelResponse(
            content=content,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            model=data.get("model"),
        )


# ---------------------------------------------------------------------------
# Fake client for testing (no network access)
# ---------------------------------------------------------------------------

class FakeModelClient:
    """Configurable fake client for tests.

    Responses are consumed from a queue. If the queue is exhausted,
    subsequent calls raise the configured fallback error.
    """

    def __init__(
        self,
        responses: list[ModelResponse | Exception] | None = None,
        default_response: ModelResponse | None = None,
    ) -> None:
        self._queue: list[ModelResponse | Exception] = list(responses or [])
        self._default = default_response or ModelResponse(
            content='{"severity":"P3","category":"Other","policy_violation":false,'
                    '"hallucination_risk":0.05,"tone_risk":0.03,"action":"SEND"}',
            input_tokens=200,
            output_tokens=40,
            model="fake-model",
        )

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 512,
        response_format: dict[str, Any] | None = None,
    ) -> ModelResponse:
        if self._queue:
            item = self._queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return self._default


def build_json_extraction_prompt(raw_content: str) -> str:
    """Return a minimal system message for parsing LLM JSON output."""
    return raw_content


def extract_json_object(content: str) -> dict[str, Any]:
    """Extract the first JSON object from a potentially prose-wrapped response."""
    content = content.strip()
    # Try direct parse first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    # Extract from markdown code fence
    import re
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Extract first {...} block
    match = re.search(r"\{[^{}]*\}", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    raise InvalidResponseError(f"No valid JSON object found in response: {content[:200]!r}")
