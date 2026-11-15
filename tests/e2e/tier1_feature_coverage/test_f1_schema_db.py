"""
Feature 1: SQLite Database Schema & Connection Management
Validates table schemas, WAL mode, foreign keys, column types, and indices.
"""

import sqlite3
import pytest


def test_f1_01_wal_mode_enabled(db_conn: sqlite3.Connection):
    """Verifies that WAL mode (Write-Ahead Logging) is active on SQLite connection."""
    cursor = db_conn.cursor()
    cursor.execute("PRAGMA journal_mode;")
    mode = cursor.fetchone()[0]
    assert mode.lower() == "wal", f"Expected WAL mode, got: {mode}"


def test_f1_02_foreign_keys_pragma_enabled(db_conn: sqlite3.Connection):
    """Verifies that foreign key enforcement is turned ON in SQLite."""
    cursor = db_conn.cursor()
    cursor.execute("PRAGMA foreign_keys;")
    fk = cursor.fetchone()[0]
    assert fk == 1, f"Expected foreign keys = 1 (enabled), got: {fk}"


def test_f1_03_plans_table_columns_and_types(db_conn: sqlite3.Connection):
    """Verifies table 'plans' schema contains all required fields, PK, and types."""
    cursor = db_conn.cursor()
    cursor.execute("PRAGMA table_info(plans);")
    columns = {row["name"]: row["type"].upper() for row in cursor.fetchall()}

    expected_columns = [
        "id",
        "name",
        "price",
        "interval",
        "description",
        "icon",
        "charge_day",
        "is_active",
        "created_at",
    ]
    for col in expected_columns:
        assert col in columns, f"Column '{col}' missing from 'plans' table"

    assert "REAL" in columns["price"] or "FLOAT" in columns["price"] or "NUMERIC" in columns["price"]


def test_f1_04_subscribers_table_schema_and_fks(db_conn: sqlite3.Connection):
    """Verifies 'subscribers' table schema and foreign key reference to 'plans'."""
    cursor = db_conn.cursor()
    cursor.execute("PRAGMA table_info(subscribers);")
    columns = {row["name"]: row["type"].upper() for row in cursor.fetchall()}

    expected_columns = [
        "id",
        "plan_id",
        "name",
        "phone",
        "start_date",
        "next_due_date",
        "last_paid_at",
        "note",
        "is_active",
        "created_at",
    ]
    for col in expected_columns:
        assert col in columns, f"Column '{col}' missing from 'subscribers' table"

    # Verify foreign key constraint
    cursor.execute("PRAGMA foreign_key_list(subscribers);")
    fk_list = cursor.fetchall()
    fk_tables = [row["table"] for row in fk_list]
    assert "plans" in fk_tables, "Foreign key from 'subscribers' to 'plans' not found"


def test_f1_05_charges_table_schema_and_fks(db_conn: sqlite3.Connection):
    """Verifies 'charges' table schema, columns, and foreign key references."""
    cursor = db_conn.cursor()
    cursor.execute("PRAGMA table_info(charges);")
    columns = {row["name"]: row["type"].upper() for row in cursor.fetchall()}

    expected_columns = [
        "id",
        "subscriber_id",
        "plan_id",
        "amount",
        "concept",
        "method",
        "status",
        "codi_qr_id",
        "qr_payload",
        "qr_image",
        "payment_link_id",
        "payment_link_url",
        "created_at",
        "paid_at",
    ]
    for col in expected_columns:
        assert col in columns, f"Column '{col}' missing from 'charges' table"

    cursor.execute("PRAGMA foreign_key_list(charges);")
    fk_list = cursor.fetchall()
    fk_tables = [row["table"] for row in fk_list]
    assert "subscribers" in fk_tables, "Foreign key from 'charges' to 'subscribers' not found"
    assert "plans" in fk_tables, "Foreign key from 'charges' to 'plans' not found"
