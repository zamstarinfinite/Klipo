import math
import os
import re
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.db import (
    advance_due_date,
    advance_subscriber_recurrence,
    calculate_subscriber_status,
    get_connection,
    init_db,
    parse_date,
)
from backend.pey_client import (
    PeyAPIError,
    PeyAuthError,
    PeyConnectionError,
    check_credentials,
    create_codi_qr,
    create_payment_link,
    get_codi_qr_transactions,
    get_payment_link_status,
)
from backend.schemas import (
    ChargeCreate,
    ChargeResponse,
    DashboardResponse,
    PlanCreate,
    PlanResponse,
    PlanUpdate,
    SubscriberCreate,
    SubscriberResponse,
    SubscriberUpdate,
)
from backend.seed import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema and seed with default demo & business data if empty
    init_db()
    seed_if_empty()
    yield


app = FastAPI(
    title="Klipo API",
    description="Mobile-first PWA subscription and payment management API for Klipo",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handles request validation errors and sanitizes non-JSON float values (NaN, Infinity)
    in the validation error details to prevent JSON serialization crashes (HTTP 500).
    """
    def sanitize(obj):
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [sanitize(v) for v in obj]
        return obj

    clean_errors = sanitize(jsonable_encoder(exc.errors()))
    return JSONResponse(status_code=422, content={"detail": clean_errors})


def get_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def format_relative_when(dt_str: Optional[str]) -> str:
    """Format an ISO datetime into a friendly label like 'Hoy, 10:45 AM' or '28 oct'."""
    if not dt_str:
        return ""
    try:
        # Handle string with or without timezone
        clean_str = dt_str.replace("Z", "")
        dt = datetime.fromisoformat(clean_str)
        today = date.today()
        if dt.date() == today:
            return f"Hoy, {dt.strftime('%I:%M %p').lstrip('0')}"
        elif (today - dt.date()).days == 1:
            return f"Ayer, {dt.strftime('%I:%M %p').lstrip('0')}"
        else:
            months = [
                "ene", "feb", "mar", "abr", "may", "jun",
                "jul", "ago", "sep", "oct", "nov", "dic"
            ]
            return f"{dt.day} {months[dt.month - 1]}"
    except Exception:
        return dt_str


# ---------------------------------------------------------------------------
# Health Check Endpoint
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health_check(conn=Depends(get_db)):
    """Verifies SQLite database connectivity AND live Pey API credentials."""
    db_ok = False
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        cursor.fetchone()
        db_ok = True
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database check failed: {str(e)}",
        )

    try:
        await check_credentials()
        return {
            "status": "ok",
            "database": "connected",
            "pey_api": "authenticated",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "error",
                "database": "connected" if db_ok else "error",
                "pey_api": f"unauthenticated: {str(e)}",
            },
        )


# ---------------------------------------------------------------------------
# Dashboard Endpoint
# ---------------------------------------------------------------------------
@app.get("/api/dashboard", response_model=DashboardResponse)
def get_dashboard(conn=Depends(get_db)):
    """
    Returns dashboard summary metrics:
    - total subscribers & active subscribers
    - count of overdue (atrasado), due soon (por_vencer), and current (al_corriente)
    - expected monthly revenue
    - collected revenue this month
    - recent movements (charges)
    """
    cursor = conn.cursor()

    # Fetch active subscribers and their plan prices
    cursor.execute("""
        SELECT s.id, s.next_due_date, s.is_active, p.price, p.interval
        FROM subscribers s
        JOIN plans p ON s.plan_id = p.id
        WHERE s.is_active = 1;
    """)
    active_subs = cursor.fetchall()

    total_subscribers = len(active_subs)
    active_count = len(active_subs)
    overdue_count = 0
    due_soon_count = 0
    current_count = 0
    expected_monthly = 0.0

    today = date.today()
    for sub in active_subs:
        st = calculate_subscriber_status(sub["next_due_date"], reference_date=today)
        if st == "atrasado":
            overdue_count += 1
        elif st == "por_vencer":
            due_soon_count += 1
        else:
            current_count += 1

        price = float(sub["price"])
        interval = (sub["interval"] or "monthly").lower()
        if interval == "weekly":
            expected_monthly += price * 4.33
        elif interval == "biweekly":
            expected_monthly += price * 2.0
        else:
            expected_monthly += price

    expected_monthly = round(expected_monthly, 2)

    # Calculate collected this month: paid charges where paid_at is in current month
    current_month_prefix = today.strftime("%Y-%m")
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0.0) as collected
        FROM charges
        WHERE status = 'paid'
          AND (paid_at LIKE ? OR (paid_at IS NULL AND created_at LIKE ?));
    """, (f"{current_month_prefix}%", f"{current_month_prefix}%"))
    collected_row = cursor.fetchone()
    collected_month = round(float(collected_row["collected"]), 2)

    # Fetch recent movements
    cursor.execute("""
        SELECT c.*, s.name as subscriber_name, p.name as plan_name
        FROM charges c
        LEFT JOIN subscribers s ON c.subscriber_id = s.id
        LEFT JOIN plans p ON c.plan_id = p.id
        ORDER BY c.created_at DESC
        LIMIT 10;
    """)
    charges_rows = cursor.fetchall()
    recent_movements = []
    for r in charges_rows:
        recent_movements.append(
            ChargeResponse(
                id=r["id"],
                subscriber_id=r["subscriber_id"],
                subscriberId=r["subscriber_id"],
                subscriber_name=r["subscriber_name"],
                plan_id=r["plan_id"],
                planId=r["plan_id"],
                plan_name=r["plan_name"],
                amount=float(r["amount"]),
                concept=r["concept"],
                method=r["method"],
                status=r["status"],
                codi_qr_id=r["codi_qr_id"],
                qr_payload=r["qr_payload"],
                qr_image=r["qr_image"],
                payment_link_id=r["payment_link_id"],
                payment_link_url=r["payment_link_url"],
                pey_transaction_id=r["pey_transaction_id"],
                num_ref=r["num_ref"],
                created_at=r["created_at"],
                paid_at=r["paid_at"],
                when=format_relative_when(r["paid_at"] or r["created_at"]),
            )
        )

    return DashboardResponse(
        total_subscribers=total_subscribers,
        active_subscribers=active_count,
        overdue_count=overdue_count,
        due_soon_count=due_soon_count,
        current_count=current_count,
        expected_monthly=expected_monthly,
        collected_month=collected_month,
        recent_movements=recent_movements,
    )


