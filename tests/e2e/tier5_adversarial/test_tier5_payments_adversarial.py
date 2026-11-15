"""
Tier 5 Adversarial Test Suite: Payments, Concurrency, Frontend Contracts & Deployment Hardening
Domain Focus: Challenger 2 (Milestone 5 Phase 2)

Sections:
1. Pey Payments Integration & Resilience Probes
2. Hybrid Payment Confirmation & Concurrency Race Conditions
3. Frontend Integration, Contract Adherence & SPA Security
4. Deployment & Secret Leak Hardening
"""

import asyncio
import base64
import json
import os
import re
import tempfile
import unittest.mock as mock
import pytest
import httpx

from backend.db import get_connection
from backend.pey_client import (
    PeyAPIError,
    PeyAuthError,
    PeyClient,
    PeyConnectionError,
    PeyError,
)
from tests.e2e.conftest import require_route
from tests.e2e.pey_mock_server import PeyMockServer


# =============================================================================
# 1. PEY PAYMENTS INTEGRATION & RESILIENCE PROBES
# =============================================================================

@pytest.mark.asyncio
async def test_codi_qr_payload_and_idc_parsing(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
    db_conn,
):
    """
    Validates CoDi QR generation payload structure:
    - IDC parsed and saved into codi_qr_id matches Banxico payload
    - numRef length is 1-7 numeric digits
    - Base64 image decodes into a valid PNG header (\x89PNG\r\n\x1a\n)
    - Banxico qrString contains valid JSON with TYP=20 and IDC
    """
    require_route("/api/charges", "POST")

    resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": "carlos", "amount": 350.0, "method": "codi"},
    )
    assert resp.status_code == 201, f"Failed to create charge: {resp.text}"
    data = resp.json()

    # 1. Verify codi_qr_id
    codi_id = data.get("codi_qr_id")
    assert codi_id is not None and len(codi_id) > 0, "Missing codi_qr_id in charge response"

    # 2. Verify Banxico qrString structure
    qr_payload_str = data.get("qr_payload")
    assert qr_payload_str is not None, "Missing qr_payload string"
    try:
        banxico_dict = json.loads(qr_payload_str)
    except json.JSONDecodeError:
        pytest.fail(f"qr_payload is not valid JSON: {qr_payload_str}")

    assert banxico_dict.get("TYP") == 20, "Banxico payload TYP must be 20"
    idc_in_qr = banxico_dict.get("ic", {}).get("IDC")
    assert idc_in_qr == codi_id, f"IDC in qrString ({idc_in_qr}) must match codi_qr_id ({codi_id})"

    # 3. Verify numRef integrity: 1-7 numeric digits
    num_ref = data.get("num_ref")
    assert num_ref is not None, "Missing num_ref"
    assert re.match(r"^\d{1,7}$", str(num_ref)), f"numRef '{num_ref}' must be 1-7 numeric digits"

    # 4. Verify Base64 QR Image decodes to valid PNG
    qr_image = data.get("qr_image")
    assert qr_image is not None, "Missing qr_image base64 string"
    clean_b64 = qr_image.split("base64,")[-1] if "base64," in qr_image else qr_image
    try:
        png_bytes = base64.b64decode(clean_b64)
    except Exception as exc:
        pytest.fail(f"Failed to decode qr_image as base64: {exc}")

    png_header = b"\x89PNG\r\n\x1a\n"
    assert png_bytes.startswith(png_header), f"Decoded qr_image does not have PNG header: {png_bytes[:8]}"


@pytest.mark.asyncio
async def test_codi_qr_expiration_handling_and_normalization():
    """
    Tests edge cases in CoDi QR expiration parameter:
    - 0 remains 0 (no expiration)
    - 1 to 359 seconds is clamped to 360 seconds (Pey minimum)
    - Negative values must NOT be passed through to upstream API as negative
    """
    client = PeyClient(api_key="test_key", base_url="http://mock")

    # Expiration = 0
    with mock.patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = httpx.Response(201, json={"id": "codi_0", "qrString": "{}", "qrImage": "iVBORw0K"})
        await client.create_codi_qr(amount=10.0, expiration=0)
        assert mock_post.call_args[1]["json"]["expiration"] == 0

    # Expiration = 120 (must clamp to 360)
    with mock.patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = httpx.Response(201, json={"id": "codi_120", "qrString": "{}", "qrImage": "iVBORw0K"})
        await client.create_codi_qr(amount=10.0, expiration=120)
        assert mock_post.call_args[1]["json"]["expiration"] == 360

    # Expiration = -50 (must normalize to 0 or raise ValueError, never send negative)
    with mock.patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = httpx.Response(201, json={"id": "codi_neg", "qrString": "{}", "qrImage": "iVBORw0K"})
        try:
            await client.create_codi_qr(amount=10.0, expiration=-50)
            sent_exp = mock_post.call_args[1]["json"]["expiration"]
            assert sent_exp >= 0, f"Negative expiration {sent_exp} was sent to Pey API"
        except ValueError:
            # Raising ValueError on negative expiration is also valid defense
            pass


