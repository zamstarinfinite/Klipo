"""
Tier 2 Boundary: Dates & Intervals Month-End Transitions
Tests Jan 31 -> Feb 28 clamping, leap year Feb 29 clamping, and weekly/biweekly cross-month transitions.
"""

from backend.db import advance_due_date


def test_bva_11_monthly_advance_jan31_to_feb28():
    """Verifies that monthly recurrence on Jan 31 clamps to Feb 28 in a non-leap year (e.g. 2026)."""
    result = advance_due_date("2026-01-31", "monthly")
    assert result == "2026-02-28", f"Expected month-end clamp 2026-02-28, got: {result}"


def test_bva_12_monthly_advance_jan31_leap_year_to_feb29():
    """Verifies that monthly recurrence on Jan 31 clamps to Feb 29 in a leap year (e.g. 2028)."""
    result = advance_due_date("2028-01-31", "monthly")
    assert result == "2028-02-29", f"Expected leap day clamp 2028-02-29, got: {result}"


def test_bva_13_weekly_advance_across_month_boundary():
    """Verifies that weekly (+7d) recurrence advances properly across month boundary (Nov 28 -> Dec 05)."""
    result = advance_due_date("2026-11-28", "weekly")
    assert result == "2026-12-05", f"Expected 2026-12-05, got: {result}"


def test_bva_14_biweekly_advance_across_month_boundary():
    """Verifies that biweekly (+15d) recurrence advances properly across month boundary (Nov 20 -> Dec 05)."""
    result = advance_due_date("2026-11-20", "biweekly")
    assert result == "2026-12-05", f"Expected 2026-12-05, got: {result}"


def test_bva_15_monthly_advance_march_to_april():
    """Verifies that monthly recurrence on March 31 clamps to April 30 (30-day month)."""
    result = advance_due_date("2026-03-31", "monthly")
    assert result == "2026-04-30", f"Expected 2026-04-30, got: {result}"
