import os
import unittest.mock as mock
from datetime import date, datetime, timedelta
import pytest
import httpx

from backend.db import (
    advance_subscriber_recurrence,
    calculate_subscriber_status,
    get_connection,
)
from backend.main import app
from backend.pey_client import PeyAuthError, PeyConnectionError


@pytest.mark.asyncio
async def test_health_check_endpoint_healthy(async_client):
    """GET /api/health returns 200 and healthy status when DB and Pey credentials are ok."""
    with mock.patch("backend.main.check_credentials", return_value={"authenticated": True, "status": "ok"}):
        res = await async_client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"
        assert data["pey_api"] == "authenticated"


@pytest.mark.asyncio
async def test_health_check_endpoint_unauthenticated(async_client):
    """GET /api/health returns 503 when Pey credentials fail authentication."""
    with mock.patch("backend.main.check_credentials", side_effect=PeyAuthError("401 Unauthorized")):
        res = await async_client.get("/api/health")
        assert res.status_code == 503
        data = res.json()
        assert "unauthenticated" in str(data.get("detail", ""))


@pytest.mark.asyncio
async def test_health_check_endpoint_pey_connection_error(async_client):
    """GET /api/health returns 503 when Pey API is unreachable."""
    with mock.patch("backend.main.check_credentials", side_effect=PeyConnectionError("Connection timeout")):
        res = await async_client.get("/api/health")
        assert res.status_code == 503


def test_advance_subscriber_recurrence_weekly(test_db):
    """Verifies weekly plan advances next_due_date by +7 days and sets status to al_corriente."""
    conn = get_connection(test_db)
    # Create weekly plan & subscriber
    with conn:
        conn.execute("INSERT OR REPLACE INTO plans (id, name, price, interval) VALUES ('plan_weekly', 'Weekly Fit', 100.0, 'weekly');")
        conn.execute("INSERT OR REPLACE INTO subscribers (id, plan_id, name, phone, next_due_date) VALUES ('sub_w1', 'plan_weekly', 'Sub Weekly', '5511223344', ?);", (date.today().isoformat(),))

    new_due = advance_subscriber_recurrence("sub_w1", conn=conn)
    expected_due = (date.today() + timedelta(days=7)).isoformat()
    assert new_due == expected_due

    # Verify status is al_corriente
    assert calculate_subscriber_status(new_due) == "al_corriente"

    # Verify last_paid_at was updated
    cursor = conn.cursor()
    cursor.execute("SELECT next_due_date, last_paid_at FROM subscribers WHERE id = 'sub_w1';")
    row = cursor.fetchone()
    assert row["next_due_date"] == expected_due
    assert row["last_paid_at"] is not None
    conn.close()


def test_advance_subscriber_recurrence_biweekly(test_db):
    """Verifies biweekly plan advances next_due_date by +15 days and sets status to al_corriente."""
    conn = get_connection(test_db)
    with conn:
        conn.execute("INSERT OR REPLACE INTO plans (id, name, price, interval) VALUES ('plan_biweekly', 'Biweekly Fit', 200.0, 'biweekly');")
        conn.execute("INSERT OR REPLACE INTO subscribers (id, plan_id, name, phone, next_due_date) VALUES ('sub_bw1', 'plan_biweekly', 'Sub Biweekly', '5511223344', ?);", (date.today().isoformat(),))

    new_due = advance_subscriber_recurrence("sub_bw1", conn=conn)
    expected_due = (date.today() + timedelta(days=15)).isoformat()
    assert new_due == expected_due
    assert calculate_subscriber_status(new_due) == "al_corriente"
    conn.close()


def test_advance_subscriber_recurrence_monthly_month_end_clamping(test_db):
    """Verifies monthly plan advances with month-end clamping (Jan 31 -> Feb 28)."""
    conn = get_connection(test_db)
    with conn:
        conn.execute("INSERT OR REPLACE INTO plans (id, name, price, interval) VALUES ('plan_monthly', 'Monthly Fit', 350.0, 'monthly');")
        # Set due date to Jan 31 in a future year to test forward advance
        conn.execute("INSERT OR REPLACE INTO subscribers (id, plan_id, name, phone, next_due_date) VALUES ('sub_m1', 'plan_monthly', 'Sub Monthly', '5511223344', '2027-01-31');")

    new_due = advance_subscriber_recurrence("sub_m1", conn=conn)
    assert new_due == "2027-02-28"
    assert calculate_subscriber_status(new_due) == "al_corriente"
    conn.close()


