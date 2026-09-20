"""Integration tests: FastAPI endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from jevroute.api.app import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_status(client):
    resp = await client.get("/api/v1/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["active_router"] == "mock_jev"
    assert data["benchmark_results_available"] is False
    assert "schema_version" in data
    assert "policy_version" in data


@pytest.mark.asyncio
async def test_decide_valid_request(client):
    payload = {
        "state": {
            "example_id": "fixture-001",
            "customer_tier": "enterprise",
            "product": "billing",
            "region": "EU",
            "ticket_subject": "Duplicate charge",
            "ticket_body": "I was charged twice.",
            "draft_reply": "We are reviewing your account.",
        }
    }
    resp = await client.post("/api/v1/decide", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["router"] == "mock_jev"
    assert data["final_action"] in ["SEND", "HOLD", "ESCALATE"]
    assert "decision" in data
    assert "policy_version" in data


@pytest.mark.asyncio
async def test_decide_invalid_request(client):
    payload = {"state": {"example_id": "x"}}  # missing required fields
    resp = await client.post("/api/v1/decide", json=payload)
    assert resp.status_code == 422  # FastAPI validation error


@pytest.mark.asyncio
async def test_decide_deterministic(client):
    payload = {
        "state": {
            "example_id": "fixture-003",
            "customer_tier": "standard",
            "product": "api",
            "region": "US",
            "ticket_subject": "Login error",
            "ticket_body": "Cannot log in.",
            "draft_reply": "We are investigating.",
        }
    }
    r1 = await client.post("/api/v1/decide", json=payload)
    r2 = await client.post("/api/v1/decide", json=payload)
    assert r1.json()["final_action"] == r2.json()["final_action"]
    assert r1.json()["decision"]["severity"] == r2.json()["decision"]["severity"]
