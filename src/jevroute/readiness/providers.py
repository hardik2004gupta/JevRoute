"""Provider readiness checks: validate credential and configuration availability."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ReadinessStatus(str, Enum):
    READY = "READY"
    MISSING_CONFIGURATION = "MISSING_CONFIGURATION"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    UNREACHABLE = "UNREACHABLE"
    BLOCKED = "BLOCKED"


@dataclass
class ProviderReadiness:
    provider: str
    status: ReadinessStatus
    reason: str
    details: dict[str, Any]


def check_jev_readiness(settings: Any) -> ProviderReadiness:
    """Check Jev provider configuration without making a network call."""
    missing: list[str] = []
    details: dict[str, Any] = {}

    api_key = getattr(settings, "jev_api_key", None)
    base_url = getattr(settings, "jev_base_url", None)

    details["JEV_API_KEY"] = "SET" if api_key else "MISSING"
    details["JEV_BASE_URL"] = base_url or "MISSING"
    details["jev_input_price"] = getattr(settings, "jev_input_price", None)
    details["jev_output_price"] = getattr(settings, "jev_output_price", None)
    details["endpoint_confirmed"] = False
    details["oq_001_status"] = "UNRESOLVED — POST {base_url}/v1/decide assumed, not confirmed"
    details["oq_002_status"] = "UNRESOLVED — pricing defaults to $0.00/token"

    if not api_key:
        missing.append("JEV_API_KEY")
    if not base_url:
        missing.append("JEV_BASE_URL")

    if missing:
        return ProviderReadiness(
            provider="jev",
            status=ReadinessStatus.MISSING_CONFIGURATION,
            reason=f"Missing: {', '.join(missing)}",
            details=details,
        )

    return ProviderReadiness(
        provider="jev",
        status=ReadinessStatus.READY,
        reason="Credentials configured (endpoint unconfirmed — OQ-001)",
        details=details,
    )


def check_llm_readiness(settings: Any) -> ProviderReadiness:
    """Check LLM provider configuration without making a network call."""
    missing: list[str] = []
    details: dict[str, Any] = {}

    api_key = getattr(settings, "llm_api_key", None)
    model_name = getattr(settings, "model_name", None)
    base_url = getattr(settings, "llm_base_url", None)

    details["LLM_API_KEY"] = "SET" if api_key else "MISSING"
    details["MODEL_NAME"] = model_name or "MISSING"
    details["LLM_BASE_URL"] = base_url or "MISSING"
    details["model_input_price"] = getattr(settings, "model_input_price", None)
    details["model_output_price"] = getattr(settings, "model_output_price", None)

    if not api_key:
        missing.append("LLM_API_KEY")
    if not model_name:
        missing.append("MODEL_NAME")

    if missing:
        return ProviderReadiness(
            provider="llm",
            status=ReadinessStatus.MISSING_CONFIGURATION,
            reason=f"Missing: {', '.join(missing)}",
            details=details,
        )

    if (getattr(settings, "model_input_price", None) is None
            or getattr(settings, "model_output_price", None) is None):
        return ProviderReadiness(
            provider="llm",
            status=ReadinessStatus.READY,
            reason="Credentials configured; pricing not set (cost will be $0.00)",
            details=details,
        )

    return ProviderReadiness(
        provider="llm",
        status=ReadinessStatus.READY,
        reason="Credentials and pricing configured",
        details=details,
    )


def check_generation_readiness(settings: Any) -> ProviderReadiness:
    """Check generation provider readiness (reuses LLM credentials for e2e-v1)."""
    llm = check_llm_readiness(settings)
    return ProviderReadiness(
        provider="generation",
        status=llm.status,
        reason=f"Depends on LLM credentials: {llm.reason}",
        details=llm.details,
    )


def check_dataset_readiness(
    research_dataset_path: str | None = None,
    frozen_manifest_exists: bool = False,
    ci_fixture_count: int = 10,
) -> ProviderReadiness:
    """Check dataset readiness for the research benchmark."""
    details: dict[str, Any] = {
        "ci_fixture_examples": ci_fixture_count,
        "research_dataset_path": research_dataset_path,
        "research_dataset_exists": research_dataset_path is not None,
        "test_set_frozen": frozen_manifest_exists,
        "target_size": "1000-2000 examples",
    }

    if not research_dataset_path:
        return ProviderReadiness(
            provider="dataset",
            status=ReadinessStatus.BLOCKED,
            reason="Research dataset not available (OQ-003). CI fixture (10 examples) is pipeline validation only.",
            details=details,
        )

    if not frozen_manifest_exists:
        return ProviderReadiness(
            provider="dataset",
            status=ReadinessStatus.MISSING_CONFIGURATION,
            reason="Research dataset found but test set not yet frozen.",
            details=details,
        )

    return ProviderReadiness(
        provider="dataset",
        status=ReadinessStatus.READY,
        reason="Research dataset present and test set frozen.",
        details=details,
    )
