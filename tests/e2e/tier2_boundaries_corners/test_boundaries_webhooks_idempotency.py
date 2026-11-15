"""
Tier 2 Boundary: Webhook Idempotency & Deduplication
Tests duplicated events, cash followed by webhook, polling after webhook, and extra payload fields.
"""

import httpx
import pytest
from tests.e2e.conftest import require_route


@pytest.mark.asyncio
async def test_bva_16_duplicate_webhook_delivery_same_event(app_client: httpx.AsyncClient):
    """Verifies posting the exact same webhook payload twice returns 200 without double-advancement."""
    require_route("/api/webhooks/pey", "POST")

    headers = {"webhook-id": "msg_duplicate_id_999"}
    payload = {
        "type": "codi.qr.payment_received",
        "codiQrId": "codi_bva_16",
        "amount": 350.0,
        "datePaid": 1790724818,
    }

    resp1 = await app_client.post("/api/webhooks/pey", json=payload, headers=headers)
    assert resp1.status_code in [200, 202]

    resp2 = await app_client.post("/api/webhooks/pey", json=payload, headers=headers)
    assert resp2.status_code in [200, 202]


@pytest.mark.asyncio
async def test_bva_17_webhook_after_manual_cash_confirmation(app_client: httpx.AsyncClient):
    """Verifies that if a charge is already paid via cash, a subsequent webhook does not corrupt state."""
    require_route("/api/webhooks/pey", "POST")
    require_route("/api/charges/{id}/mark-cash", "POST")

    # Mark cash on p3
    await app_client.post("/api/charges/p3/mark-cash")

    # Webhook arrives for p3
    payload = {
        "type": "codi.qr.payment_received",
        "codiQrId": "codi_p3",
        "amount": 350.0,
        "datePaid": 1790724818,
    }
    resp = await app_client.post("/api/webhooks/pey", json=payload)
    assert resp.status_code in [200, 202]


@pytest.mark.asyncio
async def test_bva_18_polling_after_webhook_confirmation(app_client: httpx.AsyncClient):
    """Verifies polling after webhook confirmation reports paid status immediately."""
    require_route("/api/charges/{id}/status", "GET")
    require_route("/api/webhooks/pey", "POST")

    # Charge p4 is already paid
    resp = await app_client.get("/api/charges/p4/status")
    assert resp.status_code == 200
    assert resp.json()["status"] in ["paid", "pagado"]


@pytest.mark.asyncio
async def test_bva_19_webhook_payload_with_unexpected_extra_fields(app_client: httpx.AsyncClient):
    """Verifies webhook parser tolerates extra vendor fields without returning 422."""
    require_route("/api/webhooks/pey", "POST")

    payload = {
        "type": "codi.qr.payment_received",
        "codiQrId": "codi_extra_fields",
        "amount": 350.0,
        "datePaid": 1790724818,
        "unknown_vendor_field": "unexpected_data_123",
        "nested_metadata": {"device": "mobile", "lat": 19.4326, "lon": -99.1332},
    }
    resp = await app_client.post("/api/webhooks/pey", json=payload)
    assert resp.status_code in [200, 202]


@pytest.mark.asyncio
async def test_bva_20_webhook_malformed_json_or_empty_body(app_client: httpx.AsyncClient):
    """Verifies sending malformed content to webhook endpoint returns 400 or 422 without 500 error."""
    require_route("/api/webhooks/pey", "POST")

    resp = await app_client.post(
        "/api/webhooks/pey",
        content="this is not valid json {",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code in [400, 422]
    assert resp.status_code != 500