def test_advance_subscriber_recurrence_overdue_subscriber(test_db):
    """Verifies an overdue subscriber is advanced relative to today and transitions to al_corriente."""
    conn = get_connection(test_db)
    past_date = (date.today() - timedelta(days=20)).isoformat()
    with conn:
        conn.execute("INSERT OR REPLACE INTO plans (id, name, price, interval) VALUES ('plan_monthly', 'Monthly Fit', 350.0, 'monthly');")
        conn.execute("INSERT OR REPLACE INTO subscribers (id, plan_id, name, phone, next_due_date) VALUES ('sub_overdue', 'plan_monthly', 'Sub Overdue', '5511223344', ?);", (past_date,))

    # Prior status was atrasado
    assert calculate_subscriber_status(past_date) == "atrasado"

    new_due = advance_subscriber_recurrence("sub_overdue", conn=conn)
    # New due date must be in future and status must be al_corriente
    assert calculate_subscriber_status(new_due) == "al_corriente"
    conn.close()


@pytest.mark.asyncio
async def test_create_charge_live_pey_generation(async_client, test_db):
    """POST /api/charges invokes Pey CoDi QR and Payment Link generation and saves records."""
    mock_qr_resp = {
        "id": "35codiqr123",
        "qrString": '{"TYP":20,"v":{"DEV":"123"},"ic":{"IDC":"35codiqr123"}}',
        "qrImage": "iVBORw0KGgoAAAANSUhEUgAA...",
    }
    mock_link_resp = {
        "id": "01M7LINK456",
        "url": "https://app.mipey.mx/checkout/payment-link/01M7LINK456",
    }

    with mock.patch("backend.main.create_codi_qr", return_value=mock_qr_resp) as mock_qr, \
         mock.patch("backend.main.create_payment_link", return_value=mock_link_resp) as mock_link:

        res = await async_client.post("/api/charges", json={
            "subscriber_id": "carlos",
            "amount": 0.05,
        })
        assert res.status_code == 201
        data = res.json()
        assert data["codi_qr_id"] == "35codiqr123"
        assert data["qr_payload"] == mock_qr_resp["qrString"]
        assert data["qr_image"] == mock_qr_resp["qrImage"]
        assert data["payment_link_id"] == "01M7LINK456"
        assert data["payment_link_url"] == mock_link_resp["url"]
        assert data["status"] == "pending"
        assert len(data["num_ref"]) <= 7
        assert data["num_ref"].isdigit()

        # Check in DB
        conn = get_connection(test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM charges WHERE id = ?;", (data["id"],))
        db_charge = cursor.fetchone()
        assert db_charge is not None
        assert db_charge["codi_qr_id"] == "35codiqr123"
        assert db_charge["payment_link_id"] == "01M7LINK456"
        conn.close()


@pytest.mark.asyncio
async def test_charge_status_polling_pending_to_paid(async_client, test_db):
    """GET /api/charges/{id}/status transitions pending charge to paid when Pey reports payment."""
    # Insert pending charge
    conn = get_connection(test_db)
    with conn:
        conn.execute("""
            INSERT INTO charges (id, subscriber_id, plan_id, amount, status, codi_qr_id, payment_link_id)
            VALUES ('charge_poll_test', 'carlos', 'gym', 350.0, 'pending', 'qr_poll_123', 'link_poll_123');
        """)
        cursor = conn.cursor()
        cursor.execute("SELECT next_due_date FROM subscribers WHERE id = 'carlos';")
        initial_due = cursor.fetchone()["next_due_date"]
    conn.close()

    # Case 1: Pey reports unpaid
    with mock.patch("backend.main.get_codi_qr_transactions", return_value={"items": []}), \
         mock.patch("backend.main.get_payment_link_status", return_value={"status": "pending"}):
        res = await async_client.get("/api/charges/charge_poll_test/status")
        assert res.status_code == 200
        assert res.json()["status"] == "pending"
        assert res.json()["pagado"] is False

    # Case 2: Pey reports PAID via CoDi QR
    with mock.patch("backend.main.get_codi_qr_transactions", return_value={"items": [{"status": "PAID", "transactionId": "tx_pey_999"}]}):
        res = await async_client.get("/api/charges/charge_poll_test/status")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "paid"
        assert data["pagado"] is True
        assert data["paid_at"] is not None
        assert data["subscriber_status"] == "al_corriente"
        assert data["subscriber_next_due_date"] != initial_due

    # Case 3: Idempotency - repeated poll does not advance recurrence again
    conn = get_connection(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT next_due_date FROM subscribers WHERE id = 'carlos';")
    advanced_due = cursor.fetchone()["next_due_date"]
    conn.close()

    with mock.patch("backend.main.get_codi_qr_transactions", return_value={"items": [{"status": "PAID"}]}):
        res2 = await async_client.get("/api/charges/charge_poll_test/status")
        assert res2.status_code == 200
        assert res2.json()["subscriber_next_due_date"] == advanced_due


@pytest.mark.asyncio
async def test_charge_status_polling_paid_via_payment_link(async_client, test_db):
    """GET /api/charges/{id}/status transitions to paid when Payment Link is paid."""
    conn = get_connection(test_db)
    with conn:
        conn.execute("""
            INSERT INTO charges (id, subscriber_id, plan_id, amount, status, codi_qr_id, payment_link_id)
            VALUES ('charge_link_poll', 'mariana', 'gym', 350.0, 'pending', 'qr_link_123', 'link_paid_123');
        """)
    conn.close()

    with mock.patch("backend.main.get_codi_qr_transactions", return_value={"items": []}), \
         mock.patch("backend.main.get_payment_link_status", return_value={"status": "paid"}):
        res = await async_client.get("/api/charges/charge_link_poll/status")
        assert res.status_code == 200
        assert res.json()["status"] == "paid"
        assert res.json()["pagado"] is True


@pytest.mark.asyncio
async def test_webhook_codi_payment_received(async_client, test_db):
    """POST /api/webhooks/pey processes 'codi.qr.payment_received' event."""
    conn = get_connection(test_db)
    with conn:
        conn.execute("""
            INSERT INTO charges (id, subscriber_id, plan_id, amount, status, codi_qr_id)
            VALUES ('charge_wh_codi', 'valeria', 'pilates', 400.0, 'pending', 'qr_wh_555');
        """)
    conn.close()

    payload = {
        "type": "codi.qr.payment_received",
        "codiQrId": "qr_wh_555",
        "amount": 400.0,
        "transactionId": "tx_wh_111",
    }
    res = await async_client.post("/api/webhooks/pey", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "processed"

    # Verify charge is now paid in DB
    conn = get_connection(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM charges WHERE id = 'charge_wh_codi';")
    c = cursor.fetchone()
    assert c["status"] == "paid"
    assert c["paid_at"] is not None
    assert c["pey_transaction_id"] == "tx_wh_111"
    conn.close()


@pytest.mark.asyncio
async def test_webhook_payment_link_status_updated(async_client, test_db):
    """POST /api/webhooks/pey processes 'payment_link.status_updated' event."""
    conn = get_connection(test_db)
    with conn:
        conn.execute("""
            INSERT INTO charges (id, subscriber_id, plan_id, amount, status, payment_link_id)
            VALUES ('charge_wh_link', 'roberto', 'gym', 350.0, 'pending', 'link_wh_777');
        """)
    conn.close()

    payload = {
        "type": "payment_link.status_updated",
        "paymentLinkId": "link_wh_777",
        "status": "paid",
        "clientReferenceId": "charge_wh_link",
        "transactionId": "tx_wh_222",
    }
    res = await async_client.post("/api/webhooks/pey", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "processed"

    # Verify charge is now paid in DB
    conn = get_connection(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM charges WHERE id = 'charge_wh_link';")
    c = cursor.fetchone()
    assert c["status"] == "paid"
    conn.close()


@pytest.mark.asyncio
async def test_webhook_unknown_charge_returns_gracefully(async_client):
    """POST /api/webhooks/pey gracefully handles unmatched charge without 500 error."""
    payload = {
        "type": "codi.qr.payment_received",
        "codiQrId": "non_existent_qr_id",
        "amount": 100.0,
    }
    res = await async_client.post("/api/webhooks/pey", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "processed"


@pytest.mark.asyncio
async def test_mark_cash_endpoint(async_client, test_db):
    """POST /api/charges/{id}/mark-cash marks charge paid with method 'efectivo' and advances recurrence."""
    conn = get_connection(test_db)
    with conn:
        conn.execute("""
            INSERT INTO charges (id, subscriber_id, plan_id, amount, status, method)
            VALUES ('charge_cash_1', 'ana', 'yoga', 300.0, 'pending', 'codi');
        """)
        cursor = conn.cursor()
        cursor.execute("SELECT next_due_date FROM subscribers WHERE id = 'ana';")
        orig_due = cursor.fetchone()["next_due_date"]
    conn.close()

    res = await async_client.post("/api/charges/charge_cash_1/mark-cash")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "paid"
    assert data["method"] == "efectivo"
    assert data["paid_at"] is not None
    assert data["subscriber_status"] == "al_corriente"
    assert data["subscriber_next_due_date"] != orig_due

    # Idempotent second call
    res2 = await async_client.post("/api/charges/charge_cash_1/mark-cash")
    assert res2.status_code == 200
    assert res2.json()["subscriber_next_due_date"] == data["subscriber_next_due_date"]


@pytest.mark.asyncio
async def test_mark_cash_nonexistent_charge_returns_404(async_client):
    """POST /api/charges/nonexistent/mark-cash returns 404."""
    res = await async_client.post("/api/charges/charge_does_not_exist/mark-cash")
    assert res.status_code == 404