# ---------------------------------------------------------------------------
# Plans Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/plans", response_model=List[PlanResponse])
def get_plans(conn=Depends(get_db)):
    """Returns list of all plans along with subscriber metrics."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM plans ORDER BY price ASC;")
    plans_rows = cursor.fetchall()

    today = date.today()
    current_month_prefix = today.strftime("%Y-%m")

    result = []
    for p in plans_rows:
        plan_id = p["id"]
        # Subscribers for this plan
        cursor.execute("""
            SELECT id, next_due_date
            FROM subscribers
            WHERE plan_id = ? AND is_active = 1;
        """, (plan_id,))
        subs = cursor.fetchall()
        active_subscribers = len(subs)

        late_count = sum(
            1 for s in subs
            if calculate_subscriber_status(s["next_due_date"], reference_date=today) == "atrasado"
        )

        expected = round(active_subscribers * float(p["price"]), 2)

        # Collected this month
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0.0) as col
            FROM charges
            WHERE plan_id = ? AND status = 'paid'
              AND (paid_at LIKE ? OR (paid_at IS NULL AND created_at LIKE ?));
        """, (plan_id, f"{current_month_prefix}%", f"{current_month_prefix}%"))
        collected = round(float(cursor.fetchone()["col"]), 2)

        # Pending this month
        pending = max(0.0, round(expected - collected, 2))

        result.append(
            PlanResponse(
                id=p["id"],
                name=p["name"],
                price=float(p["price"]),
                interval=p["interval"],
                description=p["description"],
                icon=p["icon"],
                charge_day=int(p["charge_day"]),
                chargeDay=int(p["charge_day"]),
                is_active=bool(p["is_active"]),
                created_at=p["created_at"],
                active_subscribers=active_subscribers,
                expected=expected,
                collected=collected,
                pending=pending,
                late_count=late_count,
            )
        )

    return result


