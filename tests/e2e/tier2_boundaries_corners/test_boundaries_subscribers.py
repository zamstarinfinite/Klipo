"""
Tier 2 Boundary: Due Date & Status Threshold Boundaries
Tests -1 day (atrasado), 0 days (por_vencer), +3 days (por_vencer), +4 days (al_corriente), and leap day.
"""

from datetime import date, timedelta
import httpx
import pytest
from backend.db import calculate_subscriber_status


def test_bva_06_due_date_yesterday_is_atrasado():
    """Verifies that next_due_date set to yesterday evaluates dynamically to 'atrasado'."""
    today = date.today()
    status = calculate_subscriber_status(today - timedelta(days=1), reference_date=today)
    assert status == "atrasado"


def test_bva_07_due_date_today_is_por_vencer():
    """Verifies that next_due_date set to today evaluates dynamically to 'por_vencer'."""
    today = date.today()
    status = calculate_subscriber_status(today, reference_date=today)
    assert status == "por_vencer"


def test_bva_08_due_date_exactly_three_days_is_por_vencer():
    """Verifies that next_due_date set to exactly today + 3 days evaluates to 'por_vencer'."""
    today = date.today()
    status = calculate_subscriber_status(today + timedelta(days=3), reference_date=today)
    assert status == "por_vencer"


def test_bva_09_due_date_four_days_is_al_corriente():
    """Verifies that next_due_date set to today + 4 days transitions to 'al_corriente'."""
    today = date.today()
    status = calculate_subscriber_status(today + timedelta(days=4), reference_date=today)
    assert status == "al_corriente"


@pytest.mark.asyncio
async def test_bva_10_due_date_leap_year_february_29(app_client: httpx.AsyncClient):
    """Verifies that a leap year date (e.g. 2028-02-29) is accepted and parsed without ValueError."""
    plans = (await app_client.get("/api/plans")).json()
    plan_id = plans[0]["id"]

    leap_sub = {
        "name": "Leap Year Subscriber",
        "phone": "5500002928",
        "plan_id": plan_id,
        "next_due_date": "2028-02-29",
    }
    resp = await app_client.post("/api/subscribers", json=leap_sub)
    assert resp.status_code in [200, 201]
    data = resp.json()
    assert data["next_due_date"] == "2028-02-29"
    assert data["status"] == "al_corriente"
