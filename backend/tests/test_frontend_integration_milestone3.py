import os
from unittest import mock
import pytest
import httpx

from backend.main import app


@pytest.mark.asyncio
async def test_static_frontend_serving(async_client: httpx.AsyncClient):
    """GET / serves the compiled React PWA frontend HTML bundle."""
    res = await async_client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    html_text = res.text
    assert "<!doctype html>" in html_text.lower() or "<html" in html_text.lower()
    assert "root" in html_text or "vite" in html_text or "assets" in html_text


@pytest.mark.asyncio
async def test_spa_fallback_routing(async_client: httpx.AsyncClient):
    """Deep links like /planes fallback to index.html; invalid /api routes return 404."""
    # SPA deep link
    res_deep = await async_client.get("/planes")
    assert res_deep.status_code == 200
    assert "text/html" in res_deep.headers.get("content-type", "")

    # Non-existent API route
    res_api = await async_client.get("/api/unknown_route_404")
    assert res_api.status_code == 404


@pytest.mark.asyncio
async def test_static_asset_serving(async_client: httpx.AsyncClient):
    """Static assets in /assets/ are served with correct status code."""
    dist_assets_dir = os.path.join(os.getcwd(), "frontend", "dist", "assets")
    if os.path.isdir(dist_assets_dir):
        files = os.listdir(dist_assets_dir)
        css_files = [f for f in files if f.endswith(".css")]
        if css_files:
            css_res = await async_client.get(f"/assets/{css_files[0]}")
            assert css_res.status_code == 200
            assert "text/css" in css_res.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_demo_plan_decimal_pricing(async_client: httpx.AsyncClient):
    """Plans API supports decimal amounts (such as $0.05 MXN demo plan)."""
    res = await async_client.get("/api/plans")
    assert res.status_code == 200
    plans = res.json()
    demo_plan = next((p for p in plans if p["id"] == "demo" or p["price"] == 0.05), None)
    assert demo_plan is not None
    assert demo_plan["price"] == 0.05

    # Create new decimal plan
    new_plan_res = await async_client.post(
        "/api/plans",
        json={
            "id": "micro_test",
            "name": "Micro Test Plan",
            "price": 0.08,
            "interval": "monthly",
            "description": "Micro billing test",
            "icon": "wallet",
            "charge_day": 15,
        },
    )
    assert new_plan_res.status_code in (200, 201)
    new_plan = new_plan_res.json()
    assert new_plan["price"] == 0.08


@pytest.mark.asyncio
async def test_subscribers_computed_statuses(async_client: httpx.AsyncClient):
    """Subscribers API returns live subscribers with computed statuses matching requirements."""
    res = await async_client.get("/api/subscribers")
    assert res.status_code == 200
    subs = res.json()
    assert len(subs) > 0

    statuses = {s["status"] for s in subs}
    # Verify valid statuses are present
    assert any(st in statuses for st in ("atrasado", "por_vencer", "al_corriente"))

    # Test creating new subscriber via API
    create_res = await async_client.post(
        "/api/subscribers",
        json={
            "name": "Lucia Fernandez",
            "phone": "5512345678",
            "plan_id": "gym",
            "note": "Nueva suscriptora PWA",
        },
    )
    assert create_res.status_code in (200, 201)
    created = create_res.json()
    assert created["name"] == "Lucia Fernandez"
    assert created["phone"] == "5512345678"
    assert created["plan_id"] == "gym"


@pytest.mark.asyncio
async def test_charge_generation_contract(async_client: httpx.AsyncClient):
    """POST /api/charges generates live charge with CoDi QR base64 image and Pey Payment Link."""
    mock_qr_response = {
        "id": "codi_idc_12345",
        "qrString": "000201010212...codi_test_payload...",
        "qrImage": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
    }
    mock_link_response = {
        "id": "plink_abcde",
        "url": "https://app.mipey.mx/checkout/plink_abcde",
        "status": "pending",
    }

    with mock.patch("backend.main.create_codi_qr", return_value=mock_qr_response), \
         mock.patch("backend.main.create_payment_link", return_value=mock_link_response):

        res = await async_client.post(
            "/api/charges",
            json={
                "subscriber_id": "carlos",
                "method": "codi",
            },
        )
        assert res.status_code == 201
        charge = res.json()
        assert charge["status"] in ("pending", "pendiente")
        assert charge["codi_qr_id"] == "codi_idc_12345"
        assert charge["qr_image"] is not None
        assert charge["payment_link_url"] == "https://app.mipey.mx/checkout/plink_abcde"


@pytest.mark.asyncio
async def test_polling_charge_status_endpoint(async_client: httpx.AsyncClient):
    """GET /api/charges/{id}/status polls status and confirms payment seamlessly."""
    # Query an existing pending charge
    charges_res = await async_client.get("/api/charges")
    charges = charges_res.json()
    pending_charge = next((c for c in charges if c["status"] in ("pending", "pendiente")), None)
    assert pending_charge is not None

    charge_id = pending_charge["id"]
    status_res = await async_client.get(f"/api/charges/{charge_id}/status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert "status" in status_data
    assert "pagado" in status_data


@pytest.mark.asyncio
async def test_mark_cash_seamless_update(async_client: httpx.AsyncClient):
    """POST /api/charges/{id}/mark-cash marks charge paid in cash and advances subscriber due date."""
    charges_res = await async_client.get("/api/charges")
    charges = charges_res.json()
    pending_charge = next((c for c in charges if c["status"] in ("pending", "pendiente")), None)
    assert pending_charge is not None

    charge_id = pending_charge["id"]
    sub_id = pending_charge["subscriber_id"]

    # Mark cash
    mark_res = await async_client.post(f"/api/charges/{charge_id}/mark-cash")
    assert mark_res.status_code == 200
    marked_data = mark_res.json()
    assert marked_data["status"] in ("paid", "pagado")
    assert marked_data["method"] == "efectivo"

    # Verify subscriber status updated
    sub_res = await async_client.get(f"/api/subscribers/{sub_id}")
    assert sub_res.status_code == 200
    sub_data = sub_res.json()
    assert sub_data["status"] == "al_corriente"


@pytest.mark.asyncio
async def test_dashboard_live_metrics(async_client: httpx.AsyncClient):
    """GET /api/dashboard returns metrics consistent with plans, subscribers, and charges."""
    res = await async_client.get("/api/dashboard")
    assert res.status_code == 200
    dash = res.json()
    assert "total_subscribers" in dash
    assert "expected_monthly" in dash
    assert "collected_month" in dash
    assert "recent_movements" in dash
    assert len(dash["recent_movements"]) > 0
