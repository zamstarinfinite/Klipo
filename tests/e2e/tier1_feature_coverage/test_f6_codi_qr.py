"""
Feature 6: CoDi QR Code Generation
Validates POST /api/charges, database persistence, numRef validation, and QR payload integrity.
"""

import httpx
import pytest
from tests.e2e.pey_mock_server import PeyMockServer


@pytest.mark.asyncio
async def test_f6_01_create_codi_charge_success(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """Verifies creating a charge creates a record with status 'pending' and method 'codi'."""
    # Find an existing subscriber
    subs_resp = await app_client.get("/api/subscribers")
    assert subs_resp.status_code == 200
    sub = subs_resp.json()[0]

    charge_payload = {
        "subscriber_id": sub["id"],
        "amount": 350.0,
        "method": "codi",
    }
    resp = await app_client.post("/api/charges", json=charge_payload)
    assert resp.status_code in [200, 201]
    charge = resp.json()

    assert charge["subscriber_id"] == sub["id"]
    assert float(charge["amount"]) == 350.0
    assert charge["status"] in ["pending", "pendiente"]
    assert charge["method"] in ["codi", "CoDi"]

    # Assert CoDi QR and qr_image unconditionally
    assert "codi_qr_id" in charge and charge["codi_qr_id"] is not None and len(charge["codi_qr_id"]) > 0
    assert "qr_image" in charge and charge["qr_image"] is not None and len(charge["qr_image"]) > 0
    assert charge["qr_image"].startswith("iVBOR") or "image/png" in charge["qr_image"] or len(charge["qr_image"]) > 50


@pytest.mark.asyncio
async def test_f6_02_codi_charge_persisted_to_database(app_client: httpx.AsyncClient):
    """Verifies that charge created via POST /api/charges is immediately visible in GET /api/charges."""
    subs_resp = await app_client.get("/api/subscribers")
    sub = subs_resp.json()[0]

    charge_payload = {
        "subscriber_id": sub["id"],
        "amount": 250.0,
        "method": "codi",
    }
    create_resp = await app_client.post("/api/charges", json=charge_payload)
    assert create_resp.status_code in [200, 201]
    charge_id = create_resp.json()["id"]

    list_resp = await app_client.get("/api/charges")
    assert list_resp.status_code == 200
    charges = list_resp.json()
    assert any(c["id"] == charge_id for c in charges)


@pytest.mark.asyncio
async def test_f6_03_codi_payload_numref_is_numeric_digits(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """Verifies that any numRef sent to Pey gateway contains 1 to 7 numeric digits."""
    subs_resp = await app_client.get("/api/subscribers")
    sub = subs_resp.json()[0]

    await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub["id"], "amount": 100.0, "method": "codi"},
    )

    captured = pey_mock.get_captured_requests()
    codi_requests = [req for req in captured if req["path"] == "/codi/qr"]
    assert len(codi_requests) > 0, "Expected at least one POST /codi/qr request to Pey gateway"
    for req in codi_requests:
        num_ref = str(req.get("body", {}).get("numRef", ""))
        assert num_ref.isdigit(), f"numRef must be numeric digits, got: {num_ref}"
        assert 1 <= len(num_ref) <= 7, f"numRef must be 1-7 digits, got: {num_ref}"


test_f6_03_codi_payload_numref_format = test_f6_03_codi_payload_numref_is_numeric_digits


@pytest.mark.asyncio
async def test_f6_04_codi_payload_expiration_setting(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """Verifies that expiration parameter in CoDi QR payload is 0 or >= 360."""
    subs_resp = await app_client.get("/api/subscribers")
    sub = subs_resp.json()[0]

    await app_client.post(
        "/api/charges",
        json={"subscriber_id": sub["id"], "amount": 50.0, "method": "codi"},
    )

    captured = pey_mock.get_captured_requests()
    codi_requests = [req for req in captured if req["path"] == "/codi/qr"]
    assert len(codi_requests) > 0, "Expected at least one POST /codi/qr request to Pey gateway"
    for req in codi_requests:
        expiration = req.get("body", {}).get("expiration", 0)
        assert expiration == 0 or expiration >= 360, f"Invalid CoDi expiration: {expiration}"


@pytest.mark.asyncio
async def test_f6_05_codi_error_handling_invalid_subscriber(app_client: httpx.AsyncClient):
    """Verifies POST /api/charges returns 404 when subscriber_id does not exist."""
    invalid_payload = {
        "subscriber_id": "non_existent_subscriber_id_9999",
        "amount": 250.0,
        "method": "codi",
    }
    resp = await app_client.post("/api/charges", json=invalid_payload)
    assert resp.status_code == 404
    data = resp.json()
    assert "detail" in data or "message" in data or "error" in data
