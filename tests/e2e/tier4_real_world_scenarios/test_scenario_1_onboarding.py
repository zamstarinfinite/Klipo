"""
Tier 4: Scenario 1 — New Plan & Subscriber Onboarding Flow
Multi-step workflow:
1. Create new plan (e.g. CrossFit Pro $450)
2. Verify plan appears in list
3. Register new subscriber (Mateo Silva)
4. Initiate first charge
5. Poll charge status (pending)
6. Simulate gateway approval
7. Poll charge status (paid)
8. Verify subscriber status transitioned to 'al_corriente'
9. Reconcile dashboard metrics
"""

from datetime import date
import httpx
import pytest
from tests.e2e.conftest import require_route
from tests.e2e.pey_mock_server import PeyMockServer


@pytest.mark.asyncio
async def test_scenario_1_onboarding(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    # Step 1: Create Plan
    plan_payload = {
        "name": "CrossFit Pro Scenario 1",
        "price": 450.00,
        "interval": "monthly",
        "charge_day": 15,
        "icon": "gym",
    }
    plan_resp = await app_client.post("/api/plans", json=plan_payload)
    assert plan_resp.status_code in [200, 201]
    plan = plan_resp.json()
    plan_id = plan["id"]
    assert plan["name"] == "CrossFit Pro Scenario 1"
    assert float(plan["price"]) == 450.0

    # Step 2: Verify Plan in List
    plans_list = (await app_client.get("/api/plans")).json()
    assert any(p["id"] == plan_id for p in plans_list)

    # Step 3: Register Subscriber
    today_str = date.today().isoformat()
    sub_payload = {
        "name": "Mateo Silva",
        "phone": "5511223344",
        "plan_id": plan_id,
        "start_date": today_str,
        "next_due_date": today_str,
    }
    sub_resp = await app_client.post("/api/subscribers", json=sub_payload)
    assert sub_resp.status_code in [200, 201]
    sub = sub_resp.json()
    sub_id = sub["id"]
    assert sub["status"] == "por_vencer"  # Due today

    # Step 4: Initiate First Charge
    charge_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub_id, "amount": 450.00, "method": "codi"},
    )
    assert charge_resp.status_code in [200, 201]
    charge = charge_resp.json()
    charge_id = charge["id"]
    assert charge["status"] in ["pending", "pendiente"]

    # Step 5: Poll Status
    require_route("/api/charges/{id}/status", "GET")
    poll_1 = await app_client.get(f"/api/charges/{charge_id}/status")
    assert poll_1.status_code == 200
    assert poll_1.json()["status"] in ["pending", "pendiente"]

    # Step 6: Simulate Bank Approval in Gateway
    codi_id = charge.get("codi_qr_id")
    assert codi_id is not None and len(codi_id) > 0, "Expected codi_qr_id"
    pey_mock.mark_codi_paid(codi_id)

    # Step 7: Poll Status (Paid)
    poll_2 = await app_client.get(f"/api/charges/{charge_id}/status")
    assert poll_2.status_code == 200
    assert poll_2.json()["status"] in ["paid", "pagado"]

    # Step 8: Verify Subscriber State Transition
    sub_after = (await app_client.get(f"/api/subscribers/{sub_id}")).json()
    assert sub_after["status"] == "al_corriente"

    # Step 9: Reconcile Dashboard
    dashboard = (await app_client.get("/api/dashboard")).json()
    assert dashboard["total_subscribers"] >= 4
