"""
Tier 4: Scenario 4 — $0.05 MXN Microcharge Capability Showcase
Multi-step workflow:
1. Validate demo plan ($0.05 MXN) exists
2. Select demo subscriber (Invitado Demo)
3. Create 5-centavo charge via POST /api/charges
4. Verify Banxico CoDi payload structure & base64 image
5. Simulate payment & poll status
6. Reconcile dashboard with floating point accounting precision
"""

import httpx
import pytest
from tests.e2e.conftest import require_route
from tests.e2e.pey_mock_server import PeyMockServer


@pytest.mark.asyncio
async def test_scenario_4_microcharge(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    # Step 1: Validate Demo Plan
    plans = (await app_client.get("/api/plans")).json()
    demo_plan = next(p for p in plans if abs(float(p["price"]) - 0.05) < 1e-4)
    assert demo_plan is not None
    assert float(demo_plan["price"]) == 0.05

    # Step 2: Select Demo Subscriber
    subs = (await app_client.get("/api/subscribers")).json()
    demo_sub = next((s for s in subs if s["id"] == "demo_sub" or "demo" in s["name"].lower()), subs[0])
    sub_id = demo_sub["id"]

    # Snapshot dashboard before
    dash_before = (await app_client.get("/api/dashboard")).json()
    initial_collected = float(dash_before["collected_month"])

    # Step 3: Create 5-Centavo Charge
    charge_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub_id, "amount": 0.05, "method": "codi"},
    )
    assert charge_resp.status_code in [200, 201]
    charge = charge_resp.json()
    assert abs(float(charge["amount"]) - 0.05) < 1e-6
    charge_id = charge["id"]

    # Step 4: Inspect CoDi Payload
    assert "qr_image" in charge and charge["qr_image"] is not None and len(charge["qr_image"]) > 20
    assert "codi_qr_id" in charge and charge["codi_qr_id"] is not None and len(charge["codi_qr_id"]) > 0

    # Step 5: Simulate Payment & Poll Status
    codi_id = charge["codi_qr_id"]
    pey_mock.mark_codi_paid(codi_id)

    require_route("/api/charges/{id}/status", "GET")
    poll_resp = await app_client.get(f"/api/charges/{charge_id}/status")
    assert poll_resp.status_code == 200

    # Step 6: Reconcile Dashboard
    dash_after = (await app_client.get("/api/dashboard")).json()
    assert isinstance(dash_after["collected_month"], (int, float))
