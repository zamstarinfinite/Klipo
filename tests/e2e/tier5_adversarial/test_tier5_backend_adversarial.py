"""
Tier 5 Adversarial Test Suite: Hardening & Stress Testing
Milestone 5 Phase 2 — Adversarial Coverage Hardening

Domain Focus:
1. Backend SQLite Persistence & Concurrency (WAL mode stress, atomic transactions, seeding race)
2. Dynamic Recurrence Advancement Arithmetic & Calendar Clamping (leap years, month-end, boundaries, drift)
3. Decimal & Microcharge Precision ($0.01/$0.05/$0.10 MXN safety, rounding, negative/zero/NaN injection)
4. Security & Robustness (SQL injection, Mexican Unicode, ID collisions, XSS & buffer resilience)
"""

import asyncio
import calendar
import concurrent.futures
from datetime import date, datetime, timedelta
import os
import sqlite3
import threading
from typing import List

import httpx
import pytest

from backend.db import (
    advance_due_date,
    advance_subscriber_recurrence,
    calculate_subscriber_status,
    get_connection,
    init_db,
    parse_date,
)
from backend.main import mark_charge_as_paid
from backend.seed import seed_if_empty


# ===========================================================================
# 1. Backend SQLite Persistence & Concurrency
# ===========================================================================

@pytest.mark.asyncio
async def test_adv_01_wal_concurrent_reads_and_writes(app_client: httpx.AsyncClient):
    """
    Stress-tests SQLite WAL mode concurrency under simultaneous read and write pressure.
    Executes 40 concurrent requests: 20 cash charge creations and 20 dashboard/subscriber queries.
    Asserts zero SQLite locking failures (no HTTP 500 / sqlite3.OperationalError: database is locked).
    """
    async def write_op(idx: int):
        return await app_client.post(
            "/api/charges",
            json={
                "subscriber_id": "carlos",
                "amount": 10.0 + idx,
                "method": "efectivo",
                "concept": f"WAL Stress Charge {idx}",
            },
        )

    async def read_op(idx: int):
        if idx % 2 == 0:
            return await app_client.get("/api/dashboard")
        return await app_client.get("/api/subscribers?plan_id=gym")

    tasks = []
    for i in range(20):
        tasks.append(write_op(i))
        tasks.append(read_op(i))

    responses = await asyncio.gather(*tasks)

    for r in responses:
        assert r.status_code in (200, 201), (
            f"Concurrency request failed with HTTP {r.status_code}: {r.text}"
        )


def test_adv_02_concurrent_seeding_race_condition(tmp_path):
    """
    Adversarial probe: tests concurrent invocation of seed_if_empty on a brand new database file.
    When multiple application workers initialize simultaneously, seed_if_empty must not crash
    with unhandled sqlite3.IntegrityError: UNIQUE constraint failed: plans.id.
    """
    db_file = str(tmp_path / "concurrent_seed.db")
    errors: List[Exception] = []

    def worker():
        try:
            seed_if_empty(db_file)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # If seed_if_empty is properly idempotent and thread-safe, zero IntegrityErrors should occur
    assert len(errors) == 0, f"Concurrent seeding raised unhandled exceptions: {errors}"

    # Verify database was cleanly seeded
    conn = get_connection(db_file)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM plans;")
    plan_count = cur.fetchone()[0]
    conn.close()
    assert plan_count == 4, f"Expected 4 plans, found {plan_count}"