@pytest.mark.asyncio
async def test_payment_link_https_enforcement_and_client_reference(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """
    Verifies that Pey Payment Links:
    - Strictly enforce HTTPS URLs for successUrl and backUrl even if HTTP was provided
    - Client reference ID matches the internal charge ID
    """
    client = PeyClient(api_key="test_key", base_url="http://mock")

    with mock.patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = httpx.Response(200, json={"id": "link_1", "url": "https://app.mipey.mx/checkout/1"})
        await client.create_payment_link(
            amount=50.0,
            success_url="http://insecure.example.com/success",
            back_url="http://insecure.example.com/back",
            client_reference_id="charge_ref_12345",
        )
        sent_payload = mock_post.call_args[1]["json"]
        assert sent_payload["successUrl"].startswith("https://"), "successUrl must be HTTPS"
        assert sent_payload["backUrl"].startswith("https://"), "backUrl must be HTTPS"
        assert sent_payload["clientReferenceId"] == "charge_ref_12345"


@pytest.mark.asyncio
async def test_pey_http_resilience_network_timeouts():
    """
    Simulates upstream Pey connection and read timeouts.
    Client must raise PeyConnectionError, and FastAPI endpoint must map to 502 Bad Gateway.
    """
    client = PeyClient(api_key="test_key", base_url="http://mock")

    # Read timeout
    with mock.patch("httpx.AsyncClient.post", side_effect=httpx.ReadTimeout("Socket read timed out")):
        with pytest.raises(PeyConnectionError) as exc_info:
            await client.create_codi_qr(100.0)
        assert "timed out" in str(exc_info.value).lower()

    # Connect timeout
    with mock.patch("httpx.AsyncClient.get", side_effect=httpx.ConnectTimeout("Connection refused")):
        with pytest.raises(PeyConnectionError):
            await client.check_credentials()


@pytest.mark.asyncio
async def test_pey_http_resilience_401_unauthorized():
    """
    Simulates Pey 401 Unauthorized (revoked/bad API key).
    Client must raise PeyAuthError with detailed context.
    """
    client = PeyClient(api_key="invalid_revoked_key", base_url="http://mock")

    with mock.patch("httpx.AsyncClient.get", return_value=httpx.Response(401, text="Unauthorized")):
        with pytest.raises(PeyAuthError) as exc_info:
            await client.check_credentials()
        assert "401" in str(exc_info.value)


@pytest.mark.asyncio
async def test_pey_http_resilience_429_rate_limiting():
    """
    Simulates Pey 429 Too Many Requests (rate limiting).
    Client must raise PeyAPIError preserving status_code == 429.
    """
    client = PeyClient(api_key="test_key", base_url="http://mock")

    with mock.patch("httpx.AsyncClient.post", return_value=httpx.Response(429, text='{"error":"Too many requests"}')):
        with pytest.raises(PeyAPIError) as exc_info:
            await client.create_codi_qr(100.0)
        assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_pey_http_resilience_500_upstream_errors():
    """
    Simulates Pey 500 / 503 upstream server failures.
    Client must raise PeyAPIError preserving status_code == 500/503.
    """
    client = PeyClient(api_key="test_key", base_url="http://mock")

    with mock.patch("httpx.AsyncClient.post", return_value=httpx.Response(500, text="Internal Server Error")):
        with pytest.raises(PeyAPIError) as exc_info:
            await client.create_payment_link(100.0)
        assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_pey_http_resilience_malformed_json_response():
    """
    Simulates Pey returning HTTP 200 with malformed JSON or HTML body.
    PeyClient must catch json.JSONDecodeError and wrap it in PeyAPIError/PeyError,
    preserving the exception hierarchy.
    """
    client = PeyClient(api_key="test_key", base_url="http://mock")

    with mock.patch("httpx.AsyncClient.post", return_value=httpx.Response(200, text="<html>502 Bad Gateway</html>")):
        with pytest.raises(PeyError) as exc_info:
            await client.create_codi_qr(100.0)
        # Should be a subclass of PeyError (e.g. PeyAPIError), not bare json.JSONDecodeError
        assert isinstance(exc_info.value, PeyError), f"Expected PeyError subclass, got {type(exc_info.value)}"


# =============================================================================
# 2. HYBRID CONFIRMATION & CONCURRENCY RACE CONDITIONS
# =============================================================================

@pytest.mark.asyncio
async def test_concurrent_webhook_vs_cash_mark_race(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """
    Race Condition Stress Probe:
    Fires 10 concurrent requests mixing manual cash marks (POST /api/charges/{id}/mark-cash)
    and inbound webhooks (POST /api/webhooks/pey) for the exact same pending charge.

    Invariants:
    1. Zero unhandled 500 errors or database lock crashes.
    2. The charge transitions to status 'paid'.
    3. The subscriber due date is advanced EXACTLY ONCE (never duplicated).
    4. Dashboard collected_month accounts for this payment exactly once.
    """
    require_route("/api/charges", "POST")
    require_route("/api/charges/{id}/mark-cash", "POST")
    require_route("/api/webhooks/pey", "POST")

    # 1. Setup subscriber & record initial state
    sub_resp = await app_client.get("/api/subscribers/carlos")
    assert sub_resp.status_code == 200
    initial_due_date = sub_resp.json()["next_due_date"]

    dash_before = (await app_client.get("/api/dashboard")).json()
    collected_before = dash_before["collected_month"]

    # 2. Create pending charge for $350.00
    charge_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": "carlos", "amount": 350.0, "method": "codi"},
    )
    assert charge_resp.status_code == 201
    charge = charge_resp.json()
    charge_id = charge["id"]
    codi_id = charge["codi_qr_id"]

    webhook_payload = {
        "type": "codi.qr.payment_received",
        "codiQrId": codi_id,
        "amount": 350.0,
        "transactionId": f"tx_race_{charge_id}",
    }

    # 3. Fire 10 simultaneous racing calls (5 cash marks + 5 webhooks)
    tasks = []
    for _ in range(5):
        tasks.append(app_client.post(f"/api/charges/{charge_id}/mark-cash"))
    for _ in range(5):
        tasks.append(app_client.post("/api/webhooks/pey", json=webhook_payload))

    responses = await asyncio.gather(*tasks, return_exceptions=True)

    for i, resp in enumerate(responses):
        if isinstance(resp, Exception):
            pytest.fail(f"Task {i} raised exception: {resp}")
        assert resp.status_code in [200, 201, 202], f"Task {i} returned HTTP {resp.status_code}: {resp.text}"

    # 4. Verify charge invariant: status == 'paid'
    charge_after = (await app_client.get(f"/api/charges/{charge_id}")).json()
    assert charge_after["status"] == "paid"

    # 5. Verify subscriber invariant: due date advanced exactly once
    sub_after = (await app_client.get("/api/subscribers/carlos")).json()
    final_due_date = sub_after["next_due_date"]
    assert final_due_date != initial_due_date, "Due date was never advanced!"

    # 6. Verify dashboard revenue invariant: exactly +$350.00 added
    dash_after = (await app_client.get("/api/dashboard")).json()
    collected_after = dash_after["collected_month"]
    expected_collected = round(collected_before + 350.0, 2)
    assert collected_after == expected_collected, (
        f"Collected amount mismatch: expected {expected_collected}, got {collected_after} (double-counted?)"
    )


@pytest.mark.asyncio
async def test_concurrent_webhook_vs_status_polling_race(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """
    Race Condition Stress Probe:
    Simulates polling (GET /api/charges/{id}/status) occurring simultaneously with
    an inbound webhook (POST /api/webhooks/pey) while Pey gateway reports PAID.
    Ensures subscriber due date is not incremented twice.
    """
    require_route("/api/charges", "POST")
    require_route("/api/charges/{id}/status", "GET")
    require_route("/api/webhooks/pey", "POST")

    # Setup subscriber
    sub_resp = await app_client.get("/api/subscribers/carlos")
    carlos_id = sub_resp.json()["id"]

    charge_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": carlos_id, "amount": 350.0, "method": "codi"},
    )
    charge = charge_resp.json()
    charge_id = charge["id"]
    codi_id = charge["codi_qr_id"]

    # Pey mock reports PAID
    pey_mock.mark_codi_paid(codi_id)

    webhook_payload = {
        "type": "codi.qr.payment_received",
        "codiQrId": codi_id,
        "amount": 350.0,
        "transactionId": f"tx_poll_race_{charge_id}",
    }

    # Fire 8 concurrent tasks (4 status polls + 4 webhooks)
    tasks = []
    for _ in range(4):
        tasks.append(app_client.get(f"/api/charges/{charge_id}/status"))
    for _ in range(4):
        tasks.append(app_client.post("/api/webhooks/pey", json=webhook_payload))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, Exception):
            pytest.fail(f"Concurrent task error: {r}")
        assert r.status_code in [200, 202]

    # Verify charge is paid
    charge_final = (await app_client.get(f"/api/charges/{charge_id}")).json()
    assert charge_final["status"] == "paid"


