"""
Feature 2: Startup Idempotent Seeding
Validates demo plan ($0.05 MXN), 3 subscriber states, charges, and idempotency.
"""

import httpx
import pytest
from backend.seed import seed_if_empty


@pytest.mark.asyncio
async def test_f2_01_demo_plan_seeded_with_five_cents(app_client: httpx.AsyncClient):
    """Verifies that startup seeding creates a demo plan with price == 0.05 MXN."""
    resp = await app_client.get("/api/plans")
    assert resp.status_code == 200
    plans = resp.json()
    assert isinstance(plans, list)

    demo_plans = [p for p in plans if abs(float(p["price"]) - 0.05) < 1e-4]
    assert len(demo_plans) >= 1, f"Expected at least one demo plan priced at $0.05 MXN, found: {plans}"
    assert "demo" in demo_plans[0]["name"].lower() or demo_plans[0]["id"] == "demo"


@pytest.mark.asyncio
async def test_f2_02_subscribers_cover_all_three_statuses(app_client: httpx.AsyncClient):
    """Verifies seeded subscribers cover 'atrasado', 'por_vencer', and 'al_corriente' states."""
    resp = await app_client.get("/api/subscribers")
    assert resp.status_code == 200
    subscribers = resp.json()
    assert len(subscribers) >= 3

    statuses = {s["status"] for s in subscribers}
    assert "atrasado" in statuses, f"Missing 'atrasado' status among seeded subscribers: {statuses}"
    assert "por_vencer" in statuses, f"Missing 'por_vencer' status among seeded subscribers: {statuses}"
    assert "al_corriente" in statuses, f"Missing 'al_corriente' status among seeded subscribers: {statuses}"


@pytest.mark.asyncio
async def test_f2_03_charge_history_seeded(app_client: httpx.AsyncClient):
    """Verifies that startup seeding seeds initial charge movements with amounts > 0."""
    resp = await app_client.get("/api/charges")
    assert resp.status_code == 200
    charges = resp.json()
    assert isinstance(charges, list)
    assert len(charges) > 0, "Expected non-empty seeded charges list"

    for c in charges:
        assert float(c["amount"]) > 0
        assert c["status"] in ["pending", "paid", "expired", "failed"]


@pytest.mark.asyncio
async def test_f2_04_seeding_is_strictly_idempotent(app_client: httpx.AsyncClient, isolated_db_path: str):
    """Verifies calling seed_if_empty on an already seeded database does not duplicate records."""
    resp_plans_1 = await app_client.get("/api/plans")
    resp_subs_1 = await app_client.get("/api/subscribers")
    resp_charges_1 = await app_client.get("/api/charges")

    count_plans_1 = len(resp_plans_1.json())
    count_subs_1 = len(resp_subs_1.json())
    count_charges_1 = len(resp_charges_1.json())

    # Call seeder again directly
    seeded_again = seed_if_empty(isolated_db_path)
    assert seeded_again is False, "Expected seed_if_empty to return False when already seeded"

    resp_plans_2 = await app_client.get("/api/plans")
    resp_subs_2 = await app_client.get("/api/subscribers")
    resp_charges_2 = await app_client.get("/api/charges")

    assert len(resp_plans_2.json()) == count_plans_1
    assert len(resp_subs_2.json()) == count_subs_1
    assert len(resp_charges_2.json()) == count_charges_1


@pytest.mark.asyncio
async def test_f2_05_seeded_dashboard_metrics_consistent(app_client: httpx.AsyncClient):
    """Verifies dashboard metrics match seeded subscriber breakdown."""
    resp_dash = await app_client.get("/api/dashboard")
    assert resp_dash.status_code == 200
    data = resp_dash.json()

    assert data["total_subscribers"] >= 3
    assert data["active_subscribers"] >= 3
    assert data["overdue_count"] >= 1
    assert data["due_soon_count"] >= 1
    assert data["current_count"] >= 1
    assert (
        data["total_subscribers"]
        == data["overdue_count"] + data["due_soon_count"] + data["current_count"]
    )
    assert data["expected_monthly"] > 0
