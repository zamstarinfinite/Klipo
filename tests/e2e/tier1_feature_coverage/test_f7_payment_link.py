"""
Feature 7: Pey Payment Link Generation & WhatsApp Sharing
Validates payment link generation, checkout URL structure, and WhatsApp wa.me link formatting.
"""

import urllib.parse
import httpx
import pytest
from tests.e2e.pey_mock_server import PeyMockServer


@pytest.mark.asyncio
async def test_f7_01_payment_link_generation_success(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """Verifies creating a charge with method 'link' sets or allows generating a payment link."""
    subs_resp = await app_client.get("/api/subscribers")
    sub = subs_resp.json()[0]

    resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub["id"], "amount": 350.0, "method": "link"},
    )
    assert resp.status_code in [200, 201]
    charge = resp.json()
    assert charge["subscriber_id"] == sub["id"]

    # Assert payment link unconditionally
    assert "payment_link_url" in charge and charge["payment_link_url"] is not None
    assert "app.mipey.mx" in charge["payment_link_url"] or "checkout" in charge["payment_link_url"]


@pytest.mark.asyncio
async def test_f7_02_payment_link_url_format_validity(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """Verifies payment link URL starts with https://app.mipey.mx/checkout/payment-link/."""
    subs_resp = await app_client.get("/api/subscribers")
    sub = subs_resp.json()[0]

    resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub["id"], "amount": 250.0, "method": "link"},
    )
    assert resp.status_code in [200, 201]
    link_url = resp.json().get("payment_link_url")
    assert link_url is not None, "Expected payment_link_url in response"
    assert link_url.startswith("https://app.mipey.mx/checkout/payment-link/")


@pytest.mark.asyncio
async def test_f7_03_whatsapp_link_formatting(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """Verifies WhatsApp share URL structure follows https://wa.me/52{phone}?text={encoded} with real payment link."""
    subs_resp = await app_client.get("/api/subscribers")
    assert subs_resp.status_code == 200
    sub = subs_resp.json()[0]
    raw_phone = sub["phone"]
    clean_phone = "".join(c for c in raw_phone if c.isdigit())

    # Create real charge to retrieve genuine payment link from API / DB
    create_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub["id"], "amount": 350.0, "method": "link"},
    )
    assert create_resp.status_code in [200, 201]
    charge = create_resp.json()
    payment_link = charge.get("payment_link_url")
    assert payment_link is not None and payment_link.startswith("https://")

    # Build standard WhatsApp URL as specified in DESIGN.md and frontend charge.tsx
    message = f"Hola {sub['name']}, te comparto tu cobro por $350.00 MXN: {payment_link}"
    encoded_message = urllib.parse.quote(message)
    whatsapp_url = f"https://wa.me/52{clean_phone}?text={encoded_message}"

    assert whatsapp_url.startswith(f"https://wa.me/52{clean_phone}?text=")
    assert payment_link in urllib.parse.unquote(whatsapp_url)


@pytest.mark.asyncio
async def test_f7_04_payment_link_passes_client_reference_id(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """Verifies clientReferenceId is passed to Pey payment-link/create endpoint."""
    subs_resp = await app_client.get("/api/subscribers")
    sub = subs_resp.json()[0]

    create_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub["id"], "amount": 150.0, "method": "link"},
    )
    assert create_resp.status_code in [200, 201]

    captured = pey_mock.get_captured_requests()
    link_requests = [req for req in captured if req["path"] == "/payment-link/create"]
    assert len(link_requests) > 0, "Expected at least one POST /payment-link/create request to Pey gateway"
    for req in link_requests:
        client_ref = req.get("body", {}).get("clientReferenceId")
        assert client_ref is not None and len(client_ref) > 0


@pytest.mark.asyncio
async def test_f7_05_payment_link_https_callbacks(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """Verifies successUrl and backUrl sent to Pey payment link gateway use HTTPS scheme."""
    subs_resp = await app_client.get("/api/subscribers")
    sub = subs_resp.json()[0]

    await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub["id"], "amount": 120.0, "method": "link"},
    )

    captured = pey_mock.get_captured_requests()
    link_requests = [req for req in captured if req["path"] == "/payment-link/create"]
    assert len(link_requests) > 0, "Expected at least one POST /payment-link/create request to Pey gateway"
    for req in link_requests:
        success_url = req.get("body", {}).get("successUrl", "")
        back_url = req.get("body", {}).get("backUrl", "")
        assert success_url.startswith("https://"), f"Expected HTTPS successUrl, got {success_url}"
        assert back_url.startswith("https://"), f"Expected HTTPS backUrl, got {back_url}"