@app.get("/api/plans/{plan_id}", response_model=PlanResponse)
def get_plan(plan_id: str, conn=Depends(get_db)):
    """Returns single plan details with computed statistics."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM plans WHERE id = ?;", (plan_id,))
    p = cursor.fetchone()
    if not p:
        raise HTTPException(status_code=404, detail="Plan not found")

    today = date.today()
    current_month_prefix = today.strftime("%Y-%m")

    cursor.execute("""
        SELECT id, next_due_date FROM subscribers WHERE plan_id = ? AND is_active = 1;
    """, (plan_id,))
    subs = cursor.fetchall()
    active_subscribers = len(subs)
    late_count = sum(
        1 for s in subs
        if calculate_subscriber_status(s["next_due_date"], reference_date=today) == "atrasado"
    )
    expected = round(active_subscribers * float(p["price"]), 2)

    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0.0) as col
        FROM charges
        WHERE plan_id = ? AND status = 'paid'
          AND (paid_at LIKE ? OR (paid_at IS NULL AND created_at LIKE ?));
    """, (plan_id, f"{current_month_prefix}%", f"{current_month_prefix}%"))
    collected = round(float(cursor.fetchone()["col"]), 2)
    pending = max(0.0, round(expected - collected, 2))

    return PlanResponse(
        id=p["id"],
        name=p["name"],
        price=float(p["price"]),
        interval=p["interval"],
        description=p["description"],
        icon=p["icon"],
        charge_day=int(p["charge_day"]),
        chargeDay=int(p["charge_day"]),
        is_active=bool(p["is_active"]),
        created_at=p["created_at"],
        active_subscribers=active_subscribers,
        expected=expected,
        collected=collected,
        pending=pending,
        late_count=late_count,
    )


@app.post("/api/plans", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
def create_plan(plan_in: PlanCreate, conn=Depends(get_db)):
    """Creates a new plan (or updates if existing ID provided)."""
    cursor = conn.cursor()
    plan_id = plan_in.id or re.sub(r"[^a-zA-Z0-9_-]", "", plan_in.name.lower().replace(" ", "-")) or uuid.uuid4().hex[:8]
    now = datetime.now().isoformat()

    cursor.execute("SELECT id FROM plans WHERE id = ?;", (plan_id,))
    existing = cursor.fetchone()

    with conn:
        if existing:
            cursor.execute("""
                UPDATE plans
                SET name = ?, price = ?, interval = ?, description = ?, icon = ?, charge_day = ?, is_active = ?
                WHERE id = ?;
            """, (
                plan_in.name,
                plan_in.price,
                plan_in.interval,
                plan_in.description,
                plan_in.icon,
                plan_in.charge_day,
                1 if plan_in.is_active else 0,
                plan_id,
            ))
        else:
            cursor.execute("""
                INSERT INTO plans (id, name, price, interval, description, icon, charge_day, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                plan_id,
                plan_in.name,
                plan_in.price,
                plan_in.interval,
                plan_in.description,
                plan_in.icon,
                plan_in.charge_day,
                1 if plan_in.is_active else 0,
                now,
            ))

    return get_plan(plan_id, conn)


@app.patch("/api/plans/{plan_id}", response_model=PlanResponse)
def update_plan(plan_id: str, plan_update: PlanUpdate, conn=Depends(get_db)):
    """Updates fields of an existing plan."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM plans WHERE id = ?;", (plan_id,))
    existing = cursor.fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Plan not found")

    fields = []
    values = []
    data = plan_update.model_dump(exclude_unset=True)
    for k, v in data.items():
        if k == "is_active":
            fields.append("is_active = ?")
            values.append(1 if v else 0)
        elif k in ["name", "price", "interval", "description", "icon", "charge_day"]:
            fields.append(f"{k} = ?")
            values.append(v)

    if fields:
        values.append(plan_id)
        with conn:
            cursor.execute(f"UPDATE plans SET {', '.join(fields)} WHERE id = ?;", values)

    return get_plan(plan_id, conn)


# ---------------------------------------------------------------------------
# Subscribers Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/subscribers", response_model=List[SubscriberResponse])
def get_subscribers(
    status: Optional[str] = Query(None, description="'atrasado', 'por_vencer', or 'al_corriente'"),
    plan_id: Optional[str] = Query(None, description="Filter by plan ID"),
    search: Optional[str] = Query(None, description="Search by name or phone"),
    conn=Depends(get_db),
):
    """
    Returns list of subscribers with dynamically computed status.
    Supports filtering by status, plan_id, and search keyword.
    """
    cursor = conn.cursor()
    query = """
        SELECT s.*, p.name as plan_name
        FROM subscribers s
        LEFT JOIN plans p ON s.plan_id = p.id
        WHERE 1 = 1
    """
    params = []

    if plan_id:
        query += " AND s.plan_id = ?"
        params.append(plan_id)

    query += " ORDER BY s.name ASC;"
    cursor.execute(query, params)
    rows = cursor.fetchall()

    today = date.today()
    results = []

    for r in rows:
        computed_status = calculate_subscriber_status(r["next_due_date"], reference_date=today)
        if status and computed_status != status:
            continue

        if search:
            q = search.lower()
            if q not in r["name"].lower() and q not in r["phone"]:
                continue

        results.append(
            SubscriberResponse(
                id=r["id"],
                plan_id=r["plan_id"],
                planId=r["plan_id"],
                name=r["name"],
                phone=r["phone"],
                start_date=r["start_date"],
                next_due_date=r["next_due_date"],
                last_paid_at=r["last_paid_at"],
                note=r["note"],
                is_active=bool(r["is_active"]),
                created_at=r["created_at"],
                status=computed_status,
                plan_name=r["plan_name"],
            )
        )

    return results


@app.get("/api/subscribers/{subscriber_id}", response_model=SubscriberResponse)
def get_subscriber(subscriber_id: str, conn=Depends(get_db)):
    """Returns details of a specific subscriber."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.*, p.name as plan_name
        FROM subscribers s
        LEFT JOIN plans p ON s.plan_id = p.id
        WHERE s.id = ?;
    """, (subscriber_id,))
    r = cursor.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    computed_status = calculate_subscriber_status(r["next_due_date"])
    return SubscriberResponse(
        id=r["id"],
        plan_id=r["plan_id"],
        planId=r["plan_id"],
        name=r["name"],
        phone=r["phone"],
        start_date=r["start_date"],
        next_due_date=r["next_due_date"],
        last_paid_at=r["last_paid_at"],
        note=r["note"],
        is_active=bool(r["is_active"]),
        created_at=r["created_at"],
        status=computed_status,
        plan_name=r["plan_name"],
    )