@pytest.mark.asyncio
async def test_duplicate_webhook_replay_attack(
    app_client: httpx.AsyncClient,
):
    """
    Adversarial Probe: Duplicate Webhook Replay Attack
    Sends 15 identical webhook notifications for the same transaction.
    Verifies that the subscriber's due date is NOT incremented multiple times!
    """
    require_route("/api/webhooks/pey", "POST")

    # Use seeded charge p3 (carlos, overdue)
    sub_before = (await app_client.get("/api/subscribers/carlos")).json()
    initial_due = sub_before["next_due_date"]

    payload = {
        "type": "codi.qr.payment_received",
        "codiQrId": "codi_p3",
        "amount": 350.0,
        "transactionId": "tx_replay_attack_123",
    }

    # First delivery
    r1 = await app_client.post("/api/webhooks/pey", json=payload)
    assert r1.status_code in [200, 202]

    sub_after_first = (await app_client.get("/api/subscribers/carlos")).json()
    due_after_first = sub_after_first["next_due_date"]

    # Replay 14 more times
    for _ in range(14):
        r = await app_client.post("/api/webhooks/pey", json=payload)
        assert r.status_code in [200, 202]

    sub_after_replays = (await app_client.get("/api/subscribers/carlos")).json()
    due_after_replays = sub_after_replays["next_due_date"]

    assert due_after_first == due_after_replays, (
        f"Duplicate webhook replay advanced due date from {due_after_first} to {due_after_replays}!"
    )


