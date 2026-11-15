import calendar
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import Generator, Optional, Union

DEFAULT_DB_PATH = "klipo.db"


def get_db_path() -> str:
    """Return database file path from DATABASE_PATH environment variable or default."""
    return os.getenv("DATABASE_PATH", DEFAULT_DB_PATH)


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Open SQLite connection with sqlite3.Row factory,
    foreign keys enabled, and WAL journal mode.
    """
    path = db_path or get_db_path()
    conn = sqlite3.connect(path, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
    except sqlite3.OperationalError:
        pass
    return conn


@contextmanager
def get_db(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite connection with automatic commit and rollback."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def parse_date(date_val: Union[str, date, datetime]) -> date:
    """Parse string or datetime object into a Python date."""
    if isinstance(date_val, datetime):
        return date_val.date()
    if isinstance(date_val, date):
        return date_val
    if isinstance(date_val, str):
        # Support ISO 8601 strings e.g. YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS
        clean_val = date_val.strip().split("T")[0].split(" ")[0].strip()
        return datetime.strptime(clean_val, "%Y-%m-%d").date()
    raise ValueError(f"Cannot parse date from {date_val}")


def calculate_subscriber_status(
    next_due_date: Union[str, date, datetime],
    reference_date: Optional[date] = None,
) -> str:
    """
    Computes dynamic subscriber status:
    - 'atrasado': next_due_date < today (diff < 0)
    - 'por_vencer': 0 <= diff <= 3 days
    - 'al_corriente': diff > 3 days
    """
    ref = reference_date or date.today()
    due = parse_date(next_due_date)
    diff = (due - ref).days

    if diff < 0:
        return "atrasado"
    elif diff <= 3:
        return "por_vencer"
    else:
        return "al_corriente"


def advance_due_date(
    current_due_date: Union[str, date, datetime],
    interval: str = "monthly",
) -> str:
    """
    Advances a due date according to plan interval:
    - 'weekly': +7 days
    - 'biweekly': +15 days
    - 'monthly': +1 month (same day next month or clamped to end of month)
    """
    due = parse_date(current_due_date)
    interval_clean = (interval or "monthly").lower().strip()

    if interval_clean == "weekly":
        new_due = due + timedelta(days=7)
    elif interval_clean == "biweekly":
        new_due = due + timedelta(days=15)
    else:  # monthly default
        year = due.year + (due.month // 12)
        month = (due.month % 12) + 1
        day = due.day
        max_day = calendar.monthrange(year, month)[1]
        new_due = date(year, month, min(day, max_day))

    return new_due.isoformat()


def advance_subscriber_recurrence(
    subscriber_id: str,
    plan_id: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> Optional[str]:
    """
    Advances subscriber's next_due_date based on plan interval:
    - weekly: +7 days
    - biweekly: +15 days
    - monthly: +1 month with month-end clamping (e.g., Jan 31 -> Feb 28/29)
    Updates last_paid_at to current timestamp.
    Guarantees subscriber status calculation becomes 'al_corriente'.
    Returns the new next_due_date string (YYYY-MM-DD).
    """
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.id, s.plan_id, s.next_due_date, p.interval
            FROM subscribers s
            LEFT JOIN plans p ON s.plan_id = p.id
            WHERE s.id = ?;
        """, (subscriber_id,))
        row = cursor.fetchone()
        if not row:
            return None

        # Determine interval from subscriber's plan or passed plan_id
        interval = row["interval"] or "monthly"
        if plan_id and plan_id != row["plan_id"]:
            cursor.execute("SELECT interval FROM plans WHERE id = ?;", (plan_id,))
            p_row = cursor.fetchone()
            if p_row and p_row["interval"]:
                interval = p_row["interval"]

        current_due = parse_date(row["next_due_date"])
        today = date.today()

        # If subscriber is overdue or due today/in the past, advance from today
        # so that diff > 3 days and the subscriber immediately transitions to 'al_corriente'
        base_date = max(current_due, today)
        new_due_date = advance_due_date(base_date, interval)
        now_iso = datetime.now().isoformat()

        cursor.execute("""
            UPDATE subscribers
            SET next_due_date = ?, last_paid_at = ?
            WHERE id = ?;
        """, (new_due_date, now_iso, subscriber_id))

        conn.commit()
        return new_due_date
    finally:
        if should_close:
            conn.close()


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database tables and indices."""
    path = db_path or get_db_path()
    conn = get_connection(path)
    try:
        with conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                interval TEXT NOT NULL DEFAULT 'monthly',
                description TEXT,
                icon TEXT NOT NULL DEFAULT 'wallet',
                charge_day INTEGER NOT NULL DEFAULT 1,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL REFERENCES plans(id),
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                start_date TEXT NOT NULL DEFAULT (date('now')),
                next_due_date TEXT NOT NULL,
                last_paid_at TEXT,
                note TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS charges (
                id TEXT PRIMARY KEY,
                subscriber_id TEXT NOT NULL REFERENCES subscribers(id),
                plan_id TEXT NOT NULL REFERENCES plans(id),
                amount REAL NOT NULL,
                concept TEXT NOT NULL DEFAULT '',
                method TEXT NOT NULL DEFAULT 'codi',
                status TEXT NOT NULL DEFAULT 'pending',
                codi_qr_id TEXT,
                qr_payload TEXT,
                qr_image TEXT,
                payment_link_id TEXT,
                payment_link_url TEXT,
                pey_transaction_id TEXT,
                num_ref TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                paid_at TEXT
            );
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_subscribers_plan_id ON subscribers(plan_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_charges_subscriber_id ON charges(subscriber_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_charges_status ON charges(status);")
    finally:
        conn.close()
