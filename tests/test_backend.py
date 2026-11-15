import os
import sqlite3
import tempfile
from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient

from backend.db import (
    advance_due_date,
    calculate_subscriber_status,
    get_connection,
    init_db,
)
from backend.main import app
from backend.seed import seed_if_empty


@pytest.fixture
def temp_db(monkeypatch):
    """Fixture providing an isolated temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = f.name

    monkeypatch.setenv("DATABASE_PATH", temp_path)
    init_db(temp_path)

    yield temp_path

    if os.path.exists(temp_path):
        os.remove(temp_path)


def test_db_init_and_tables(temp_db):
    """Verify table creation, column structure, foreign keys, and WAL mode."""
    conn = get_connection(temp_db)
    cursor = conn.cursor()

    # Check WAL mode
    cursor.execute("PRAGMA journal_mode;")
    mode = cursor.fetchone()[0]
    assert mode.lower() == "wal"

    # Check foreign keys enabled
    cursor.execute("PRAGMA foreign_keys;")
    fk = cursor.fetchone()[0]
    assert fk == 1

    # Verify tables exist
    cursor.execute("""
        SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;
    """)
    tables = [row["name"] for row in cursor.fetchall()]
    assert "plans" in tables
    assert "subscribers" in tables
    assert "charges" in tables

    # Verify indices exist
    cursor.execute("""
        SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%';
    """)
    indices = [row["name"] for row in cursor.fetchall()]
    assert "idx_subscribers_plan_id" in indices
    assert "idx_charges_subscriber_id" in indices
    assert "idx_charges_status" in indices

    conn.close()


def test_dynamic_status_calculation():
    """Verify subscriber status computation logic according to specification."""
    ref_date = date(2026, 11, 15)

    # 1. Overdue: next_due_date < today -> 'atrasado'
    assert calculate_subscriber_status("2026-11-14", reference_date=ref_date) == "atrasado"
    assert calculate_subscriber_status("2026-10-01", reference_date=ref_date) == "atrasado"

    # 2. Due soon: 0 <= diff <= 3 days -> 'por_vencer'
    assert calculate_subscriber_status("2026-11-15", reference_date=ref_date) == "por_vencer"  # diff = 0 (today)
    assert calculate_subscriber_status("2026-11-16", reference_date=ref_date) == "por_vencer"  # diff = 1
    assert calculate_subscriber_status("2026-11-17", reference_date=ref_date) == "por_vencer"  # diff = 2
    assert calculate_subscriber_status("2026-11-18", reference_date=ref_date) == "por_vencer"  # diff = 3

    # 3. Current: diff > 3 days -> 'al_corriente'
    assert calculate_subscriber_status("2026-11-19", reference_date=ref_date) == "al_corriente"  # diff = 4
    assert calculate_subscriber_status("2026-12-15", reference_date=ref_date) == "al_corriente"  # diff = 30


def test_advance_due_date():
    """Verify recurrence calculation logic."""
    start = "2026-01-15"
    assert advance_due_date(start, "weekly") == "2026-01-22"
    assert advance_due_date(start, "biweekly") == "2026-01-30"
    assert advance_due_date(start, "monthly") == "2026-02-15"

    # End of month edge case (Jan 31 -> Feb 28 in non-leap year)
    assert advance_due_date("2026-01-31", "monthly") == "2026-02-28"


def test_idempotent_seeding(temp_db):
    """Verify seeding runs once on empty DB and does not duplicate data on subsequent calls."""
    # First seed call
    seeded = seed_if_empty(temp_db)
    assert seeded is True

    conn = get_connection(temp_db)
    cursor = conn.cursor()

    # Check plans
    cursor.execute("SELECT COUNT(*) FROM plans;")
    plan_count = cursor.fetchone()[0]
    assert plan_count == 4

    # Check demo plan with $0.05 MXN
    cursor.execute("SELECT id, name, price FROM plans WHERE id = 'demo';")
    demo_plan = cursor.fetchone()
    assert demo_plan is not None
    assert demo_plan["name"] == "Demo Hackathon · Prueba Real"
    assert demo_plan["price"] == 0.05

    # Check subscribers (16 total: 15 business + 1 demo)
    cursor.execute("SELECT COUNT(*) FROM subscribers;")
    sub_count = cursor.fetchone()[0]
    assert sub_count == 16

    # Verify demo subscriber exists
    cursor.execute("SELECT * FROM subscribers WHERE id = 'demo_sub';")
    demo_sub = cursor.fetchone()
    assert demo_sub is not None
    assert demo_sub["phone"] == "5512345678"
    assert demo_sub["plan_id"] == "demo"

    # Verify charges
    cursor.execute("SELECT COUNT(*) FROM charges;")
    charge_count = cursor.fetchone()[0]
    assert charge_count == 4

    conn.close()

    # Second seed call must be idempotent (no-op)
    seeded_again = seed_if_empty(temp_db)
    assert seeded_again is False

    # Check counts remain identical
    conn = get_connection(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM plans;")
    assert cursor.fetchone()[0] == plan_count
    cursor.execute("SELECT COUNT(*) FROM subscribers;")
    assert cursor.fetchone()[0] == sub_count
    cursor.execute("SELECT COUNT(*) FROM charges;")
    assert cursor.fetchone()[0] == charge_count
    conn.close()


def test_api_endpoints(temp_db):
    """Test all REST API endpoints using FastAPI TestClient."""
    seed_if_empty(temp_db)

    with TestClient(app) as client:
        # 1. Health check
        res_health = client.get("/api/health")
        assert res_health.status_code == 200
        assert res_health.json()["status"] == "ok"
        assert res_health.json()["database"] == "connected"

        # 2. Dashboard
        res_dash = client.get("/api/dashboard")
        assert res_dash.status_code == 200
        dash_data = res_dash.json()
        assert dash_data["total_subscribers"] == 16
        assert dash_data["active_subscribers"] == 16
        assert dash_data["overdue_count"] >= 3
        assert dash_data["due_soon_count"] >= 2
        assert dash_data["current_count"] >= 10
        assert dash_data["expected_monthly"] > 0
        assert isinstance(dash_data["recent_movements"], list)
        assert len(dash_data["recent_movements"]) > 0

        # 3. Plans
        res_plans = client.get("/api/plans")
        assert res_plans.status_code == 200
        plans_list = res_plans.json()
        assert len(plans_list) == 4
        demo_p = next(p for p in plans_list if p["id"] == "demo")
        assert demo_p["price"] == 0.05
        assert demo_p["active_subscribers"] == 1

        # Test GET single plan
        res_single_plan = client.get("/api/plans/gym")
        assert res_single_plan.status_code == 200
        assert res_single_plan.json()["name"] == "Gym Fit"

        # Test GET nonexistent plan -> 404
        assert client.get("/api/plans/nonexistent").status_code == 404

        # Test POST /api/plans
        res_new_plan = client.post("/api/plans", json={
            "id": "crossfit",
            "name": "CrossFit Pro",
            "price": 550.0,
            "interval": "monthly",
            "description": "Entrenamiento de alta intensidad",
            "icon": "gym",
            "charge_day": 10,
        })
        assert res_new_plan.status_code == 201
        assert res_new_plan.json()["id"] == "crossfit"
        assert res_new_plan.json()["price"] == 550.0

        # Test PATCH /api/plans/{id}
        res_patch_plan = client.patch("/api/plans/crossfit", json={"price": 600.0})
        assert res_patch_plan.status_code == 200
        assert res_patch_plan.json()["price"] == 600.0
        assert res_patch_plan.json()["name"] == "CrossFit Pro"

        # 4. Subscribers
        res_subs = client.get("/api/subscribers")
        assert res_subs.status_code == 200
        subs_list = res_subs.json()
        assert len(subs_list) == 16

        # Check status filtering
        res_atrasados = client.get("/api/subscribers?status=atrasado")
        assert res_atrasados.status_code == 200
        for s in res_atrasados.json():
            assert s["status"] == "atrasado"

        res_vencer = client.get("/api/subscribers?status=por_vencer")
        assert res_vencer.status_code == 200
        for s in res_vencer.json():
            assert s["status"] == "por_vencer"

        res_corriente = client.get("/api/subscribers?status=al_corriente")
        assert res_corriente.status_code == 200
        for s in res_corriente.json():
            assert s["status"] == "al_corriente"

        # Check plan_id filtering
        res_gym_subs = client.get("/api/subscribers?plan_id=gym")
        assert res_gym_subs.status_code == 200
        assert len(res_gym_subs.json()) > 0
        for s in res_gym_subs.json():
            assert s["plan_id"] == "gym"

        # Check search filtering
        res_search_name = client.get("/api/subscribers?search=Roberto")
        assert res_search_name.status_code == 200
        assert len(res_search_name.json()) == 1
        assert res_search_name.json()[0]["name"] == "Roberto Gómez"

        res_search_phone = client.get("/api/subscribers?search=5512345678")
        assert res_search_phone.status_code == 200
        assert len(res_search_phone.json()) == 1
        assert res_search_phone.json()[0]["name"] == "Invitado Demo"

        # Test GET single subscriber
        res_single_sub = client.get("/api/subscribers/roberto")
        assert res_single_sub.status_code == 200
        assert res_single_sub.json()["name"] == "Roberto Gómez"

        # Test GET nonexistent subscriber -> 404
        assert client.get("/api/subscribers/nonexistent").status_code == 404

        # Test POST /api/subscribers
        res_new_sub = client.post("/api/subscribers", json={
            "name": "Esteban Quito",
            "phone": "5599887766",
            "plan_id": "gym",
            "note": "Inscripción presencial",
        })
        assert res_new_sub.status_code == 201
        new_sub_data = res_new_sub.json()
        assert new_sub_data["name"] == "Esteban Quito"
        assert new_sub_data["plan_id"] == "gym"
        assert new_sub_data["status"] == "al_corriente"

        # Test POST /api/subscribers with invalid plan -> 400
        res_invalid_plan_sub = client.post("/api/subscribers", json={
            "name": "Bad Sub",
            "phone": "5500000000",
            "plan_id": "plan_does_not_exist",
        })
        assert res_invalid_plan_sub.status_code == 400

        # Test PATCH /api/subscribers/{id}
        res_patch_sub = client.patch(f"/api/subscribers/{new_sub_data['id']}", json={"note": "Nota actualizada"})
        assert res_patch_sub.status_code == 200
        assert res_patch_sub.json()["note"] == "Nota actualizada"

        # 5. Charges
        res_charges = client.get("/api/charges")
        assert res_charges.status_code == 200
        charges_list = res_charges.json()
        assert len(charges_list) >= 4

        # Filter charges by subscriber
        res_charges_carlos = client.get("/api/charges?subscriber_id=carlos")
        assert res_charges_carlos.status_code == 200
        assert len(res_charges_carlos.json()) >= 1
        assert res_charges_carlos.json()[0]["subscriber_id"] == "carlos"

        # Filter charges by status
        res_charges_paid = client.get("/api/charges?status=paid")
        assert res_charges_paid.status_code == 200
        for c in res_charges_paid.json():
            assert c["status"] == "paid"

        # Test POST /api/charges
        res_new_charge = client.post("/api/charges", json={
            "subscriber_id": "roberto",
            "amount": 350.0,
            "concept": "Cobro mensualidad Gym",
        })
        assert res_new_charge.status_code == 201
        new_charge_data = res_new_charge.json()
        assert new_charge_data["subscriber_id"] == "roberto"
        assert new_charge_data["amount"] == 350.0
        assert new_charge_data["status"] == "pending"

        # 6. Root endpoint
        res_root = client.get("/")
        assert res_root.status_code == 200