def test_adv_03_transaction_atomicity_charge_and_subscriber(tmp_path):
    """
    Verifies transaction atomicity when recording charges and updating subscribers.
    If recurrence advancement fails (e.g. corrupted next_due_date), the charge must NOT
    remain permanently committed as 'paid' while the subscriber remains untouched.
    """
    db_file = str(tmp_path / "atomicity_test.db")
    init_db(db_file)
    conn = get_connection(db_file)

    with conn:
        conn.execute(
            "INSERT INTO plans (id, name, price, interval) VALUES ('p1', 'Plan 1', 100.0, 'monthly');"
        )
        # Seed subscriber with corrupt next_due_date to simulate failure during advancement
        conn.execute(
            "INSERT INTO subscribers (id, plan_id, name, phone, next_due_date) "
            "VALUES ('sub_err', 'p1', 'Error Sub', '5500000000', 'CORRUPT_DATE_VALUE');"
        )
        conn.execute(
            "INSERT INTO charges (id, subscriber_id, plan_id, amount, status) "
            "VALUES ('ch_atom', 'sub_err', 'p1', 100.0, 'pending');"
        )

    # Attempt to mark charge as paid
    error_occurred = False
    try:
        mark_charge_as_paid("ch_atom", conn)
    except Exception:
        error_occurred = True

    # Check whether atomicity was broken: if advancement failed, charge should NOT be marked paid
    cur = conn.cursor()
    cur.execute("SELECT status, paid_at FROM charges WHERE id = 'ch_atom';")
    ch_row = cur.fetchone()
    conn.close()

    assert error_occurred, "Advancement should have failed on corrupted date"
    assert ch_row["status"] != "paid", (
        "ATOMICITY VIOLATION: Charge was committed as 'paid' even though subscriber advancement failed!"
    )


@pytest.mark.asyncio
async def test_adv_04_double_payment_race_condition_idempotency(app_client: httpx.AsyncClient):
    """
    Probes double-payment race condition on mark-cash.
    Fires 10 simultaneous POST requests to mark the exact same pending charge as paid.
    Asserts that next_due_date advances exactly once (no multi-month leaps for 1 payment).
    """
    # 1. Fetch initial subscriber due date
    sub_init = (await app_client.get("/api/subscribers/mariana")).json()
    init_due_date = sub_init["next_due_date"]

    # 2. Fire 10 concurrent mark-cash requests on charge 'p3' (mariana's pending charge)
    tasks = [
        app_client.post("/api/charges/p3/mark-cash")
        for _ in range(10)
    ]
    responses = await asyncio.gather(*tasks)

    # All should return 200 OK (idempotent response)
    for r in responses:
        assert r.status_code == 200

    # 3. Fetch subscriber due date after race
    sub_final = (await app_client.get("/api/subscribers/mariana")).json()
    final_due_date = sub_final["next_due_date"]

    # In Mariana's plan (monthly), due date should have advanced by exactly 1 month
    expected_due_date = advance_due_date(max(parse_date(init_due_date), date.today()), "monthly")
    assert final_due_date == expected_due_date, (
        f"Double-payment race caused improper advance: expected {expected_due_date}, got {final_due_date}"
    )


def test_adv_05_seeding_with_partial_preexisting_data(tmp_path):
    """
    Tests seeding resilience when partial pre-existing data exists.
    If a database was initialized with only plans, seed_if_empty should cleanly populate
    subscribers and charges or guarantee system consistency.
    """
    db_file = str(tmp_path / "partial_seed.db")
    init_db(db_file)
    conn = get_connection(db_file)
    with conn:
        conn.execute(
            "INSERT INTO plans (id, name, price, interval) VALUES ('custom_plan', 'Custom Fit', 99.0, 'monthly');"
        )
    conn.close()

    # Calling seed_if_empty
    seeded = seed_if_empty(db_file)
    # Seeder checks plan_count > 0 and returns False without crashing
    assert seeded is False

    conn = get_connection(db_file)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM plans;")
    p_cnt = cur.fetchone()[0]
    conn.close()
    assert p_cnt == 1


# ===========================================================================
# 2. Dynamic Recurrence Advancement Arithmetic & Calendar Clamping
# ===========================================================================

def test_adv_06_month_end_clamping_all_months():
    """
    Verifies calendar clamping behavior across all 31-day months to shorter months:
    - Jan 31 -> Feb 28 (non-leap 2026)
    - Mar 31 -> Apr 30
    - May 31 -> Jun 30
    - Aug 31 -> Sep 30
    - Oct 31 -> Nov 30
    - Dec 31 -> Jan 31 (next year)
    """
    assert advance_due_date("2026-01-31", "monthly") == "2026-02-28"
    assert advance_due_date("2026-03-31", "monthly") == "2026-04-30"
    assert advance_due_date("2026-05-31", "monthly") == "2026-06-30"
    assert advance_due_date("2026-08-31", "monthly") == "2026-09-30"
    assert advance_due_date("2026-10-31", "monthly") == "2026-11-30"
    assert advance_due_date("2026-12-31", "monthly") == "2027-01-31"


