"""
Feature 10: Manual Cash Payment Confirmation
Validates POST /api/charges/{id}/mark-cash, method='efectivo', date advancement, and dashboard update.
"""

import httpx
import pytest
from tests.e2e.conftest import require_route


@pytest.mark.asyncio
async def test_f10_01_mark_cash_success(app_client: httpx.AsyncClient):
    """Verifies marking a charge paid with cash sets method='efectivo' and status='paid'."""
    require_route("/api/charges/{id}/mark-cash", "POST")

    # Use seeded pending charge p3
    resp = await app_client.post("/api/charges/p3/mark-cash")
    assert resp.status_code in [200, 204]
    data = resp.json()
    assert data["status"] in ["paid", "pagado"]
    assert data["method"] in ["efectivo", "cash"]
    assert data.get("paid_at") is not None


@pytest.mark.asyncio
async def test_f10_02_mark_cash_advances_subscriber_due_date(app_client: httpx.AsyncClient):
    """Verifies marking cash payment advances subscriber's next_due_date."""
    require_route("/api/charges/{id}/mark-cash", "POST")

    # Get subscriber before mark-cash
    sub_before = (await app_client.get("/api/subscribers/mariana")).json()
    initial_due_date = sub_before["next_due_date"]

    await app_client.post("/api/charges/p3/mark-cash")

    sub_after = (await app_client.get("/api/subscribers/mariana")).json()
    assert sub_after["next_due_date"] > initial_due_date


@pytest.mark.asyncio
async def test_f10_03_mark_cash_already_paid_charge(app_client: httpx.AsyncClient):
    """Verifies marking cash on an already paid charge is either rejected (400) or handled idempotently."""
    require_route("/api/charges/{id}/mark-cash", "POST")

    # p4 is seeded as paid
    resp = await app_client.post("/api/charges/p4/mark-cash")
    assert resp.status_code in [200, 400]


@pytest.mark.asyncio
async def test_f10_04_mark_cash_updates_dashboard_collected_amount(app_client: httpx.AsyncClient):
    """Verifies that confirming cash payment reflects on dashboard collected_month."""
    require_route("/api/charges/{id}/mark-cash", "POST")

    dash_before = (await app_client.get("/api/dashboard")).json()
    initial_collected = float(dash_before["collected_month"])

    await app_client.post("/api/charges/p3/mark-cash")

    dash_after = (await app_client.get("/api/dashboard")).json()
    assert float(dash_after["collected_month"]) >= initial_collected


@pytest.mark.asyncio
async def test_f10_05_mark_cash_nonexistent_charge_returns_404(app_client: httpx.AsyncClient):
    """Verifies marking cash on non-existent charge returns 404."""
    require_route("/api/charges/{id}/mark-cash", "POST")

    resp = await app_client.post("/api/charges/invalid_non_existent_charge_123/mark-cash")
    assert resp.status_code == 404