@app.post("/api/subscribers", response_model=SubscriberResponse, status_code=status.HTTP_201_CREATED)
def create_subscriber(sub_in: SubscriberCreate, conn=Depends(get_db)):
    """
    Creates a new subscriber.
    Computes initial next_due_date based on plan interval if not explicitly provided.
    """
    cursor = conn.cursor()

    # Validate plan exists
    cursor.execute("SELECT id, name, interval, price FROM plans WHERE id = ?;", (sub_in.plan_id,))
    plan = cursor.fetchone()
    if not plan:
        raise HTTPException(status_code=400, detail=f"Plan '{sub_in.plan_id}' does not exist")

    today = date.today()
    if sub_in.id:
        sub_id = sub_in.id
        cursor.execute("SELECT id FROM subscribers WHERE id = ?;", (sub_id,))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail=f"Subscriber with ID '{sub_id}' already exists")
    else:
        slug = re.sub(r"[^a-zA-Z0-9_-]", "", sub_in.name.lower().replace(" ", "_")) or uuid.uuid4().hex[:8]
        cursor.execute("SELECT id FROM subscribers WHERE id = ?;", (slug,))
        if cursor.fetchone():
            sub_id = f"{slug}_{uuid.uuid4().hex[:6]}"
        else:
            sub_id = slug
    start_date = sub_in.start_date or today.isoformat()
    next_due_date = sub_in.next_due_date or advance_due_date(start_date, plan["interval"])
    now = datetime.now().isoformat()
    note = sub_in.note or f"Nuevo suscriptor {plan['name']}"

    try:
        with conn:
            cursor.execute("""
                INSERT INTO subscribers (id, plan_id, name, phone, start_date, next_due_date, note, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?);
            """, (
                sub_id,
                sub_in.plan_id,
                sub_in.name,
                sub_in.phone,
                start_date,
                next_due_date,
                note,
                now,
            ))

            # If instant charge requested, create pending charge record
            if sub_in.instant_charge:
                charge_id = f"c_{uuid.uuid4().hex[:8]}"
                cursor.execute("""
                    INSERT INTO charges (id, subscriber_id, plan_id, amount, concept, method, status, created_at)
                    VALUES (?, ?, ?, ?, ?, 'codi', 'pending', ?);
                """, (
                    charge_id,
                    sub_id,
                    sub_in.plan_id,
                    float(plan["price"]),
                    f"Cobro inicial {plan['name']}",
                    now,
                ))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Subscriber conflict: {exc}",
        )

    return get_subscriber(sub_id, conn)