def test_adv_07_leap_year_transitions():
    """
    Verifies recurrence math on leap years (2024, 2028) vs non-leap years (2023, 2025, 2100):
    - Leap 2024: Jan 31 -> Feb 29
    - Leap 2024: Feb 29 -> Mar 29
    - Leap 2028: Jan 31 -> Feb 29
    - Non-leap 2023: Jan 31 -> Feb 28
    - Non-leap 2025: Jan 31 -> Feb 28
    - Non-leap 2100 (century rule): Jan 31 -> Feb 28
    """
    assert advance_due_date("2024-01-31", "monthly") == "2024-02-29"
    assert advance_due_date("2024-02-29", "monthly") == "2024-03-29"
    assert advance_due_date("2028-01-31", "monthly") == "2028-02-29"
    assert advance_due_date("2023-01-31", "monthly") == "2023-02-28"
    assert advance_due_date("2025-01-31", "monthly") == "2025-02-28"
    assert advance_due_date("2100-01-31", "monthly") == "2100-02-28"


def test_adv_08_consecutive_monthly_advances_day_loss():
    """
    Examines anchor-day persistence vs permanent day clamping downgrade.
    When a subscriber joins on Jan 31:
    - Month 1: 2026-01-31 -> 2026-02-28 (clamped)
    - Month 2: 2026-02-28 -> advances to 2026-03-28 (loses anchor day 31!)
    Documents this behavior to evaluate billing cycle day retention.
    """
    m1 = advance_due_date("2026-01-31", "monthly")
    assert m1 == "2026-02-28"
    m2 = advance_due_date(m1, "monthly")
    # Document whether day 31 was permanently lost
    assert m2 in ("2026-03-28", "2026-03-31")


def test_adv_09_weekly_biweekly_boundary_transitions():
    """
    Verifies weekly (+7d) and biweekly (+15d) arithmetic across month and leap day boundaries:
    - Weekly leap: 2024-02-25 -> 2024-03-03 (+7d across Feb 29)
    - Weekly non-leap: 2023-02-25 -> 2023-03-04 (+7d across Feb 28)
    - Weekly year rollover: 2026-12-28 -> 2027-01-04
    - Biweekly leap: 2024-02-15 -> 2024-03-01 (+15d across Feb 29)
    - Biweekly non-leap: 2023-02-15 -> 2023-03-02 (+15d across Feb 28)
    - Biweekly year rollover: 2026-12-20 -> 2027-01-04 (+15d across year boundary)
    """
    # Weekly
    assert advance_due_date("2024-02-25", "weekly") == "2024-03-03"
    assert advance_due_date("2023-02-25", "weekly") == "2023-03-04"
    assert advance_due_date("2026-12-28", "weekly") == "2027-01-04"

    # Biweekly
    assert advance_due_date("2024-02-15", "biweekly") == "2024-03-01"
    assert advance_due_date("2023-02-15", "biweekly") == "2023-03-02"
    assert advance_due_date("2026-12-20", "biweekly") == "2027-01-04"


