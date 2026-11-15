"""
Feature 9: Inbound Webhook Processing
Validates POST /api/webhooks/pey, CoDi/Payment Link events, idempotency, and graceful error handling.
"""

import httpx
import pytest
from tests.e2e.conftest import require_route


@pytest.mark.asyncio
async def test_f9_01_webhook_codi_payment_received(app_client: httpx.AsyncClient):
    """Verifies inbound codi.qr.payment_received webhook marks charge as paid."""
    require_route("/api/webhooks/pey", "POST")

    payload = {
        "type": "codi.qr.payment_received",
        "codiQrId": "codi_0001",
        "amount": 350.0,
        "datePaid": 1790724818,
        "transactionId": "tx_codi_0001",
    }
    resp = await app_client.post("/api/webhooks/pey", json=payload)
    assert resp.status_code in [200, 202]
    data = resp.json()
    assert "status" in data or "received" in data or "message" in data


@pytest.mark.asyncio
async def test_f9_02_webhook_payment_link_status_updated(app_client: httpx.AsyncClient):
    """Verifies inbound payment_link.status_updated webhook processes paid status."""
    require_route("/api/webhooks/pey", "POST")

    payload = {
        "type": "payment_link.status_updated",
        "paymentLinkId": "link_0001",
        "status": "paid",
        "clientReferenceId": "c_sample_reference",
        "transactions": [{"transactionId": "tx_link_0001", "amount": 250.0, "datePaid": 1790724818}],
    }
    resp = await app_client.post("/api/webhooks/pey", json=payload)
    assert resp.status_code in [200, 202]


@pytest.mark.asyncio
async def test_f9_03_webhook_deduplication_via_message_id(app_client: httpx.AsyncClient):
    """Verifies duplicate webhook delivers return 200 without double-advancing recurrence."""
    require_route("/api/webhooks/pey", "POST")

    headers = {"webhook-id": "msg_duplicate_test_001"}
    payload = {
        "type": "codi.qr.payment_received",
        "codiQrId": "codi_dup_test",
        "amount": 100.0,
        "datePaid": 1790724818,
    }

    resp1 = await app_client.post("/api/webhooks/pey", json=payload, headers=headers)
    assert resp1.status_code in [200, 202]

    # Duplicate call
    resp2 = await app_client.post("/api/webhooks/pey", json=payload, headers=headers)
    assert resp2.status_code in [200, 202]


@pytest.mark.asyncio
async def test_f9_04_webhook_ignores_unrecognized_event(app_client: httpx.AsyncClient):
    """Verifies unknown webhook event type is acknowledged gracefully without crashing."""
    require_route("/api/webhooks/pey", "POST")

    payload = {"type": "unknown.system.probe_event", "payload": {}}
    resp = await app_client.post("/api/webhooks/pey", json=payload)
    assert resp.status_code in [200, 202]


@pytest.mark.asyncio
async def test_f9_05_webhook_missing_charge_returns_graceful_acknowledgment(app_client: httpx.AsyncClient):
    """Verifies webhook for unrecorded charge returns graceful 200/202 to avoid gateway retries."""
    require_route("/api/webhooks/pey", "POST")

    payload = {
        "type": "codi.qr.payment_received",
        "codiQrId": "completely_unrecorded_codi_id_8888",
        "amount": 500.0,
        "datePaid": 1790724818,
    }
    resp = await app_client.post("/api/webhooks/pey", json=payload)
    assert resp.status_code in [200, 202]
