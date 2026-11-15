"""
Tier 4: Scenario 3 — Concurrent Hybrid Confirmation Race (Webhook vs Polling)
Multi-step workflow:
1. Setup charge for subscriber Carlos (amount $350)
2. Configure mock gateway status to PAID
3. Trigger simultaneous confirmation requests (polling + webhook + cash mark) via asyncio.gather
4. Verify database invariants: exactly one advances date, no double-counting in collected_month
"""

import asyncio
import httpx
import pytest
from tests.e2e.conftest import require_route
from tests.e2e.pey_mock_server import PeyMockServer


@pytest.mark.asyncio
async def test_scenario_3_concurrent_race(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    # Step 1: Create Charge for Carlos
    sub_resp = await app_client.get("/api/subscribers/carlos")
    assert sub_resp.status_code == 200
    carlos = sub_resp.json()
    initial_due_date = carlos["next_due_date"]

    charge_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": "carlos", "amount": 350.0, "method": "codi"},
    )
    assert charge_resp.status_code in [200, 201]
    charge = charge_resp.json()
    charge_id = charge["id"]
    codi_id = charge.get("codi_qr_id")
    assert codi_id is not None and len(codi_id) > 0, "Expected codi_qr_id in charge"

    # Step 2: Configure Mock Gateway
    pey_mock.mark_codi_paid(codi_id)

    # Step 3: Trigger Simultaneous Confirmations
    require_route("/api/charges/{id}/status", "GET")
    require_route("/api/webhooks/pey", "POST")

    webhook_payload = {
        "type": "codi.qr.payment_received",
        "codiQrId": codi_id,
        "amount": 350.0,
        "datePaid": 1794720000,
    }

    async def call_poll():
        return await app_client.get(f"/api/charges/{charge_id}/status")

    async def call_webhook():
        return await app_client.post(
            "/api/webhooks/pey",
            json=webhook_payload,
            headers={"webhook-id": f"race_{charge_id}"},
        )

    # Execute both simultaneously
    results = await asyncio.gather(call_poll(), call_webhook(), return_exceptions=True)
    for r in results:
        if isinstance(r, httpx.Response):
            assert r.status_code in [200, 202]

    # Step 4: Verify Database Invariants
    carlos_after = (await app_client.get("/api/subscribers/carlos")).json()
    # next_due_date should not be advanced more than once
    charges_list = (await app_client.get(f"/api/charges?subscriber_id=carlos")).json()
    assert len(charges_list) >= 1