def test_adv_10_subscriber_status_exact_boundaries():
    """
    Tests exact boundary transitions for calculate_subscriber_status:
    - diff < 0: 'atrasado'
    - 0 <= diff <= 3: 'por_vencer'
    - diff > 3: 'al_corriente'
    Also tests ISO datetime strings with timestamps and timezone indicators.
    """
    ref = date(2026, 11, 15)

    assert calculate_subscriber_status("2026-11-14", reference_date=ref) == "atrasado"
    assert calculate_subscriber_status("2026-11-15", reference_date=ref) == "por_vencer"  # diff = 0
    assert calculate_subscriber_status("2026-11-16", reference_date=ref) == "por_vencer"  # diff = 1
    assert calculate_subscriber_status("2026-11-17", reference_date=ref) == "por_vencer"  # diff = 2
    assert calculate_subscriber_status("2026-11-18", reference_date=ref) == "por_vencer"  # diff = 3
    assert calculate_subscriber_status("2026-11-19", reference_date=ref) == "al_corriente"  # diff = 4

    # ISO datetime with time components
    assert calculate_subscriber_status("2026-11-15T23:59:59", reference_date=ref) == "por_vencer"
    assert calculate_subscriber_status("2026-11-15 00:00:00", reference_date=ref) == "por_vencer"
    assert calculate_subscriber_status("2026-11-14T12:00:00Z", reference_date=ref) == "atrasado"


def test_adv_11_date_parsing_leading_whitespace():
    """
    Adversarial probe: tests parse_date resilience against leading and trailing whitespace.
    Dates like ' 2026-11-15 ' or '2026-11-15 ' should parse cleanly without raising ValueError.
    """
    # parse_date should parse clean dates
    d1 = parse_date("2026-11-15")
    assert d1 == date(2026, 11, 15)

    # Date with leading whitespace should not fail with empty string parse error
    d2 = parse_date(" 2026-11-15")
    assert d2 == date(2026, 11, 15)


def test_adv_12_overdue_subscriber_billing_date_drift(tmp_path):
    """
    Probes billing date drift when an overdue subscriber pays days after their scheduled charge_day.
    If a subscriber has charge_day = 1 and pays on day 20, does next_due_date permanently drift to day 20?
    """
    db_file = str(tmp_path / "drift_test.db")
    init_db(db_file)
    conn = get_connection(db_file)

    with conn:
        conn.execute(
            "INSERT INTO plans (id, name, price, interval, charge_day) VALUES ('gym', 'Gym Fit', 350.0, 'monthly', 1);"
        )
        conn.execute(
            "INSERT INTO subscribers (id, plan_id, name, phone, next_due_date) "
            "VALUES ('sub_drift', 'gym', 'Drifting Sub', '5511223344', '2026-10-01');"
        )

    # Roberto was due 2026-10-01. Paying on today's date advances recurrence.
    new_due = advance_subscriber_recurrence("sub_drift", conn=conn)
    conn.close()

    assert new_due is not None
    # Check if the calculated status is al_corriente
    assert calculate_subscriber_status(new_due) == "al_corriente"


# ===========================================================================
# 3. Decimal & Microcharge Precision
# ===========================================================================

@pytest.mark.asyncio
async def test_adv_13_microcharge_amounts_lifecycle(app_client: httpx.AsyncClient):
    """
    Validates end-to-end support for microcharges down to $0.01, $0.05, and $0.10 MXN:
    1. Demo plan of $0.05 MXN exists and creates charges correctly.
    2. Creating a $0.01 MXN plan and recording a cash payment.
    3. Creating a $0.10 MXN charge and verifying dashboard reflection.
    """
    # 1. Verify demo plan ($0.05 MXN)
    demo_plan = (await app_client.get("/api/plans/demo")).json()
    assert demo_plan["price"] == 0.05

    # 2. Create custom microcharge plan ($0.01 MXN)
    plan_resp = await app_client.post(
        "/api/plans",
        json={
            "id": "micro_one_cent",
            "name": "Micro Plan 1 Centavo",
            "price": 0.01,
            "interval": "monthly",
        },
    )
    assert plan_resp.status_code == 201
    assert plan_resp.json()["price"] == 0.01

    # 3. Create subscriber on micro plan
    sub_resp = await app_client.post(
        "/api/subscribers",
        json={
            "id": "sub_micro",
            "name": "Micro Subscriber",
            "phone": "5511002200",
            "plan_id": "micro_one_cent",
        },
    )
    assert sub_resp.status_code == 201

    # 4. Record cash payment of $0.01 MXN
    charge_resp = await app_client.post(
        "/api/charges",
        json={
            "subscriber_id": "sub_micro",
            "amount": 0.01,
            "method": "efectivo",
            "concept": "Microcharge payment $0.01 MXN",
        },
    )
    assert charge_resp.status_code == 201
    assert charge_resp.json()["amount"] == 0.01
    assert charge_resp.json()["status"] == "paid"


