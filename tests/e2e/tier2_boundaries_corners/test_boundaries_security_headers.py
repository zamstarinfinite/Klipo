"""
Tier 2 Boundary: Security Headers & Missing API Keys
Tests missing API key handling, gateway 401 wrapping, Bearer authorization, SQL injection, and phone sanitization.
"""

import os
import httpx
import pytest
from tests.e2e.pey_mock_server import PeyMockServer


@pytest.mark.asyncio
async def test_bva_21_missing_pey_api_key_graceful_degradation(app_client: httpx.AsyncClient):
    """Verifies that when PEY_API_KEY is empty, the health check and core CRUD continue working."""
    original_key = os.environ.get("PEY_API_KEY", "")
    os.environ["PEY_API_KEY"] = ""
    try:
        resp = await app_client.get("/api/health")
        assert resp.status_code in [200, 503]
        # Core plans and subscribers must still function
        plans_resp = await app_client.get("/api/plans")
        assert plans_resp.status_code == 200
    finally:
        os.environ["PEY_API_KEY"] = original_key


@pytest.mark.asyncio
async def test_bva_22_pey_gateway_401_wrapped_cleanly(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """Verifies mock 401 Unauthorized from Pey gateway does not cause unhandled 500 server crash."""
    pey_mock.set_unauthorized(True)
    resp = await app_client.get("/api/health")
    assert resp.status_code in [200, 502, 503]
    assert resp.status_code != 500


@pytest.mark.asyncio
async def test_bva_23_authorization_header_strictly_bearer(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """Verifies outgoing requests to Pey API strictly use 'Bearer <token>' and NEVER 'x-api-key'."""
    await app_client.get("/api/health")
    captured = pey_mock.get_captured_requests()
    for req in captured:
        headers = req["headers"]
        auth = headers.get("authorization", "")
        if auth:
            assert auth.startswith("Bearer ")
        assert "x-api-key" not in headers


@pytest.mark.asyncio
async def test_bva_24_sql_injection_defense_in_subscriber_search_and_create(app_client: httpx.AsyncClient):
    """Verifies SQL injection attempts in search queries or subscriber names are sanitized."""
    injection_name = "Robert'); DROP TABLE subscribers;--"
    plans = (await app_client.get("/api/plans")).json()
    plan_id = plans[0]["id"]

    create_resp = await app_client.post(
        "/api/subscribers",
        json={"name": injection_name, "phone": "5512345678", "plan_id": plan_id},
    )
    assert create_resp.status_code in [200, 201]

    # Verify table subscribers was NOT dropped
    verify_resp = await app_client.get("/api/subscribers")
    assert verify_resp.status_code == 200
    assert len(verify_resp.json()) > 0

    # Search injection
    search_resp = await app_client.get("/api/subscribers?search=' OR '1'='1")
    assert search_resp.status_code == 200


@pytest.mark.asyncio
async def test_bva_25_phone_number_sanitization(app_client: httpx.AsyncClient):
    """Verifies phone numbers with formatting characters (+52, parentheses, spaces, dashes) are stored."""
    plans = (await app_client.get("/api/plans")).json()
    plan_id = plans[0]["id"]

    formatted_phone = "+52 (55) 1234-5678"
    resp = await app_client.post(
        "/api/subscribers",
        json={"name": "Phone Sanitize Test", "phone": formatted_phone, "plan_id": plan_id},
    )
    assert resp.status_code in [200, 201]
    data = resp.json()
    assert "phone" in data
