import os
import unittest.mock as mock
import pytest
import httpx

from backend.pey_client import (
    PeyAPIError,
    PeyAuthError,
    PeyClient,
    PeyConnectionError,
    check_credentials,
    create_codi_qr,
    create_payment_link,
    get_codi_qr_transactions,
    get_payment_link_status,
    get_pey_api_key,
    is_codi_qr_paid,
    is_payment_link_paid,
)

_RealAsyncClient = httpx.AsyncClient


def test_get_pey_api_key_from_env(monkeypatch):
    monkeypatch.setenv("PEY_API_KEY", "test_env_key_12345")
    key = get_pey_api_key()
    assert key == "test_env_key_12345"


def test_get_pey_api_key_fallback_file(monkeypatch, tmp_path):
    monkeypatch.delenv("PEY_API_KEY", raising=False)
    # Check that if key file exists it reads from it
    key_file = tmp_path / "apiPey.txt"
    key_file.write_text("file_key_abcde")
    monkeypatch.chdir(tmp_path)
    assert get_pey_api_key() == "file_key_abcde"


def test_pey_client_auth_headers_bearer_format():
    client = PeyClient(api_key="sk_live_sample_token")
    headers = client._get_headers()
    # Must use Bearer token header, never x-api-key
    assert headers["Authorization"] == "Bearer sk_live_sample_token"
    assert "x-api-key" not in headers
    assert headers["Content-Type"] == "application/json"


def test_pey_client_missing_key_raises_auth_error():
    client = PeyClient(api_key="")
    with pytest.raises(PeyAuthError):
        client._get_headers()


@pytest.mark.asyncio
async def test_check_credentials_success():
    client = PeyClient(api_key="valid_token")

    async def mock_handler(request: httpx.Request):
        assert request.headers["Authorization"] == "Bearer valid_token"
        assert request.url.path == "/transaction/api-key"
        return httpx.Response(200, json={"items": [], "nextToken": None})

    mock_transport = httpx.MockTransport(mock_handler)
    with mock.patch("backend.pey_client.httpx.AsyncClient", side_effect=lambda *a, **kw: _RealAsyncClient(transport=mock_transport)):
        res = await client.check_credentials()
        assert res["authenticated"] is True
        assert res["status"] == "ok"


@pytest.mark.asyncio
async def test_check_credentials_unauthorized():
    client = PeyClient(api_key="invalid_token")

    async def mock_handler(request: httpx.Request):
        return httpx.Response(401, json={"message": "Unauthorized"})

    mock_transport = httpx.MockTransport(mock_handler)
    with mock.patch("backend.pey_client.httpx.AsyncClient", side_effect=lambda *a, **kw: _RealAsyncClient(transport=mock_transport)):
        with pytest.raises(PeyAuthError):
            await client.check_credentials()


@pytest.mark.asyncio
async def test_check_credentials_connection_error():
    client = PeyClient(api_key="valid_token")

    async def mock_handler(request: httpx.Request):
        raise httpx.ConnectError("Connection refused")

    mock_transport = httpx.MockTransport(mock_handler)
    with mock.patch("backend.pey_client.httpx.AsyncClient", side_effect=lambda *a, **kw: _RealAsyncClient(transport=mock_transport)):
        with pytest.raises(PeyConnectionError):
            await client.check_credentials()


@pytest.mark.asyncio
async def test_create_codi_qr_mock():
    client = PeyClient(api_key="valid_token")
    captured_payload = {}

    async def mock_handler(request: httpx.Request):
        nonlocal captured_payload
        assert request.headers["Authorization"] == "Bearer valid_token"
        assert request.url.path == "/codi/qr"
        import json
        captured_payload = json.loads(request.content.decode("utf-8"))
        return httpx.Response(201, json={
            "id": "35a13c183a",
            "qrString": '{"TYP":20,"ic":{"IDC":"35a13c183a"}}',
            "qrImage": "iVBORw0KGgoAAAANSUhEUgAA...",
        })

    mock_transport = httpx.MockTransport(mock_handler)
    with mock.patch("backend.pey_client.httpx.AsyncClient", side_effect=lambda *a, **kw: _RealAsyncClient(transport=mock_transport)):
        res = await client.create_codi_qr(
            amount=0.05,
            concept="Membresia Gym",
            num_ref="1234567",
            expiration=0,
            generate_image=True,
        )
        assert res["id"] == "35a13c183a"
        assert "qrString" in res
        assert "qrImage" in res
        assert captured_payload["amount"] == 0.05
        assert captured_payload["concept"] == "Membresia Gym"
        assert captured_payload["numRef"] == "1234567"
        assert captured_payload["expiration"] == 0
        assert captured_payload["generateImage"] is True


