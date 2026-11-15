"""
Feature 5: Health Check Endpoint
Validates /api/health checking SQLite connectivity and Pey gateway credential verification.
"""

import os
import httpx
import pytest
from tests.e2e.pey_mock_server import PeyMockServer


@pytest.mark.asyncio
async def test_f5_01_health_check_healthy(app_client: httpx.AsyncClient):
    """Verifies that GET /api/health returns 200 and healthy database status."""
    resp = await app_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"
    assert data.get("database") in ["connected", "ok"]


@pytest.mark.asyncio
async def test_f5_02_health_check_detects_database_disconnect(app_client: httpx.AsyncClient, tmp_path):
    """Verifies health check detects inaccessible database and degrades or returns 503."""
    orig_db_path = os.environ.get("DATABASE_PATH")
    orig_sqlite_path = os.environ.get("SQLITE_DB_PATH")
    invalid_path = str(tmp_path / "non_existent_subdir" / "cannot_create.db")
    os.environ["DATABASE_PATH"] = invalid_path
    os.environ["SQLITE_DB_PATH"] = invalid_path
    try:
        resp = await app_client.get("/api/health")
        # Should return 503 Service Unavailable or degraded status
        assert resp.status_code in [500, 503] or resp.json().get("database") in ["disconnected", "error"]
    finally:
        if orig_db_path is not None:
            os.environ["DATABASE_PATH"] = orig_db_path
        else:
            os.environ.pop("DATABASE_PATH", None)
        if orig_sqlite_path is not None:
            os.environ["SQLITE_DB_PATH"] = orig_sqlite_path
        else:
            os.environ.pop("SQLITE_DB_PATH", None)


test_f5_02_health_check_detects_db_disconnect = test_f5_02_health_check_detects_database_disconnect


@pytest.mark.asyncio
async def test_f5_03_health_check_response_structure(app_client: httpx.AsyncClient):
    """Verifies standard schema keys in /api/health payload."""
    resp = await app_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "database" in data


@pytest.mark.asyncio
async def test_f5_04_health_check_pey_gateway_auth(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """Verifies health check interacts with Pey mock endpoint /transaction/api-key if integrated."""
    resp = await app_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "pey_api" in data
    assert data["pey_api"] in ["authenticated", "ok"]


@pytest.mark.asyncio
async def test_f5_05_health_check_header_verification(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """Verifies that any outbound requests to Pey gateway send Authorization: Bearer <token>."""
    await app_client.get("/api/health")
    captured = pey_mock.get_captured_requests()
    for req in captured:
        auth = req["headers"].get("authorization", "")
        if auth:
            assert auth.startswith("Bearer "), f"Authorization header must start with Bearer, got: {auth}"
        assert "x-api-key" not in req["headers"], "Header x-api-key must NOT be sent to Pey API"
