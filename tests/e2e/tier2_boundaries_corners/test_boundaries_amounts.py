"""
Tier 2 Boundary: Amount Boundaries & Numeric Precision
Tests $0.01 min, $0.05 demo, $0.10 max demo, non-positive rejections, and floating point fidelity.
"""

import httpx
import pytest


@pytest.mark.asyncio
async def test_bva_01_minimum_allowed_amount_one_cent(app_client: httpx.AsyncClient):
    """Verifies that the minimum allowed charge amount $0.01 is accepted without truncation."""
    subs = (await app_client.get("/api/subscribers")).json()
    sub_id = subs[0]["id"]

    resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub_id, "amount": 0.01},
    )
    assert resp.status_code in [200, 201]
    charge = resp.json()
    assert abs(float(charge["amount"]) - 0.01) < 1e-6


@pytest.mark.asyncio
async def test_bva_02_demo_plan_amount_five_cents(app_client: httpx.AsyncClient):
    """Verifies that the demo microcharge of $0.05 MXN is supported."""
    plans = (await app_client.get("/api/plans")).json()
    demo_plan = next((p for p in plans if abs(float(p["price"]) - 0.05) < 1e-4), None)
    assert demo_plan is not None

    subs = (await app_client.get("/api/subscribers")).json()
    sub_id = subs[0]["id"]

    resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub_id, "amount": 0.05},
    )
    assert resp.status_code in [200, 201]
    charge = resp.json()
    assert abs(float(charge["amount"]) - 0.05) < 1e-6


@pytest.mark.asyncio
async def test_bva_03_demo_upper_bound_ten_cents(app_client: httpx.AsyncClient):
    """Verifies that $0.10 MXN microcharge is processed cleanly within centavo range."""
    subs = (await app_client.get("/api/subscribers")).json()
    sub_id = subs[0]["id"]

    resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub_id, "amount": 0.10},
    )
    assert resp.status_code in [200, 201]
    charge = resp.json()
    assert abs(float(charge["amount"]) - 0.10) < 1e-6


@pytest.mark.asyncio
async def test_bva_04_zero_and_negative_amounts_rejected(app_client: httpx.AsyncClient):
    """Verifies creating plans with amount <= 0 is rejected by validation."""
    invalid_plan_zero = {
        "name": "Zero Plan",
        "price": 0.0,
        "interval": "monthly",
    }
    resp_zero = await app_client.post("/api/plans", json=invalid_plan_zero)
    assert resp_zero.status_code in [400, 422]

    invalid_plan_neg = {
        "name": "Negative Plan",
        "price": -15.0,
        "interval": "monthly",
    }
    resp_neg = await app_client.post("/api/plans", json=invalid_plan_neg)
    assert resp_neg.status_code in [400, 422]


@pytest.mark.asyncio
async def test_bva_05_floating_point_rounding_safety(app_client: httpx.AsyncClient):
    """Verifies amounts like 199.99 preserve 2-decimal precision without IEEE 754 precision drift."""
    subs = (await app_client.get("/api/subscribers")).json()
    sub_id = subs[0]["id"]

    resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub_id, "amount": 199.99},
    )
    assert resp.status_code in [200, 201]
    charge = resp.json()
    # Stored amount should equal 199.99
    assert round(float(charge["amount"]), 2) == 199.99