@pytest.mark.asyncio
async def test_create_codi_qr_num_ref_formatting():
    client = PeyClient(api_key="valid_token")
    captured_payload = {}

    async def mock_handler(request: httpx.Request):
        nonlocal captured_payload
        import json
        captured_payload = json.loads(request.content.decode("utf-8"))
        return httpx.Response(201, json={"id": "idc123", "qrString": "", "qrImage": ""})

    mock_transport = httpx.MockTransport(mock_handler)
    with mock.patch("backend.pey_client.httpx.AsyncClient", side_effect=lambda *a, **kw: _RealAsyncClient(transport=mock_transport)):
        # num_ref with extra characters or length > 7
        await client.create_codi_qr(amount=10.0, num_ref="REF-9876543210")
        # Should be sanitized to numeric and truncated to at most 7 digits
        assert len(captured_payload["numRef"]) <= 7
        assert captured_payload["numRef"].isdigit()

        # expiration between 1 and 359 clamped to 360
        await client.create_codi_qr(amount=10.0, expiration=60)
        assert captured_payload["expiration"] == 360


@pytest.mark.asyncio
async def test_create_codi_qr_negative_amount_raises():
    client = PeyClient(api_key="valid_token")
    with pytest.raises(ValueError, match="greater than or equal to 0"):
        await client.create_codi_qr(amount=-5.0)


@pytest.mark.asyncio
async def test_create_payment_link_mock():
    client = PeyClient(api_key="valid_token")
    captured_payload = {}

    async def mock_handler(request: httpx.Request):
        nonlocal captured_payload
        assert request.headers["Authorization"] == "Bearer valid_token"
        assert request.url.path == "/payment-link/create"
        import json
        captured_payload = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={
            "id": "01M7ERP9CZX7RTKVP84G5NXN0N",
            "url": "https://app.mipey.mx/checkout/payment-link/01M7ERP9CZX7RTKVP84G5NXN0N",
        })

    mock_transport = httpx.MockTransport(mock_handler)
    with mock.patch("backend.pey_client.httpx.AsyncClient", side_effect=lambda *a, **kw: _RealAsyncClient(transport=mock_transport)):
        res = await client.create_payment_link(
            amount=0.05,
            success_url="https://klipo.onrender.com/success",
            back_url="https://klipo.onrender.com/cancel",
            client_reference_id="charge_123",
        )
        assert res["id"] == "01M7ERP9CZX7RTKVP84G5NXN0N"
        assert "url" in res
        assert captured_payload["amount"] == 0.05
        assert captured_payload["successUrl"].startswith("https://")
        assert captured_payload["backUrl"].startswith("https://")
        assert captured_payload["clientReferenceId"] == "charge_123"


@pytest.mark.asyncio
async def test_create_payment_link_zero_amount_raises():
    client = PeyClient(api_key="valid_token")
    with pytest.raises(ValueError, match="greater than 0"):
        await client.create_payment_link(amount=0)


@pytest.mark.asyncio
async def test_codi_qr_transactions_polling():
    client = PeyClient(api_key="valid_token")

    async def mock_handler(request: httpx.Request):
        if "paid_qr" in request.url.path:
            return httpx.Response(200, json={
                "items": [{"transactionId": "tx1", "status": "PAID", "datePaid": 1790724818}],
                "nextToken": None,
            })
        elif "pending_qr" in request.url.path:
            return httpx.Response(200, json={
                "items": [{"transactionId": "tx2", "status": "PENDING"}],
                "nextToken": None,
            })
        elif "empty_qr" in request.url.path:
            return httpx.Response(200, json={"items": [], "nextToken": None})
        else:
            return httpx.Response(404, json={"message": "Not Found"})

    mock_transport = httpx.MockTransport(mock_handler)
    with mock.patch("backend.pey_client.httpx.AsyncClient", side_effect=lambda *a, **kw: _RealAsyncClient(transport=mock_transport)):
        assert await client.is_codi_qr_paid("paid_qr") is True
        assert await client.is_codi_qr_paid("pending_qr") is False
        assert await client.is_codi_qr_paid("empty_qr") is False
        assert await client.is_codi_qr_paid("unknown_qr") is False


@pytest.mark.asyncio
async def test_payment_link_status_polling():
    client = PeyClient(api_key="valid_token")

    async def mock_handler(request: httpx.Request):
        if "paid_link" in request.url.path:
            return httpx.Response(200, json={"id": "paid_link", "status": "paid"})
        elif "pending_link" in request.url.path:
            return httpx.Response(200, json={"id": "pending_link", "status": "pending"})
        else:
            return httpx.Response(404, json={"message": "Not Found"})

    mock_transport = httpx.MockTransport(mock_handler)
    with mock.patch("backend.pey_client.httpx.AsyncClient", side_effect=lambda *a, **kw: _RealAsyncClient(transport=mock_transport)):
        assert await client.is_payment_link_paid("paid_link") is True
        assert await client.is_payment_link_paid("pending_link") is False
        assert await client.is_payment_link_paid("unknown_link") is False


@pytest.mark.asyncio
async def test_live_pey_credentials():
    """Live test verifying real credentials against https://api.pey.mx/transaction/api-key."""
    key = get_pey_api_key()
    if not key:
        pytest.skip("Pey API key not found in environment or apiPey.txt; skipping live probe.")

    client = PeyClient(api_key=key)
    res = await client.check_credentials()
    assert res.get("authenticated") is True
    assert "items" in res