@app.patch("/api/subscribers/{subscriber_id}", response_model=SubscriberResponse)
def update_subscriber(subscriber_id: str, sub_update: SubscriberUpdate, conn=Depends(get_db)):
    """Updates fields of an existing subscriber."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subscribers WHERE id = ?;", (subscriber_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Subscriber not found")

    fields = []
    values = []
    data = sub_update.model_dump(exclude_unset=True)
    for k, v in data.items():
        if k == "is_active":
            fields.append("is_active = ?")
            values.append(1 if v else 0)
        elif k in ["name", "phone", "plan_id", "next_due_date", "note"]:
            fields.append(f"{k} = ?")
            values.append(v)

    if fields:
        values.append(subscriber_id)
        with conn:
            cursor.execute(f"UPDATE subscribers SET {', '.join(fields)} WHERE id = ?;", values)

    return get_subscriber(subscriber_id, conn)


# ---------------------------------------------------------------------------
# Charges Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/charges", response_model=List[ChargeResponse])
def get_charges(
    subscriber_id: Optional[str] = Query(None, description="Filter by subscriber ID"),
    plan_id: Optional[str] = Query(None, description="Filter by plan ID"),
    status: Optional[str] = Query(None, description="Filter by status ('paid', 'pending', etc.)"),
    conn=Depends(get_db),
):
    """Returns charge movements history, ordered newest first."""
    cursor = conn.cursor()
    query = """
        SELECT c.*, s.name as subscriber_name, p.name as plan_name
        FROM charges c
        LEFT JOIN subscribers s ON c.subscriber_id = s.id
        LEFT JOIN plans p ON c.plan_id = p.id
        WHERE 1 = 1
    """
    params = []

    if subscriber_id:
        query += " AND c.subscriber_id = ?"
        params.append(subscriber_id)
    if plan_id:
        query += " AND c.plan_id = ?"
        params.append(plan_id)
    if status:
        query += " AND c.status = ?"
        params.append(status)

    query += " ORDER BY c.created_at DESC;"
    cursor.execute(query, params)
    rows = cursor.fetchall()

    results = []
    for r in rows:
        results.append(
            ChargeResponse(
                id=r["id"],
                subscriber_id=r["subscriber_id"],
                subscriberId=r["subscriber_id"],
                subscriber_name=r["subscriber_name"],
                plan_id=r["plan_id"],
                planId=r["plan_id"],
                plan_name=r["plan_name"],
                amount=float(r["amount"]),
                concept=r["concept"],
                method=r["method"],
                status=r["status"],
                codi_qr_id=r["codi_qr_id"],
                qr_payload=r["qr_payload"],
                qr_image=r["qr_image"],
                payment_link_id=r["payment_link_id"],
                payment_link_url=r["payment_link_url"],
                pey_transaction_id=r["pey_transaction_id"],
                num_ref=r["num_ref"],
                created_at=r["created_at"],
                paid_at=r["paid_at"],
                when=format_relative_when(r["paid_at"] or r["created_at"]),
            )
        )

    return results


def mark_charge_as_paid(
    charge_id: str,
    conn,
    method: Optional[str] = None,
    pey_transaction_id: Optional[str] = None,
) -> Optional[dict]:
    """
    Transitions charge to 'paid' status idempotently.
    Updates paid_at and method.
    If the charge transitioned from non-paid to paid, calls advance_subscriber_recurrence.
    Returns the refreshed charge row dict.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, s.name as subscriber_name, p.name as plan_name, s.next_due_date as sub_due_date
        FROM charges c
        JOIN subscribers s ON c.subscriber_id = s.id
        JOIN plans p ON c.plan_id = p.id
        WHERE c.id = ?;
    """, (charge_id,))
    charge = cursor.fetchone()
    if not charge:
        return None

    if charge["status"] != "paid":
        now_iso = datetime.now().isoformat()
        fields = ["status = 'paid'", "paid_at = ?"]
        params = [now_iso]
        if method:
            fields.append("method = ?")
            params.append(method)
        if pey_transaction_id:
            fields.append("pey_transaction_id = ?")
            params.append(pey_transaction_id)
        params.append(charge_id)

        with conn:
            cursor.execute(f"""
                UPDATE charges
                SET {', '.join(fields)}
                WHERE id = ? AND status != 'paid';
            """, params)

            if cursor.rowcount > 0:
                advance_subscriber_recurrence(charge["subscriber_id"], charge["plan_id"], conn=conn)

    cursor.execute("""
        SELECT c.*, s.name as subscriber_name, p.name as plan_name, s.next_due_date, s.last_paid_at
        FROM charges c
        JOIN subscribers s ON c.subscriber_id = s.id
        JOIN plans p ON c.plan_id = p.id
        WHERE c.id = ?;
    """, (charge_id,))
    return cursor.fetchone()


@app.post("/api/charges", response_model=ChargeResponse, status_code=status.HTTP_201_CREATED)
async def create_charge(charge_in: ChargeCreate, conn=Depends(get_db)):
    """
    Creates a new charge record in SQLite with live CoDi QR and Payment Link from Pey API.
    """
    cursor = conn.cursor()

    # Look up subscriber
    cursor.execute("""
        SELECT s.*, p.price as plan_price, p.name as plan_name
        FROM subscribers s
        JOIN plans p ON s.plan_id = p.id
        WHERE s.id = ?;
    """, (charge_in.subscriber_id,))
    sub = cursor.fetchone()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    plan_id = charge_in.plan_id or sub["plan_id"]
    amount = charge_in.amount if charge_in.amount is not None else float(sub["plan_price"])
    concept = charge_in.concept or f"Cobro {sub['plan_name']}"
    method = charge_in.method or "codi"
    charge_id = f"c_{uuid.uuid4().hex[:10]}"
    now = datetime.now().isoformat()

    # Compute valid numRef (1-7 digits numeric)
    num_ref = str(uuid.uuid4().int % 9000000 + 1000000)

    codi_qr_id = None
    qr_payload = None
    qr_image = None
    payment_link_id = None
    payment_link_url = None

    if method != "efectivo":
        try:
            qr_data = await create_codi_qr(
                amount=amount,
                concept=concept,
                num_ref=num_ref,
                expiration=0,
                generate_image=True,
            )
            codi_qr_id = qr_data.get("id")
            qr_payload = qr_data.get("qrString")
            qr_image = qr_data.get("qrImage")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to generate CoDi QR via Pey API: {str(e)}",
            )

        try:
            link_data = await create_payment_link(
                amount=amount,
                client_reference_id=charge_id,
            )
            payment_link_id = link_data.get("id")
            payment_link_url = link_data.get("url")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to generate Payment Link via Pey API: {str(e)}",
            )

    initial_status = "paid" if method == "efectivo" else "pending"
    paid_at = now if method == "efectivo" else None

    with conn:
        cursor.execute("""
            INSERT INTO charges (
                id, subscriber_id, plan_id, amount, concept, method, status,
                codi_qr_id, qr_payload, qr_image, payment_link_id, payment_link_url,
                num_ref, created_at, paid_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            charge_id,
            charge_in.subscriber_id,
            plan_id,
            amount,
            concept,
            method,
            initial_status,
            codi_qr_id,
            qr_payload,
            qr_image,
            payment_link_id,
            payment_link_url,
            num_ref,
            now,
            paid_at,
        ))

        if method == "efectivo":
            advance_subscriber_recurrence(charge_in.subscriber_id, plan_id, conn=conn)

    cursor.execute("SELECT next_due_date FROM subscribers WHERE id = ?;", (charge_in.subscriber_id,))
    sub_row = cursor.fetchone()
    next_due = sub_row["next_due_date"] if sub_row else sub["next_due_date"]
    sub_status = calculate_subscriber_status(next_due)

    return ChargeResponse(
        id=charge_id,
        subscriber_id=charge_in.subscriber_id,
        subscriberId=charge_in.subscriber_id,
        subscriber_name=sub["name"],
        plan_id=plan_id,
        planId=plan_id,
        plan_name=sub["plan_name"],
        amount=amount,
        concept=concept,
        method=method,
        status=initial_status,
        codi_qr_id=codi_qr_id,
        qr_payload=qr_payload,
        qr_image=qr_image,
        payment_link_id=payment_link_id,
        payment_link_url=payment_link_url,
        num_ref=num_ref,
        created_at=now,
        paid_at=paid_at,
        when=format_relative_when(paid_at or now),
        subscriber_next_due_date=next_due,
        subscriber_status=sub_status,
    )


