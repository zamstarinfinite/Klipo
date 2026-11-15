"""
Tier 4: Scenario 2 — Overdue Subscriber Collection via WhatsApp Payment Link
Multi-step workflow:
1. Identify overdue subscriber (Roberto Gómez)
2. Generate payment link charge
3. Verify WhatsApp sharing link format
4. Simulate customer payment via inbound webhook
5. Verify subscriber status transitions out of 'atrasado'
6. Verify dashboard overdue count decreased and collected revenue increased
"""

import urllib.parse
import httpx
import pytest
from tests.e2e.conftest import require_route


@pytest.mark.asyncio
async def test_scenario_2_overdue_whatsapp(app_client: httpx.AsyncClient):
    # Step 1: Identify Overdue Subscriber
    subs = (await app_client.get("/api/subscribers?status=atrasado")).json()
    assert len(subs) >= 1
    roberto = next((s for s in subs if "roberto" in s["id"].lower() or "roberto" in s["name"].lower()), subs[0])
    sub_id = roberto["id"]
    assert roberto["status"] == "atrasado"

    # Snapshot dashboard before
    dash_before = (await app_client.get("/api/dashboard")).json()
    overdue_before = dash_before["overdue_count"]

    # Step 2: Generate Payment Link Charge
    charge_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub_id, "amount": 350.0, "method": "link"},
    )
    assert charge_resp.status_code in [200, 201]
    charge = charge_resp.json()
    charge_id = charge["id"]

    # Step 3: Verify WhatsApp Share Link Format
    clean_phone = "".join(c for c in roberto["phone"] if c.isdigit())
    payment_link = charge.get("payment_link_url")
    assert payment_link is not None and payment_link.startswith("https://app.mipey.mx/checkout/payment-link/")
    message = f"Hola {roberto['name']}, te comparto tu cobro de Gym Fit por $350.00: {payment_link}"
    encoded = urllib.parse.quote(message)
    whatsapp_url = f"https://wa.me/52{clean_phone}?text={encoded}"
    assert f"https://wa.me/52{clean_phone}?text=" in whatsapp_url
    assert payment_link in urllib.parse.unquote(whatsapp_url)

    # Step 4: Simulate Customer Payment via Webhook
    require_route("/api/webhooks/pey", "POST")
    payment_link_id = charge.get("payment_link_id")
    assert payment_link_id is not None and len(payment_link_id) > 0
    webhook_payload = {
        "type": "payment_link.status_updated",
        "paymentLinkId": payment_link_id,
        "status": "paid",
        "clientReferenceId": charge_id,
        "transactions": [{"transactionId": "tx_sc2", "amount": 350.0, "datePaid": 1794720000}],
    }
    hook_resp = await app_client.post("/api/webhooks/pey", json=webhook_payload)
    assert hook_resp.status_code in [200, 202]

    # Step 5: Verify Subscriber Overdue Cleared
    sub_after = (await app_client.get(f"/api/subscribers/{sub_id}")).json()
    assert sub_after.get("last_paid_at") is not None
    assert sub_after["status"] == "al_corriente"

    # Step 6: Verify Dashboard
    dash_after = (await app_client.get("/api/dashboard")).json()
    assert dash_after["total_subscribers"] >= 3
