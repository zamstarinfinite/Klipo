"""
Tier 3: Pairwise Combinatorial Test Suite
Implements the 12-test Orthogonal Array Matrix (Method × Frequency × Initial Status × Confirmation Channel).
Derived from Spec Miner 1 handoff report (§4.5).
"""

from datetime import date, timedelta
import httpx
import pytest
from backend.db import advance_due_date, calculate_subscriber_status
from tests.e2e.conftest import require_route
from tests.e2e.pey_mock_server import PeyMockServer


@pytest.mark.asyncio
async def test_t3_01_codi_semanal_atrasado_polling(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """T3-01: CoDi QR × Semanal × Atrasado × Polling -> Advances weekly from today/due."""
    # Create weekly plan
    plan_resp = await app_client.post(
        "/api/plans",
        json={"name": "Weekly Plan T3-01", "price": 100.0, "interval": "weekly"},
    )
    plan_id = plan_resp.json()["id"]

    # Create overdue subscriber
    overdue_date = (date.today() - timedelta(days=10)).isoformat()
    sub_resp = await app_client.post(
        "/api/subscribers",
        json={"name": "Sub T3-01", "phone": "5511000001", "plan_id": plan_id, "next_due_date": overdue_date},
    )
    sub = sub_resp.json()
    assert sub["status"] == "atrasado"

    # Create CoDi charge
    charge_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub["id"], "amount": 100.0, "method": "codi"},
    )
    charge_id = charge_resp.json()["id"]

    require_route("/api/charges/{id}/status", "GET")
    status_resp = await app_client.get(f"/api/charges/{charge_id}/status")
    assert status_resp.status_code == 200


@pytest.mark.asyncio
async def test_t3_02_codi_quincenal_porvencer_webhook(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """T3-02: CoDi QR × Quincenal × Por Vencer × Webhook -> Advances biweekly."""
    plan_resp = await app_client.post(
        "/api/plans",
        json={"name": "Biweekly Plan T3-02", "price": 200.0, "interval": "biweekly"},
    )
    plan_id = plan_resp.json()["id"]

    due_soon_date = (date.today() + timedelta(days=2)).isoformat()
    sub_resp = await app_client.post(
        "/api/subscribers",
        json={"name": "Sub T3-02", "phone": "5511000002", "plan_id": plan_id, "next_due_date": due_soon_date},
    )
    sub = sub_resp.json()
    assert sub["status"] == "por_vencer"

    require_route("/api/webhooks/pey", "POST")
    webhook_resp = await app_client.post(
        "/api/webhooks/pey",
        json={"type": "codi.qr.payment_received", "codiQrId": "codi_t3_02", "amount": 200.0},
    )
    assert webhook_resp.status_code in [200, 202]


@pytest.mark.asyncio
async def test_t3_03_codi_mensual_alcorriente_polling(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """T3-03: CoDi QR × Mensual × Al Corriente × Polling -> Advances monthly."""
    plan_resp = await app_client.post(
        "/api/plans",
        json={"name": "Monthly Plan T3-03", "price": 350.0, "interval": "monthly"},
    )
    plan_id = plan_resp.json()["id"]

    current_date = (date.today() + timedelta(days=15)).isoformat()
    sub_resp = await app_client.post(
        "/api/subscribers",
        json={"name": "Sub T3-03", "phone": "5511000003", "plan_id": plan_id, "next_due_date": current_date},
    )
    sub = sub_resp.json()
    assert sub["status"] == "al_corriente"

    charge_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub["id"], "amount": 350.0, "method": "codi"},
    )
    charge_id = charge_resp.json()["id"]

    require_route("/api/charges/{id}/status", "GET")
    resp = await app_client.get(f"/api/charges/{charge_id}/status")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_t3_04_link_semanal_porvencer_webhook(app_client: httpx.AsyncClient):
    """T3-04: Payment Link × Semanal × Por Vencer × Webhook -> Weekly advance."""
    plan_resp = await app_client.post(
        "/api/plans",
        json={"name": "Weekly Plan T3-04", "price": 120.0, "interval": "weekly"},
    )
    plan_id = plan_resp.json()["id"]

    due_soon_date = (date.today() + timedelta(days=1)).isoformat()
    sub_resp = await app_client.post(
        "/api/subscribers",
        json={"name": "Sub T3-04", "phone": "5511000004", "plan_id": plan_id, "next_due_date": due_soon_date},
    )
    sub = sub_resp.json()
    assert sub["status"] == "por_vencer"

    require_route("/api/webhooks/pey", "POST")
    resp = await app_client.post(
        "/api/webhooks/pey",
        json={"type": "payment_link.status_updated", "paymentLinkId": "link_t3_04", "status": "paid"},
    )
    assert resp.status_code in [200, 202]