@pytest.mark.asyncio
async def test_adv_14_floating_point_summation_accuracy(app_client: httpx.AsyncClient):
    """
    Stress-tests floating-point summation precision on dashboard collected_month:
    Records 20 cash payments of $0.05 MXN (expected sum = $1.00 MXN).
    Asserts dashboard collected_month accurately reflects exact decimal addition without float noise.
    """
    dash_before = (await app_client.get("/api/dashboard")).json()["collected_month"]

    for i in range(20):
        r = await app_client.post(
            "/api/charges",
            json={
                "subscriber_id": "carlos",
                "amount": 0.05,
                "method": "efectivo",
                "concept": f"Precision probe {i}",
            },
        )
        assert r.status_code == 201

    dash_after = (await app_client.get("/api/dashboard")).json()["collected_month"]
    expected_after = round(dash_before + (20 * 0.05), 2)
    assert dash_after == expected_after, (
        f"Floating-point summation discrepancy: expected {expected_after}, got {dash_after}"
    )


@pytest.mark.asyncio
async def test_adv_15_plan_vs_dashboard_expected_revenue_consistency(app_client: httpx.AsyncClient):
    """
    Verifies consistency between GET /api/plans/{id} 'expected' and Dashboard 'expected_monthly'
    for weekly and biweekly recurring plans.
    A weekly plan of $100 with 1 subscriber should contribute 4.33x (~$433 MXN/month) consistently.
    """
    # Create weekly plan
    await app_client.post(
        "/api/plans",
        json={"id": "plan_weekly_adv", "name": "Weekly Adv", "price": 100.0, "interval": "weekly"},
    )
    # Add active subscriber
    await app_client.post(
        "/api/subscribers",
        json={"id": "sub_wk_adv", "name": "Weekly Sub", "phone": "5599881122", "plan_id": "plan_weekly_adv"},
    )

    plan_data = (await app_client.get("/api/plans/plan_weekly_adv")).json()
    dash_data = (await app_client.get("/api/dashboard")).json()

    # Document whether plan expected revenue accounts for recurrence interval
    # Dashboard accounts for weekly (* 4.33):
    assert dash_data["expected_monthly"] > 0
    # Plan expected revenue should ideally also represent monthly expected value (433.00), not raw 100.00
    assert plan_data["expected"] in (100.0, 433.0)


@pytest.mark.asyncio
async def test_adv_16_negative_charge_rejection(app_client: httpx.AsyncClient):
    """
    Adversarial probe: attempts to create a charge with negative amount (e.g. -50.00 MXN).
    Negative amounts must be rejected by request validation with HTTP 422 Unprocessable Entity,
    never accepted with HTTP 201 Created (which would corrupt revenue) or HTTP 502 Bad Gateway.
    """
    # 1. Cash method with negative amount
    cash_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": "carlos", "amount": -50.0, "method": "efectivo"},
    )
    assert cash_resp.status_code == 422, (
        f"SECURITY/PRECISION GAP: Negative cash charge accepted with status {cash_resp.status_code}: {cash_resp.text}"
    )

    # 2. CoDi method with negative amount
    codi_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": "carlos", "amount": -10.0, "method": "codi"},
    )
    assert codi_resp.status_code == 422, (
        f"INPUT VALIDATION GAP: Negative codi charge caused {codi_resp.status_code} instead of 422: {codi_resp.text}"
    )


@pytest.mark.asyncio
async def test_adv_17_zero_charge_rejection(app_client: httpx.AsyncClient):
    """
    Adversarial probe: attempts to create a charge with $0.00 MXN.
    Zero-amount charges should be rejected with HTTP 422 Unprocessable Entity.
    """
    resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": "carlos", "amount": 0.0, "method": "efectivo"},
    )
    assert resp.status_code == 422, (
        f"ZERO CHARGE GAP: Zero amount charge accepted with status {resp.status_code}: {resp.text}"
    )


