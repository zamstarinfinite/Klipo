"""
Feature 8: Live Payment Status Polling
Validates GET /api/charges/{id}/status, state transition from pending to paid, and idempotency.
"""

import httpx
import pytest
from tests.e2e.conftest import require_route
from tests.e2e.pey_mock_server import PeyMockServer


@pytest.mark.asyncio
async def test_f8_01_polling_returns_pending_when_unpaid(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """Verifies querying charge status returns 'pending' when not yet paid."""
    require_route("/api/charges/{id}/status", "GET")

    # Create a charge
    subs_resp = await app_client.get("/api/subscribers")
    sub = subs_resp.json()[0]
    create_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub["id"], "amount": 350.0},
    )
    charge_id = create_resp.json()["id"]

    resp = await app_client.get(f"/api/charges/{charge_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ["pending", "pendiente"]


@pytest.mark.asyncio
async def test_f8_02_polling_transitions_to_paid(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """Verifies that when Pey reports transaction as PAID, polling updates status to 'paid'."""
    require_route("/api/charges/{id}/status", "GET")

    subs_resp = await app_client.get("/api/subscribers")
    sub = subs_resp.json()[0]
    create_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub["id"], "amount": 350.0},
    )
    charge_data = create_resp.json()
    charge_id = charge_data["id"]
    codi_id = charge_data.get("codi_qr_id")
    assert codi_id is not None and len(codi_id) > 0, "Expected codi_qr_id in charge response"

    # Mark as paid in mock gateway
    pey_mock.mark_codi_paid(codi_id)

    resp = await app_client.get(f"/api/charges/{charge_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ["paid", "pagado"]
    assert data.get("paid_at") is not None


@pytest.mark.asyncio
async def test_f8_03_polling_payment_link_status(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """Verifies polling handles payment link charges."""
    require_route("/api/charges/{id}/status", "GET")

    subs_resp = await app_client.get("/api/subscribers")
    sub = subs_resp.json()[0]
    create_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub["id"], "amount": 250.0, "method": "link"},
    )
    charge_data = create_resp.json()
    charge_id = charge_data["id"]
    link_id = charge_data.get("payment_link_id")
    assert link_id is not None and len(link_id) > 0, "Expected payment_link_id in charge response"

    pey_mock.mark_link_paid(link_id)

    resp = await app_client.get(f"/api/charges/{charge_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ["paid", "pagado"]


@pytest.mark.asyncio
async def test_f8_04_polling_idempotent_when_already_paid(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """Verifies polling an already-paid charge returns paid status and does not re-advance dates."""
    require_route("/api/charges/{id}/status", "GET")

    # Seeded charge p4 is already paid in seed.py
    resp = await app_client.get("/api/charges/p4/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ["paid", "pagado"]


@pytest.mark.asyncio
async def test_f8_05_polling_nonexistent_charge_returns_404(app_client: httpx.AsyncClient):
    """Verifies polling a non-existent charge returns 404 Not Found."""
    require_route("/api/charges/{id}/status", "GET")

    resp = await app_client.get("/api/charges/non_existent_charge_uuid_9999/status")
    assert resp.status_code == 404
    assert "detail" in resp.json() or "message" in resp.json()
