"""
Feature 11: Automatic Recurrence Advancement
Validates weekly (+7d), biweekly (+15d), and monthly (+1mo) recurrence advancement and overdue clearing.
"""

from datetime import date, timedelta
import httpx
import pytest
from backend.db import advance_due_date, calculate_subscriber_status


def test_f11_01_weekly_plan_advance_seven_days():
    """Verifies weekly interval advances next_due_date by exactly 7 calendar days."""
    start = "2026-11-15"
    advanced = advance_due_date(start, "weekly")
    assert advanced == "2026-11-22"


def test_f11_02_biweekly_plan_advance_fifteen_days():
    """Verifies biweekly interval advances next_due_date by exactly 15 calendar days."""
    start = "2026-11-15"
    advanced = advance_due_date(start, "biweekly")
    assert advanced == "2026-11-30"


def test_f11_03_monthly_plan_advance_one_month():
    """Verifies monthly interval advances next_due_date by 1 calendar month."""
    start = "2026-11-15"
    advanced = advance_due_date(start, "monthly")
    assert advanced == "2026-12-15"


@pytest.mark.asyncio
async def test_f11_04_overdue_subscriber_status_cleared_on_advance(app_client: httpx.AsyncClient):
    """Verifies an overdue subscriber status transitions to 'al_corriente' when advanced into future."""
    # Roberto is overdue by 14 days
    sub_resp = await app_client.get("/api/subscribers/roberto")
    assert sub_resp.status_code == 200
    sub = sub_resp.json()
    assert sub["status"] == "atrasado"

    # Advance next_due_date by updating subscriber
    future_date = (date.today() + timedelta(days=25)).isoformat()
    patch_resp = await app_client.patch(
        "/api/subscribers/roberto",
        json={"next_due_date": future_date},
    )
    assert patch_resp.status_code == 200
    updated_sub = patch_resp.json()
    assert updated_sub["status"] == "al_corriente"


def test_f11_05_event_driven_recurrence_without_cron():
    """Verifies calculation of subscriber status is dynamic and pure, requiring zero background cron."""
    today = date.today()
    assert calculate_subscriber_status(today - timedelta(days=1), reference_date=today) == "atrasado"
    assert calculate_subscriber_status(today, reference_date=today) == "por_vencer"
    assert calculate_subscriber_status(today + timedelta(days=3), reference_date=today) == "por_vencer"
    assert calculate_subscriber_status(today + timedelta(days=4), reference_date=today) == "al_corriente"