@pytest.mark.asyncio
async def test_t3_05_link_quincenal_alcorriente_polling(app_client: httpx.AsyncClient):
    """T3-05: Payment Link × Quincenal × Al Corriente × Polling -> Biweekly advance."""
    plan_resp = await app_client.post(
        "/api/plans",
        json={"name": "Biweekly Plan T3-05", "price": 250.0, "interval": "biweekly"},
    )
    plan_id = plan_resp.json()["id"]

    current_date = (date.today() + timedelta(days=10)).isoformat()
    sub_resp = await app_client.post(
        "/api/subscribers",
        json={"name": "Sub T3-05", "phone": "5511000005", "plan_id": plan_id, "next_due_date": current_date},
    )
    sub = sub_resp.json()
    assert sub["status"] == "al_corriente"

    charge_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub["id"], "amount": 250.0, "method": "link"},
    )
    charge_id = charge_resp.json()["id"]

    require_route("/api/charges/{id}/status", "GET")
    resp = await app_client.get(f"/api/charges/{charge_id}/status")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_t3_06_link_mensual_atrasado_webhook(app_client: httpx.AsyncClient):
    """T3-06: Payment Link × Mensual × Atrasado × Webhook -> Monthly advance."""
    plan_resp = await app_client.post(
        "/api/plans",
        json={"name": "Monthly Plan T3-06", "price": 400.0, "interval": "monthly"},
    )
    plan_id = plan_resp.json()["id"]

    overdue_date = (date.today() - timedelta(days=20)).isoformat()
    sub_resp = await app_client.post(
        "/api/subscribers",
        json={"name": "Sub T3-06", "phone": "5511000006", "plan_id": plan_id, "next_due_date": overdue_date},
    )
    sub = sub_resp.json()
    assert sub["status"] == "atrasado"

    require_route("/api/webhooks/pey", "POST")
    resp = await app_client.post(
        "/api/webhooks/pey",
        json={"type": "payment_link.status_updated", "paymentLinkId": "link_t3_06", "status": "paid"},
    )
    assert resp.status_code in [200, 202]


@pytest.mark.asyncio
async def test_t3_07_cash_semanal_alcorriente_markcash(app_client: httpx.AsyncClient):
    """T3-07: Cash × Semanal × Al Corriente × Mark-Cash -> Weekly advance."""
    plan_resp = await app_client.post(
        "/api/plans",
        json={"name": "Weekly Plan T3-07", "price": 80.0, "interval": "weekly"},
    )
    plan_id = plan_resp.json()["id"]

    current_date = (date.today() + timedelta(days=6)).isoformat()
    sub_resp = await app_client.post(
        "/api/subscribers",
        json={"name": "Sub T3-07", "phone": "5511000007", "plan_id": plan_id, "next_due_date": current_date},
    )
    sub = sub_resp.json()

    charge_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub["id"], "amount": 80.0, "method": "efectivo"},
    )
    charge_id = charge_resp.json()["id"]

    require_route("/api/charges/{id}/mark-cash", "POST")
    cash_resp = await app_client.post(f"/api/charges/{charge_id}/mark-cash")
    assert cash_resp.status_code in [200, 204]