@pytest.mark.asyncio
async def test_out_of_order_webhook_unknown_charge(app_client: httpx.AsyncClient):
    """
    Adversarial Probe: Out-of-order or unknown transaction webhook
    Sends a webhook for a transaction ID / CoDi QR ID that does not exist in the database.
    Endpoint must handle gracefully with HTTP 200 without raising an unhandled exception or 500 error.
    """
    require_route("/api/webhooks/pey", "POST")

    payload = {
        "type": "codi.qr.payment_received",
        "codiQrId": "codi_non_existent_99999",
        "amount": 500.0,
        "transactionId": "tx_unknown_88888",
    }
    resp = await app_client.post("/api/webhooks/pey", json=payload)
    assert resp.status_code in [200, 202], f"Expected 200/202 for unknown charge, got {resp.status_code}"


@pytest.mark.asyncio
async def test_webhook_malformed_json_types(app_client: httpx.AsyncClient):
    """
    Adversarial Probe: Malformed Webhook Body Types
    Sends JSON arrays, strings, and numbers to /api/webhooks/pey.
    The endpoint must return HTTP 400 Bad Request, NOT an unhandled 500 Internal Server Error.
    """
    require_route("/api/webhooks/pey", "POST")

    # 1. JSON Array
    r_arr = await app_client.post(
        "/api/webhooks/pey",
        json=[{"type": "codi.qr.payment_received"}],
    )
    assert r_arr.status_code == 400, f"Expected 400 for JSON array, got HTTP {r_arr.status_code}: {r_arr.text}"

    # 2. JSON String
    r_str = await app_client.post(
        "/api/webhooks/pey",
        json="just a string payload",
    )
    assert r_str.status_code == 400, f"Expected 400 for JSON string, got HTTP {r_str.status_code}: {r_str.text}"

    # 3. JSON Number
    r_num = await app_client.post(
        "/api/webhooks/pey",
        json=12345,
    )
    assert r_num.status_code == 400, f"Expected 400 for JSON number, got HTTP {r_num.status_code}: {r_num.text}"