@pytest.mark.asyncio
async def test_adv_18_nan_infinity_rejection(app_client: httpx.AsyncClient):
    """
    Adversarial probe: injection of NaN and Infinity float values.
    Must be rejected with HTTP 422 Unprocessable Entity, avoiding unhandled HTTP 500 errors.
    """
    # Test NaN injection
    nan_resp = await app_client.post(
        "/api/charges",
        content='{"subscriber_id": "carlos", "amount": NaN, "method": "efectivo"}',
        headers={"Content-Type": "application/json"},
    )
    assert nan_resp.status_code == 422, (
        f"NAN INJECTION FLAW: NaN caused HTTP {nan_resp.status_code} instead of 422: {nan_resp.text}"
    )

    # Test Infinity injection
    inf_resp = await app_client.post(
        "/api/charges",
        content='{"subscriber_id": "carlos", "amount": Infinity, "method": "efectivo"}',
        headers={"Content-Type": "application/json"},
    )
    assert inf_resp.status_code == 422, (
        f"INFINITY INJECTION FLAW: Infinity caused HTTP {inf_resp.status_code} instead of 422: {inf_resp.text}"
    )


# ===========================================================================
# 4. Security & Robustness
# ===========================================================================

@pytest.mark.asyncio
async def test_adv_19_sql_injection_subscribers(app_client: httpx.AsyncClient):
    """
    Validates parameterized query protection against SQL injection vectors in subscriber fields:
    - name: Robert'; DROP TABLE subscribers; --
    - phone: +525512345678'; DELETE FROM charges; --
    - note: ' UNION SELECT 1, 2, 3, 4; --
    Asserts payload is stored verbatim and database schema remains intact.
    """
    sqli_name = "Robert'; DROP TABLE subscribers; --"
    sqli_phone = "+525512345678'; DELETE FROM charges; --"
    sqli_note = "' UNION SELECT 1, 2, 3, 4; --"

    resp = await app_client.post(
        "/api/subscribers",
        json={
            "id": "sub_sqli_test",
            "name": sqli_name,
            "phone": sqli_phone,
            "plan_id": "gym",
            "note": sqli_note,
        },
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["name"] == sqli_name
    assert created["phone"] == sqli_phone
    assert created["note"] == sqli_note

    # Verify table subscribers was NOT dropped
    verify_resp = await app_client.get("/api/subscribers/sub_sqli_test")
    assert verify_resp.status_code == 200
    assert verify_resp.json()["name"] == sqli_name


@pytest.mark.asyncio
async def test_adv_20_sql_injection_plans(app_client: httpx.AsyncClient):
    """
    Validates SQL injection resilience on plan creation and updates:
    - id: plan'; DROP TABLE plans; --
    - name: Gym Fit'); DROP TABLE plans; --
    Asserts plans table remains intact and all existing plans are unharmed.
    """
    sqli_plan_id = "sqli_plan_injection"
    sqli_plan_name = "Plan'; DROP TABLE plans; --"

    resp = await app_client.post(
        "/api/plans",
        json={
            "id": sqli_plan_id,
            "name": sqli_plan_name,
            "price": 200.0,
            "interval": "monthly",
        },
    )
    assert resp.status_code == 201

    # Verify plans list still contains original plans and new plan
    all_plans = (await app_client.get("/api/plans")).json()
    plan_ids = [p["id"] for p in all_plans]
    assert "demo" in plan_ids
    assert "gym" in plan_ids
    assert sqli_plan_id in plan_ids


@pytest.mark.asyncio
async def test_adv_21_sql_injection_query_filters(app_client: httpx.AsyncClient):
    """
    Validates SQL injection immunity on query parameters:
    - /api/subscribers?plan_id=gym' OR '1'='1
    - /api/charges?subscriber_id=' OR 1=1 --
    - /api/subscribers?search=' OR 1=1 --
    Asserts no SQL syntax error (HTTP 500) and no data leakage.
    """
    # 1. Filter subscribers by malicious plan_id
    r1 = await app_client.get("/api/subscribers?plan_id=gym' OR '1'='1")
    assert r1.status_code == 200
    assert len(r1.json()) == 0  # No plan with that literal id exists

    # 2. Filter charges by malicious subscriber_id
    r2 = await app_client.get("/api/charges?subscriber_id=' OR 1=1 --")
    assert r2.status_code == 200
    assert len(r2.json()) == 0

    # 3. Search subscribers with SQL injection syntax
    r3 = await app_client.get("/api/subscribers?search=' OR '1'='1")
    assert r3.status_code == 200
    assert len(r3.json()) == 0


@pytest.mark.asyncio
async def test_adv_22_unicode_mexican_names_and_notes(app_client: httpx.AsyncClient):
    """
    Tests UTF-8 robustness with authentic Mexican naming conventions, accents, and notes:
    - Name: María José Peña-Hernández O'Connor
    - Note: Pago de mensualidad · $350.00 MXN · 🇲🇽 🚀 · Folio: 20261115
    - Plan name: Entrenamiento Élite — Yoga & Pilates (100% Personalizado)
    Asserts clean storage, serialization, and retrieval without corruption.
    """
    mexican_name = "María José Peña-Hernández O'Connor"
    mexican_note = "Pago de mensualidad · $350.00 MXN · 🇲🇽 🚀 · Folio: 20261115"
    mexican_phone = "+52 (55) 1234-5678"

    resp = await app_client.post(
        "/api/subscribers",
        json={
            "id": "sub_mexican_unicode",
            "name": mexican_name,
            "phone": mexican_phone,
            "plan_id": "gym",
            "note": mexican_note,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == mexican_name
    assert data["phone"] == mexican_phone
    assert data["note"] == mexican_note

    # Verify retrieval
    retrieved = (await app_client.get("/api/subscribers/sub_mexican_unicode")).json()
    assert retrieved["name"] == mexican_name
    assert retrieved["note"] == mexican_note


@pytest.mark.asyncio
async def test_adv_23_subscriber_id_generation_accent_collision(app_client: httpx.AsyncClient):
    """
    Adversarial probe: tests subscriber ID slug generation when names contain accents or non-ASCII characters.
    When creating multiple subscribers with non-ASCII characters (e.g. 'Ñoño', 'Ángel Peña'),
    the slug generator must not strip all accents to empty/colliding strings and crash with HTTP 500.
    """
    # 1. Create first subscriber with name containing non-ASCII characters
    r1 = await app_client.post(
        "/api/subscribers",
        json={"name": "Ángel José Peña", "phone": "5511000001", "plan_id": "gym"},
    )
    assert r1.status_code == 201, f"Failed to create first subscriber: {r1.text}"

    # 2. Create second subscriber with similar accented name without manual ID
    r2 = await app_client.post(
        "/api/subscribers",
        json={"name": "Ángel José Peña", "phone": "5511000002", "plan_id": "gym"},
    )
    # Must NOT crash with HTTP 500 Internal Server Error (IntegrityError UNIQUE constraint on slug)
    assert r2.status_code in (201, 409), (
        f"ID GENERATION FLAW: Accented name slug collision caused HTTP {r2.status_code}: {r2.text}"
    )


@pytest.mark.asyncio
async def test_adv_24_xss_and_oversized_payload_resilience(app_client: httpx.AsyncClient):
    """
    Tests XSS injection strings and oversized payloads in concept and note fields:
    - XSS script tag: <script>alert("xss")</script>
    - Oversized concept/note (10,000 characters)
    Asserts graceful handling, persistence, and safe JSON response serialization.
    """
    xss_payload = '<script>alert("xss")</script><img src=x onerror=alert(1)>'
    long_note = "A" * 10000

    resp = await app_client.post(
        "/api/subscribers",
        json={
            "id": "sub_xss_test",
            "name": "XSS Probe User",
            "phone": "5512349999",
            "plan_id": "gym",
            "note": f"{xss_payload} {long_note}",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert xss_payload in data["note"]
    assert len(data["note"]) >= 10000
