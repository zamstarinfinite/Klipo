"""
Feature 4: Core CRUD API Endpoints
Validates dashboard summary, plan CRUD, subscriber CRUD, and charges history.
"""

import httpx
import pytest


@pytest.mark.asyncio
async def test_f4_01_get_dashboard_summary(app_client: httpx.AsyncClient):
    """Verifies GET /api/dashboard returns correct structure and data types."""
    resp = await app_client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json()

    for key in [
        "total_subscribers",
        "active_subscribers",
        "overdue_count",
        "due_soon_count",
        "current_count",
        "expected_monthly",
        "collected_month",
        "recent_movements",
    ]:
        assert key in data, f"Key '{key}' missing from /api/dashboard response"

    assert isinstance(data["recent_movements"], list)
    assert isinstance(data["total_subscribers"], int)
    assert isinstance(data["expected_monthly"], (int, float))


@pytest.mark.asyncio
async def test_f4_02_create_and_list_plan(app_client: httpx.AsyncClient):
    """Verifies creating a new plan via POST /api/plans and retrieving it via GET /api/plans."""
    new_plan = {
        "name": "E2E CrossFit Gold",
        "price": 550.0,
        "interval": "monthly",
        "description": "Plan creado para prueba E2E",
        "icon": "gym",
        "charge_day": 15,
    }
    create_resp = await app_client.post("/api/plans", json=new_plan)
    assert create_resp.status_code in [200, 201]
    plan_data = create_resp.json()
    assert plan_data["name"] == "E2E CrossFit Gold"
    assert float(plan_data["price"]) == 550.0
    plan_id = plan_data["id"]

    list_resp = await app_client.get("/api/plans")
    assert list_resp.status_code == 200
    plans = list_resp.json()
    assert any(p["id"] == plan_id for p in plans)


@pytest.mark.asyncio
async def test_f4_03_create_and_list_subscriber(app_client: httpx.AsyncClient):
    """Verifies creating a subscriber via POST /api/subscribers and listing it."""
    # Retrieve an existing plan ID first
    plans_resp = await app_client.get("/api/plans")
    assert plans_resp.status_code == 200
    plan_id = plans_resp.json()[0]["id"]

    new_sub = {
        "name": "Valeria Test E2E",
        "phone": "5512349999",
        "plan_id": plan_id,
        "note": "Suscriptor E2E de prueba",
    }
    create_resp = await app_client.post("/api/subscribers", json=new_sub)
    assert create_resp.status_code in [200, 201]
    sub_data = create_resp.json()
    assert sub_data["name"] == "Valeria Test E2E"
    assert sub_data["plan_id"] == plan_id
    assert sub_data["status"] in ["atrasado", "por_vencer", "al_corriente"]

    list_resp = await app_client.get("/api/subscribers")
    assert list_resp.status_code == 200
    subs = list_resp.json()
    assert any(s["id"] == sub_data["id"] for s in subs)


@pytest.mark.asyncio
async def test_f4_04_get_charges_history(app_client: httpx.AsyncClient):
    """Verifies GET /api/charges returns charge movements with subscriber and plan names."""
    resp = await app_client.get("/api/charges")
    assert resp.status_code == 200
    charges = resp.json()
    assert isinstance(charges, list)
    assert len(charges) > 0

    first_charge = charges[0]
    for field in ["id", "subscriber_id", "plan_id", "amount", "status", "created_at"]:
        assert field in first_charge, f"Field '{field}' missing from charge object"


@pytest.mark.asyncio
async def test_f4_05_subscriber_instant_charge_creation(app_client: httpx.AsyncClient):
    """Verifies creating a subscriber with instant_charge=True creates a pending charge."""
    plans_resp = await app_client.get("/api/plans")
    plan = plans_resp.json()[0]

    sub_payload = {
        "name": "Ignacio Instant Charge",
        "phone": "5511223344",
        "plan_id": plan["id"],
        "instant_charge": True,
    }
    create_resp = await app_client.post("/api/subscribers", json=sub_payload)
    assert create_resp.status_code in [200, 201]
    sub_data = create_resp.json()

    # Verify charge was created for this subscriber
    charges_resp = await app_client.get(f"/api/charges?subscriber_id={sub_data['id']}")
    assert charges_resp.status_code == 200
    charges = charges_resp.json()
    assert len(charges) >= 1
    assert charges[0]["subscriber_id"] == sub_data["id"]
    assert charges[0]["status"] in ["pending", "pendiente"]