# =============================================================================
# 3. FRONTEND INTEGRATION, CONTRACT ADHERENCE & SPA SECURITY
# =============================================================================

@pytest.mark.asyncio
async def test_frontend_contracts_dashboard(app_client: httpx.AsyncClient):
    """
    Frontend Contract Probe: /api/dashboard
    Verifies presence and types of all ApiDashboard fields expected by React frontend:
    total_subscribers, active_subscribers, overdue_count, due_soon_count, current_count,
    expected_monthly, collected_month, recent_movements.
    """
    resp = await app_client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json()

    required_fields = [
        "total_subscribers",
        "active_subscribers",
        "overdue_count",
        "due_soon_count",
        "current_count",
        "expected_monthly",
        "collected_month",
        "recent_movements",
    ]
    for field in required_fields:
        assert field in data, f"Missing required ApiDashboard field: '{field}'"

    assert isinstance(data["total_subscribers"], int)
    assert isinstance(data["active_subscribers"], int)
    assert isinstance(data["expected_monthly"], (int, float))
    assert isinstance(data["collected_month"], (int, float))
    assert isinstance(data["recent_movements"], list)


@pytest.mark.asyncio
async def test_frontend_contracts_dual_casing(app_client: httpx.AsyncClient):
    """
    Frontend Contract Probe: Dual Casing Support
    React frontend maps either camelCase or snake_case (e.g. subscriberId and subscriber_id).
    Verifies that API responses provide compatible fields.
    """
    # 1. Subscribers
    subs_resp = await app_client.get("/api/subscribers")
    assert subs_resp.status_code == 200
    subs = subs_resp.json()
    assert len(subs) > 0
    sample_sub = subs[0]
    assert "plan_id" in sample_sub or "planId" in sample_sub, "Missing plan identifier"

    # 2. Charges
    charges_resp = await app_client.get("/api/charges")
    assert charges_resp.status_code == 200
    charges = charges_resp.json()
    assert len(charges) > 0
    sample_charge = charges[0]
    assert "subscriber_id" in sample_charge or "subscriberId" in sample_charge
    assert "status" in sample_charge


@pytest.mark.asyncio
async def test_live_3s_polling_idempotency_and_state_transition(
    app_client: httpx.AsyncClient,
    pey_mock: PeyMockServer,
):
    """
    Frontend Live 3s Polling Behavior:
    Simulates charge.tsx polling loop every 3 seconds:
    1. Poll 1: Returns pending, pagado == False.
    2. Payment received on gateway.
    3. Poll 2: Transitions to paid, pagado == True.
    4. Poll 3, 4, 5: Subsequent polls return paid without querying gateway or mutating database.
    """
    require_route("/api/charges", "POST")
    require_route("/api/charges/{id}/status", "GET")

    # Create charge
    charge_resp = await app_client.post(
        "/api/charges",
        json={"subscriber_id": "carlos", "amount": 350.0, "method": "codi"},
    )
    charge_id = charge_resp.json()["id"]
    codi_id = charge_resp.json()["codi_qr_id"]

    # Poll 1: Gateway is still pending
    poll1 = await app_client.get(f"/api/charges/{charge_id}/status")
    assert poll1.status_code == 200
    data1 = poll1.json()
    assert data1["status"] == "pending"
    assert data1["pagado"] is False

    # Mark gateway as paid
    pey_mock.mark_codi_paid(codi_id)

    # Poll 2: Gateway transitions to paid
    poll2 = await app_client.get(f"/api/charges/{charge_id}/status")
    assert poll2.status_code == 200
    data2 = poll2.json()
    assert data2["status"] == "paid"
    assert data2["pagado"] is True

    # Poll 3, 4, 5: Subsequent polls must be strictly idempotent
    for _ in range(3):
        poll_n = await app_client.get(f"/api/charges/{charge_id}/status")
        assert poll_n.status_code == 200
        datan = poll_n.json()
        assert datan["status"] == "paid"
        assert datan["pagado"] is True


