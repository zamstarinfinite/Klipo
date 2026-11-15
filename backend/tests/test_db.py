import os
import sqlite3
import tempfile
from datetime import date, datetime, timedelta

import pytest

from backend.db import (
    advance_due_date,
    advance_subscriber_recurrence,
    calculate_subscriber_status,
    get_connection,
    init_db,
    parse_date,
)
from backend.seed import seed_if_empty


def test_init_db_creates_tables_and_pragmas():
    """Verifies that init_db creates all required tables, pragmas, and indexes."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test_schema.db")
        init_db(db_path)

        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()

            # Verify foreign keys pragma
            cursor.execute("PRAGMA foreign_keys;")
            assert cursor.fetchone()[0] == 1

            # Verify tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {row[0] for row in cursor.fetchall()}
            assert "plans" in tables
            assert "subscribers" in tables
            assert "charges" in tables

            # Verify indexes exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
            indexes = {row[0] for row in cursor.fetchall()}
            assert "idx_subscribers_plan_id" in indexes
            assert "idx_charges_subscriber_id" in indexes
            assert "idx_charges_status" in indexes
        finally:
            conn.close()


def test_seed_if_empty_idempotency():
    """Verifies that seed_if_empty seeds only once and is strictly idempotent."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test_seeder.db")
        init_db(db_path)

        # First run on empty DB must return True
        first_run = seed_if_empty(db_path)
        assert first_run is True

        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM plans;")
            plan_count = cursor.fetchone()[0]
            assert plan_count >= 4

            cursor.execute("SELECT COUNT(*) FROM subscribers;")
            sub_count = cursor.fetchone()[0]
            assert sub_count >= 16

            cursor.execute("SELECT COUNT(*) FROM charges;")
            charge_count = cursor.fetchone()[0]
            assert charge_count >= 4
        finally:
            conn.close()

        # Second run on populated DB must return False and not duplicate records
        second_run = seed_if_empty(db_path)
        assert second_run is False

        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM plans;")
            assert cursor.fetchone()[0] == plan_count

            cursor.execute("SELECT COUNT(*) FROM subscribers;")
            assert cursor.fetchone()[0] == sub_count

            cursor.execute("SELECT COUNT(*) FROM charges;")
            assert cursor.fetchone()[0] == charge_count
        finally:
            conn.close()


def test_parse_date_formats():
    """Verifies parsing of various date representations."""
    # String YYYY-MM-DD
    assert parse_date("2026-11-15") == date(2026, 11, 15)
    # String ISO with T
    assert parse_date("2026-11-15T10:30:00") == date(2026, 11, 15)
    # Date object
    assert parse_date(date(2026, 11, 15)) == date(2026, 11, 15)
    # Datetime object
    assert parse_date(datetime(2026, 11, 15, 14, 0)) == date(2026, 11, 15)

    with pytest.raises(ValueError):
        parse_date(12345)


def test_calculate_subscriber_status_boundaries():
    """Verifies subscriber status categorization relative to reference date."""
    ref = date(2026, 11, 15)

    # Past due -> atrasado
    assert calculate_subscriber_status(date(2026, 11, 14), reference_date=ref) == "atrasado"
    assert calculate_subscriber_status("2026-10-31", reference_date=ref) == "atrasado"

    # Due today (0 days) -> por_vencer
    assert calculate_subscriber_status(date(2026, 11, 15), reference_date=ref) == "por_vencer"

    # Due in 1-3 days -> por_vencer
    assert calculate_subscriber_status(date(2026, 11, 16), reference_date=ref) == "por_vencer"
    assert calculate_subscriber_status(date(2026, 11, 18), reference_date=ref) == "por_vencer"

    # Due in 4+ days -> al_corriente
    assert calculate_subscriber_status(date(2026, 11, 19), reference_date=ref) == "al_corriente"
    assert calculate_subscriber_status(date(2026, 12, 15), reference_date=ref) == "al_corriente"


def test_advance_due_date_intervals():
    """Verifies advance_due_date logic for weekly, biweekly, and monthly intervals."""
    # Weekly: +7 days
    assert advance_due_date("2026-11-01", "weekly") == "2026-11-08"

    # Biweekly: +15 days
    assert advance_due_date("2026-11-01", "biweekly") == "2026-11-16"

    # Monthly regular
    assert advance_due_date("2026-05-10", "monthly") == "2026-06-10"

    # Monthly end of month clamping (Jan 31 -> Feb 28 in non-leap year)
    assert advance_due_date("2025-01-31", "monthly") == "2025-02-28"

    # Monthly end of month clamping (Jan 31 -> Feb 29 in leap year 2028)
    assert advance_due_date("2028-01-31", "monthly") == "2028-02-29"

    # Monthly year rollover (Dec -> Jan)
    assert advance_due_date("2026-12-15", "monthly") == "2027-01-15"