@app.get("/api/charges/{charge_id}", response_model=ChargeResponse)
def get_charge(charge_id: str, conn=Depends(get_db)):
    """Returns single charge details."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, s.name as subscriber_name, p.name as plan_name, s.next_due_date
        FROM charges c
        LEFT JOIN subscribers s ON c.subscriber_id = s.id
        LEFT JOIN plans p ON c.plan_id = p.id
        WHERE c.id = ?;
    """, (charge_id,))
    r = cursor.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Charge not found")

    next_due = r["next_due_date"] or ""
    sub_status = calculate_subscriber_status(next_due) if next_due else ""

    return ChargeResponse(
        id=r["id"],
        subscriber_id=r["subscriber_id"],
        subscriberId=r["subscriber_id"],
        subscriber_name=r["subscriber_name"],
        plan_id=r["plan_id"],
        planId=r["plan_id"],
        plan_name=r["plan_name"],
        amount=float(r["amount"]),
        concept=r["concept"],
        method=r["method"],
        status=r["status"],
        codi_qr_id=r["codi_qr_id"],
        qr_payload=r["qr_payload"],
        qr_image=r["qr_image"],
        payment_link_id=r["payment_link_id"],
        payment_link_url=r["payment_link_url"],
        pey_transaction_id=r["pey_transaction_id"],
        num_ref=r["num_ref"],
        created_at=r["created_at"],
        paid_at=r["paid_at"],
        when=format_relative_when(r["paid_at"] or r["created_at"]),
        subscriber_next_due_date=next_due,
        subscriber_status=sub_status,
    )


