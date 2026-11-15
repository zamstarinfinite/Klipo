"""
Tier 4: Scenario 5 — Field Cash Collection & Instant Dashboard Reconciliation
Multi-step workflow:
1. Snapshot initial dashboard metrics
2. Batch cash payment for subscriber 1 (Luis Morales - overdue)
3. Batch cash payment for subscriber 2 (Mariana Ortiz - due soon)
4. Verify subscribers advance out of overdue/due-soon states
5. Reconcile dashboard ledger and recent movements list
"""

import httpx
import pytest
from tests.e2e.conftest import require_route


@pytest.mark.asyncio
async def test_scenario_5_field_cash(app_client: httpx.AsyncClient):
    # Step 1: Snapshot Initial Dashboard
    dash_init = (await app_client.get("/api/dashboard")).json()
    init_collected = float(dash_init["collected_month"])

    # Step 2: In-Person Collection Subscriber 1 (Luis Morales - Overdue)
    sub1_resp = await app_client.get("/api/subscribers/luis")
    assert sub1_resp.status_code == 200
    luis = sub1_resp.json()
    assert luis["status"] == "atrasado"

    charge1_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": "luis", "amount": 350.0, "method": "efectivo"},
    )
    assert charge1_resp.status_code in [200, 201]
    charge1_id = charge1_resp.json()["id"]

    require_route("/api/charges/{id}/mark-cash", "POST")
    mark1_resp = await app_client.post(f"/api/charges/{charge1_id}/mark-cash")
    assert mark1_resp.status_code in [200, 204]

    # Step 3: In-Person Collection Subscriber 2 (Mariana Ortiz - Due Soon)
    charge2_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": "mariana", "amount": 350.0, "method": "efectivo"},
    )
    assert charge2_resp.status_code in [200, 201]
    charge2_id = charge2_resp.json()["id"]

    mark2_resp = await app_client.post(f"/api/charges/{charge2_id}/mark-cash")
    assert mark2_resp.status_code in [200, 204]

    # Step 4: Verify Subscribers Advanced
    luis_after = (await app_client.get("/api/subscribers/luis")).json()
    mariana_after = (await app_client.get("/api/subscribers/mariana")).json()
    assert luis_after["status"] == "al_corriente"
    assert mariana_after["status"] == "al_corriente"

    # Step 5: Reconcile Dashboard
    dash_final = (await app_client.get("/api/dashboard")).json()
    assert float(dash_final["collected_month"]) >= init_collected + 700.0
    recent = dash_final["recent_movements"]
    assert len(recent) >= 2