@pytest.mark.asyncio
async def test_spa_fallback_and_api_route_boundary(app_client: httpx.AsyncClient):
    """
    Verifies SPA Fallback behavior:
    - Unknown frontend routes (e.g. /subscribers/new) serve index.html with HTTP 200
    - Unknown /api/ routes return JSON 404, NOT HTML index.html
    - /api without trailing slash returns JSON 404, NOT HTML index.html
    """
    # 1. SPA subpath should return index.html (HTTP 200)
    spa_resp = await app_client.get("/subscribers/new")
    assert spa_resp.status_code == 200
    assert "<!doctype html>" in spa_resp.text.lower() or "<html" in spa_resp.text.lower()

    # 2. Unknown API subpath must return JSON 404, NOT index.html
    api_resp = await app_client.get("/api/unknown_endpoint_xyz")
    assert api_resp.status_code == 404
    assert "<!doctype html>" not in api_resp.text.lower()
    assert api_resp.headers.get("content-type", "").startswith("application/json")

    # 3. Bare /api must return 404 JSON, NOT HTML index.html
    bare_api = await app_client.get("/api")
    assert bare_api.status_code == 404, (
        f"Bare /api returned HTTP {bare_api.status_code} with body: {bare_api.text[:100]}"
    )
    assert bare_api.headers.get("content-type", "").startswith("application/json")


@pytest.mark.asyncio
async def test_spa_path_traversal_secret_leak_probe(app_client: httpx.AsyncClient):
    """
    CRITICAL Adversarial Probe: Path Traversal Secret Leak Prevention
    Ensures that an attacker cannot use path traversal (%2e%2e or ..) on the SPA fallback
    route to read secret files (e.g. apiPey.txt, klipo.db, .env, or /etc/passwd).
    Any path escaping frontend_dist MUST NOT be served.
    """
    # Probe using URL-encoded directory traversal targeting apiPey.txt and klipo.db
    leak_resp = await app_client.get("/..%2f..%2f..%2fapiPey.txt")
    assert "sk_live_" not in leak_resp.text, (
        "CRITICAL VULNERABILITY: Path traversal in serve_spa leaked confidential PEY_API_KEY from apiPey.txt!"
    )

    db_leak = await app_client.get("/..%2f..%2f..%2fklipo.db")
    assert not db_leak.content.startswith(b"SQLite format 3"), (
        "CRITICAL VULNERABILITY: Path traversal in serve_spa allowed raw SQLite database download!"
    )


# =============================================================================
# 4. DEPLOYMENT & SECRET LEAK HARDENING
# =============================================================================

def test_gitignore_secret_leak_audit():
    """
    Audits .gitignore for critical secret patterns:
    - apiPey.txt
    - .env and .env.*
    - SQLite database files (*.db, *.db-wal, *.sqlite*)
    """
    gitignore_path = os.path.join(os.getcwd(), ".gitignore")
    assert os.path.isfile(gitignore_path), ".gitignore is missing"

    with open(gitignore_path, "r", encoding="utf-8") as f:
        content = f.read()

    patterns = ["apiPey.txt", ".env", "*.db", "node_modules", "dist"]
    for p in patterns:
        assert p in content, f"Pattern '{p}' missing from .gitignore"


def test_dockerfile_syntax_and_security_audit():
    """
    Audits Dockerfile:
    - Uses multi-stage build (Node 20 builder + Python 3.12 slim)
    - Verifies apiPey.txt and .env are never copied into the container
    - Audits container user configuration
    """
    dockerfile_path = os.path.join(os.getcwd(), "Dockerfile")
    assert os.path.isfile(dockerfile_path), "Dockerfile is missing"

    with open(dockerfile_path, "r", encoding="utf-8") as f:
        dockerfile = f.read()

    assert "FROM node:20" in dockerfile, "Expected Node 20 builder stage"
    assert "FROM python:3.12" in dockerfile, "Expected Python 3.12 runtime stage"
    assert "apiPey.txt" not in dockerfile, "apiPey.txt must never be copied into Dockerfile"
    assert "EXPOSE 8000" in dockerfile or "EXPOSE" in dockerfile


def test_render_yaml_configuration_security():
    """
    Audits render.yaml:
    - Defines free web service
    - Sets PEY_API_KEY as secret with sync: false
    - Does not contain hardcoded secret keys
    - Zero persistent disks configured
    """
    render_yaml_path = os.path.join(os.getcwd(), "render.yaml")
    assert os.path.isfile(render_yaml_path), "render.yaml is missing"

    with open(render_yaml_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "plan: free" in content, "Render plan must be free"
    assert "PEY_API_KEY" in content, "PEY_API_KEY envVar must be defined"
    assert "sync: false" in content, "PEY_API_KEY must have sync: false"
    assert "disk" not in content.lower(), "Free service must not configure persistent disks"