@app.get("/api/charges/{charge_id}/status")
async def get_charge_status(charge_id: str, conn=Depends(get_db)):
    """
    Polls Pey API (CoDi QR transactions and Payment Link status) for payment status.
    If payment is confirmed:
    - Transitions charge status to 'paid'
    - Updates paid_at timestamp
    - Idempotently advances subscriber recurrence (next_due_date and last_paid_at)
    Returns updated charge status and subscriber info.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, s.name as subscriber_name, p.name as plan_name, s.next_due_date, s.last_paid_at
        FROM charges c
        JOIN subscribers s ON c.subscriber_id = s.id
        JOIN plans p ON c.plan_id = p.id
        WHERE c.id = ?;
    """, (charge_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Charge not found")

    if row["status"] != "paid":
        is_paid = False
        pey_tx_id = None

        # Check CoDi QR transactions
        if row["codi_qr_id"]:
            try:
                tx_data = await get_codi_qr_transactions(row["codi_qr_id"])
                items = tx_data.get("items", [])
                paid_items = [it for it in items if str(it.get("status", "")).upper() == "PAID"]
                if paid_items:
                    is_paid = True
                    pey_tx_id = paid_items[0].get("transactionId")
            except Exception:
                pass

        # If not paid via CoDi QR, check Payment Link status
        if not is_paid and row["payment_link_id"]:
            try:
                link_data = await get_payment_link_status(row["payment_link_id"])
                if str(link_data.get("status", "")).lower() == "paid":
                    is_paid = True
            except Exception:
                pass

        if is_paid:
            mark_charge_as_paid(charge_id, conn, method="codi", pey_transaction_id=pey_tx_id)
            cursor.execute("""
                SELECT c.*, s.name as subscriber_name, p.name as plan_name, s.next_due_date, s.last_paid_at
                FROM charges c
                JOIN subscribers s ON c.subscriber_id = s.id
                JOIN plans p ON c.plan_id = p.id
                WHERE c.id = ?;
            """, (charge_id,))
            row = cursor.fetchone()

    sub_status = calculate_subscriber_status(row["next_due_date"])
    charge_resp = ChargeResponse(
        id=row["id"],
        subscriber_id=row["subscriber_id"],
        subscriberId=row["subscriber_id"],
        subscriber_name=row["subscriber_name"],
        plan_id=row["plan_id"],
        planId=row["plan_id"],
        plan_name=row["plan_name"],
        amount=float(row["amount"]),
        concept=row["concept"],
        method=row["method"],
        status=row["status"],
        codi_qr_id=row["codi_qr_id"],
        qr_payload=row["qr_payload"],
        qr_image=row["qr_image"],
        payment_link_id=row["payment_link_id"],
        payment_link_url=row["payment_link_url"],
        pey_transaction_id=row["pey_transaction_id"],
        num_ref=row["num_ref"],
        created_at=row["created_at"],
        paid_at=row["paid_at"],
        when=format_relative_when(row["paid_at"] or row["created_at"]),
        subscriber_next_due_date=row["next_due_date"],
        subscriber_status=sub_status,
    )
    result = charge_resp.model_dump()
    result["pagado"] = (row["status"] == "paid")
    return result


@app.post("/api/webhooks/pey")
async def pey_webhook(request: Request, conn=Depends(get_db)):
    """
    Receives webhook notifications from Pey for:
    - 'codi.qr.payment_received'
    - 'payment_link.status_updated'
    Finds charge by codi_qr_id, payment_link_id, or clientReferenceId.
    Idempotently transitions charge to 'paid', updates paid_at, and advances subscriber recurrence.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"error": "Webhook payload must be a JSON object"})

    event_type = body.get("type", "")
    codi_qr_id = body.get("codiQrId") or body.get("codi_qr_id")
    payment_link_id = body.get("paymentLinkId") or body.get("payment_link_id")
    client_ref = body.get("clientReferenceId") or body.get("client_reference_id")
    status_val = str(body.get("status", "")).lower()
    tx_id = body.get("transactionId") or body.get("transaction_id")

    cursor = conn.cursor()
    charge = None

    if codi_qr_id:
        cursor.execute("SELECT id FROM charges WHERE codi_qr_id = ?;", (codi_qr_id,))
        charge = cursor.fetchone()

    if not charge and payment_link_id:
        cursor.execute("SELECT id FROM charges WHERE payment_link_id = ?;", (payment_link_id,))
        charge = cursor.fetchone()

    if not charge and client_ref:
        cursor.execute("SELECT id FROM charges WHERE id = ?;", (client_ref,))
        charge = cursor.fetchone()

    if not charge:
        return {"status": "processed", "warning": "Charge not found"}

    charge_id = charge["id"]

    should_mark_paid = False
    if event_type == "codi.qr.payment_received":
        should_mark_paid = True
    elif event_type == "payment_link.status_updated" and status_val == "paid":
        should_mark_paid = True
    elif status_val == "paid":
        should_mark_paid = True

    if should_mark_paid:
        mark_charge_as_paid(charge_id, conn, method="codi", pey_transaction_id=tx_id)

    return {"status": "processed"}


@app.post("/api/charges/{charge_id}/mark-cash", response_model=ChargeResponse)
def mark_charge_cash(charge_id: str, conn=Depends(get_db)):
    """
    Manually marks charge as paid with method = 'efectivo',
    updates paid_at, and advances subscriber recurrence.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM charges WHERE id = ?;", (charge_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Charge not found")

    updated = mark_charge_as_paid(charge_id, conn, method="efectivo")
    if not updated:
        raise HTTPException(status_code=404, detail="Charge not found")

    sub_status = calculate_subscriber_status(updated["next_due_date"])
    return ChargeResponse(
        id=updated["id"],
        subscriber_id=updated["subscriber_id"],
        subscriberId=updated["subscriber_id"],
        subscriber_name=updated["subscriber_name"],
        plan_id=updated["plan_id"],
        planId=updated["plan_id"],
        plan_name=updated["plan_name"],
        amount=float(updated["amount"]),
        concept=updated["concept"],
        method=updated["method"],
        status=updated["status"],
        codi_qr_id=updated["codi_qr_id"],
        qr_payload=updated["qr_payload"],
        qr_image=updated["qr_image"],
        payment_link_id=updated["payment_link_id"],
        payment_link_url=updated["payment_link_url"],
        pey_transaction_id=updated["pey_transaction_id"],
        num_ref=updated["num_ref"],
        created_at=updated["created_at"],
        paid_at=updated["paid_at"],
        when=format_relative_when(updated["paid_at"] or updated["created_at"]),
        subscriber_next_due_date=updated["next_due_date"],
        subscriber_status=sub_status,
    )