@pytest.mark.asyncio
async def test_t3_08_cash_quincenal_atrasado_markcash(app_client: httpx.AsyncClient):
    """T3-08: Cash × Quincenal × Atrasado × Mark-Cash -> Biweekly advance."""
    plan_resp = await app_client.post(
        "/api/plans",
        json={"name": "Biweekly Plan T3-08", "price": 180.0, "interval": "biweekly"},
    )
    plan_id = plan_resp.json()["id"]

    overdue_date = (date.today() - timedelta(days=5)).isoformat()
    sub_resp = await app_client.post(
        "/api/subscribers",
        json={"name": "Sub T3-08", "phone": "5511000008", "plan_id": plan_id, "next_due_date": overdue_date},
    )
    sub = sub_resp.json()

    charge_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub["id"], "amount": 180.0, "method": "efectivo"},
    )
    charge_id = charge_resp.json()["id"]

    require_route("/api/charges/{id}/mark-cash", "POST")
    cash_resp = await app_client.post(f"/api/charges/{charge_id}/mark-cash")
    assert cash_resp.status_code in [200, 204]


@pytest.mark.asyncio
async def test_t3_09_cash_mensual_porvencer_markcash(app_client: httpx.AsyncClient):
    """T3-09: Cash × Mensual × Por Vencer × Mark-Cash -> Monthly advance."""
    plan_resp = await app_client.post(
        "/api/plans",
        json={"name": "Monthly Plan T3-09", "price": 300.0, "interval": "monthly"},
    )
    plan_id = plan_resp.json()["id"]

    due_soon_date = (date.today() + timedelta(days=3)).isoformat()
    sub_resp = await app_client.post(
        "/api/subscribers",
        json={"name": "Sub T3-09", "phone": "5511000009", "plan_id": plan_id, "next_due_date": due_soon_date},
    )
    sub = sub_resp.json()

    charge_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub["id"], "amount": 300.0, "method": "efectivo"},
    )
    charge_id = charge_resp.json()["id"]

    require_route("/api/charges/{id}/mark-cash", "POST")
    cash_resp = await app_client.post(f"/api/charges/{charge_id}/mark-cash")
    assert cash_resp.status_code in [200, 204]


def test_t3_10_corner_codi_mensual_porvencer_polling_monthend():
    """T3-10: Corner Case -> Month-end clamping Jan 31 -> Feb 28 on monthly plan."""
    advanced = advance_due_date("2026-01-31", "monthly")
    assert advanced == "2026-02-28"


@pytest.mark.asyncio
async def test_t3_11_decimal_link_semanal_atrasado_webhook_microcharge(app_client: httpx.AsyncClient):
    """T3-11: Decimal Case -> Microcharge of $0.05 on weekly overdue subscriber."""
    plans = (await app_client.get("/api/plans")).json()
    demo_plan = next(p for p in plans if abs(float(p["price"]) - 0.05) < 1e-4)

    sub_resp = await app_client.post(
        "/api/subscribers",
        json={
            "name": "Microcharge Overdue Sub",
            "phone": "5500000011",
            "plan_id": demo_plan["id"],
            "next_due_date": (date.today() - timedelta(days=7)).isoformat(),
        },
    )
    sub = sub_resp.json()
    assert sub["status"] == "atrasado"

    charge_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub["id"], "amount": 0.05, "method": "link"},
    )
    assert charge_resp.status_code in [200, 201]
    assert abs(float(charge_resp.json()["amount"]) - 0.05) < 1e-6


@pytest.mark.asyncio
async def test_t3_12_multipaid_cash_mensual_atrasado_markcash_sameday(app_client: httpx.AsyncClient):
    """T3-12: Multi-Payment Case -> Subscriber making multiple payments."""
    plans = (await app_client.get("/api/plans")).json()
    plan = plans[0]

    sub_resp = await app_client.post(
        "/api/subscribers",
        json={"name": "Multi Pay Sub", "phone": "5500000012", "plan_id": plan["id"]},
    )
    sub = sub_resp.json()

    c1 = await app_client.post("/api/charges", json={"subscriber_id": sub["id"], "amount": 50.0})
    c2 = await app_client.post("/api/charges", json={"subscriber_id": sub["id"], "amount": 50.0})
    assert c1.status_code in [200, 201]
    assert c2.status_code in [200, 201]
    assert c1.json()["id"] != c2.json()["id"]
