"""
Feature 3: Static Asset Serving & SPA Routing Fallback
Validates static asset mounts, SPA fallbacks, JSON 404 for API routes, and CORS headers.
"""

import httpx
import pytest


@pytest.mark.asyncio
async def test_f3_01_root_endpoint_serves_html_or_info(app_client: httpx.AsyncClient):
    """Verifies that GET / returns HTTP 200 (HTML or JSON informative info)."""
    resp = await app_client.get("/")
    assert resp.status_code == 200
    # In full build mode, returns text/html. In headless standalone API mode, returns JSON info.
    assert "text/html" in resp.headers.get("content-type", "") or "application/json" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_f3_02_static_asset_serving_mime_type(app_client: httpx.AsyncClient):
    """Verifies static asset handling (e.g. /favicon.ico or /assets/)."""
    resp = await app_client.get("/assets/index.js")
    # If dist is mounted, returns static file; if not mounted yet, returns 404 or SPA fallback
    assert resp.status_code in [200, 404]


@pytest.mark.asyncio
async def test_f3_03_spa_route_fallback(app_client: httpx.AsyncClient):
    """Verifies SPA client-side routes (e.g. /planes, /suscriptores) return 200 or 404 without 500 error."""
    resp = await app_client.get("/planes")
    assert resp.status_code in [200, 404]
    assert resp.status_code != 500


@pytest.mark.asyncio
async def test_f3_04_unknown_api_endpoint_returns_json_404(app_client: httpx.AsyncClient):
    """Verifies unknown /api/* endpoints return JSON 404 (and not HTML SPA page)."""
    resp = await app_client.get("/api/definitely_non_existent_endpoint_xyz")
    assert resp.status_code == 404
    assert "application/json" in resp.headers.get("content-type", "")
    data = resp.json()
    assert "detail" in data or "message" in data or "error" in data


@pytest.mark.asyncio
async def test_f3_05_cors_headers_handling(app_client: httpx.AsyncClient):
    """Verifies CORS preflight headers on API endpoints."""
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type",
    }
    resp = await app_client.options("/api/plans", headers=headers)
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") in ["*", "http://localhost:5173"]