# ---------------------------------------------------------------------------
# Static Mounting & SPA Fallback
# ---------------------------------------------------------------------------
def setup_frontend_mounting(app: FastAPI):
    """Mounts frontend dist static files if present, else provides informative root."""
    frontend_dist = os.getenv("FRONTEND_DIST")
    if not frontend_dist:
        candidates = [
            os.path.join(os.getcwd(), "frontend", "dist"),
            os.path.join(os.getcwd(), "frontend", "Mejorar flujo de suscripciones", "dist"),
        ]
        for c in candidates:
            if os.path.isdir(c):
                frontend_dist = c
                break

    if frontend_dist and os.path.isdir(frontend_dist):
        assets_dir = os.path.join(frontend_dist, "assets")
        if os.path.isdir(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="API route not found")
            dist_root = os.path.realpath(frontend_dist)
            resolved_path = os.path.realpath(os.path.join(frontend_dist, full_path))
            if full_path and resolved_path.startswith(dist_root + os.sep) and os.path.isfile(resolved_path):
                return FileResponse(resolved_path)
            index_path = os.path.join(frontend_dist, "index.html")
            if os.path.isfile(index_path):
                return FileResponse(index_path)
            return JSONResponse(
                status_code=404,
                content={"detail": "Index file not found in frontend dist"},
            )
    else:
        @app.get("/")
        async def root():
            return {
                "status": "ok",
                "app": "Klipo PWA Backend",
                "version": "1.0.0",
                "docs": "/docs",
                "message": "Frontend dist not mounted. API is running standalone.",
            }


setup_frontend_mounting(app)
