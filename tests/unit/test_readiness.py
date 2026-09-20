"""Tests for provider readiness checks and benchmark preflight."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from jevroute.readiness.providers import (
    ReadinessStatus,
    check_dataset_readiness,
    check_generation_readiness,
    check_jev_readiness,
    check_llm_readiness,
)


# ---------------------------------------------------------------------------
# Stub settings
# ---------------------------------------------------------------------------

@dataclass
class _Settings:
    jev_api_key: str | None = None
    jev_base_url: str | None = None
    llm_api_key: str | None = None
    model_name: str | None = None
    llm_base_url: str | None = None
    model_input_price: float | None = None
    model_output_price: float | None = None
    jev_input_price: float | None = None
    jev_output_price: float | None = None


# ---------------------------------------------------------------------------
# Jev readiness
# ---------------------------------------------------------------------------

def test_jev_missing_both():
    r = check_jev_readiness(_Settings())
    assert r.status == ReadinessStatus.MISSING_CONFIGURATION
    assert "JEV_API_KEY" in r.reason


def test_jev_missing_url():
    r = check_jev_readiness(_Settings(jev_api_key="sk-xxx"))
    assert r.status == ReadinessStatus.MISSING_CONFIGURATION
    assert "JEV_BASE_URL" in r.reason


def test_jev_missing_key():
    r = check_jev_readiness(_Settings(jev_base_url="http://jev.test"))
    assert r.status == ReadinessStatus.MISSING_CONFIGURATION
    assert "JEV_API_KEY" in r.reason


def test_jev_ready_with_credentials():
    r = check_jev_readiness(_Settings(jev_api_key="sk-xxx", jev_base_url="http://jev.test"))
    assert r.status == ReadinessStatus.READY
    assert "OQ-001" in r.reason  # must document unconfirmed endpoint


def test_jev_details_include_oq_notes():
    r = check_jev_readiness(_Settings(jev_api_key="sk-xxx", jev_base_url="http://jev.test"))
    assert "oq_001_status" in r.details
    assert "oq_002_status" in r.details
    assert "UNRESOLVED" in r.details["oq_001_status"]


# ---------------------------------------------------------------------------
# LLM readiness
# ---------------------------------------------------------------------------

def test_llm_missing_both():
    r = check_llm_readiness(_Settings())
    assert r.status == ReadinessStatus.MISSING_CONFIGURATION
    assert "LLM_API_KEY" in r.reason


def test_llm_missing_model():
    r = check_llm_readiness(_Settings(llm_api_key="sk-yyy"))
    assert r.status == ReadinessStatus.MISSING_CONFIGURATION
    assert "MODEL_NAME" in r.reason


def test_llm_ready_without_pricing():
    r = check_llm_readiness(_Settings(llm_api_key="sk-yyy", model_name="gpt-4"))
    assert r.status == ReadinessStatus.READY
    assert "pricing not set" in r.reason


def test_llm_ready_with_pricing():
    r = check_llm_readiness(_Settings(
        llm_api_key="sk-yyy", model_name="gpt-4",
        model_input_price=0.01, model_output_price=0.03,
    ))
    assert r.status == ReadinessStatus.READY


# ---------------------------------------------------------------------------
# Generation readiness (delegates to LLM)
# ---------------------------------------------------------------------------

def test_generation_blocked_when_llm_missing():
    r = check_generation_readiness(_Settings())
    assert r.status == ReadinessStatus.MISSING_CONFIGURATION
    assert r.provider == "generation"


def test_generation_ready_when_llm_ready():
    r = check_generation_readiness(_Settings(llm_api_key="sk-yyy", model_name="gpt-4"))
    assert r.status == ReadinessStatus.READY


# ---------------------------------------------------------------------------
# Dataset readiness
# ---------------------------------------------------------------------------

def test_dataset_blocked_no_research_dataset():
    r = check_dataset_readiness(research_dataset_path=None)
    assert r.status == ReadinessStatus.BLOCKED
    assert "OQ-003" in r.reason


def test_dataset_missing_config_no_manifest():
    r = check_dataset_readiness(
        research_dataset_path="/some/path/test.jsonl",
        frozen_manifest_exists=False,
    )
    assert r.status == ReadinessStatus.MISSING_CONFIGURATION
    assert "not yet frozen" in r.reason


def test_dataset_ready():
    r = check_dataset_readiness(
        research_dataset_path="/some/path/test.jsonl",
        frozen_manifest_exists=True,
        ci_fixture_count=10,
    )
    assert r.status == ReadinessStatus.READY
    assert r.details["ci_fixture_examples"] == 10
    assert r.details["test_set_frozen"] is True


# ---------------------------------------------------------------------------
# Preflight integration
# ---------------------------------------------------------------------------

def test_preflight_all_blocked(tmp_path):
    from jevroute.readiness.preflight import run_preflight
    result = run_preflight(
        results_dir=tmp_path / "results",
        datasets_dir=tmp_path / "datasets",
        research_dataset_stem=None,
        settings=_Settings(),
    )
    assert result.ready is False
    assert result.dataset.status == ReadinessStatus.BLOCKED
    assert result.jev.status == ReadinessStatus.MISSING_CONFIGURATION
    assert result.llm.status == ReadinessStatus.MISSING_CONFIGURATION


def test_preflight_to_dict_schema(tmp_path):
    from jevroute.readiness.preflight import run_preflight
    result = run_preflight(
        results_dir=tmp_path / "results",
        datasets_dir=tmp_path / "datasets",
        settings=_Settings(),
    )
    d = result.to_dict()
    assert d["_schema"] == "jevroute-preflight-v1"
    assert "overall" in d
    assert "experiments" in d
    assert "baseline-v1" in d["experiments"]


def test_preflight_experiment_ready_blocked(tmp_path):
    from jevroute.readiness.preflight import run_preflight
    result = run_preflight(
        results_dir=tmp_path / "results",
        datasets_dir=tmp_path / "datasets",
        settings=_Settings(),
    )
    ok, reason = result.experiment_ready("baseline-v1")
    assert ok is False
    assert reason  # some blocker reason


def test_preflight_output_dirs_writable(tmp_path):
    from jevroute.readiness.preflight import run_preflight
    result = run_preflight(
        results_dir=tmp_path / "results",
        datasets_dir=tmp_path / "datasets",
        settings=_Settings(),
    )
    assert result.output_dirs_writable is True


def test_preflight_policy_and_schema_always_ready(tmp_path):
    from jevroute.readiness.preflight import run_preflight
    result = run_preflight(
        results_dir=tmp_path / "results",
        datasets_dir=tmp_path / "datasets",
        settings=_Settings(),
    )
    assert result.policy_ready is True
    assert result.schema_ready is True
