"""Test suite verifying time conversions and timezone handling (UTC to PHT)."""

from datetime import datetime, timezone
from src.utils.time_utils import (
    PHT_TIMEZONE,
    format_iso_to_pht,
    get_utc_now_iso,
    is_session_past_midnight_pht,
)


def test_time_conversions():
    # ISO string UTC
    utc_now = get_utc_now_iso()
    assert utc_now is not None

    parsed_dt = datetime.fromisoformat(utc_now)
    assert parsed_dt.tzinfo == timezone.utc

    # PHT formatting
    pht_display = format_iso_to_pht(utc_now)
    assert pht_display != ""

    # Specific fixed time test (12:00:00 UTC == 20:00:00 PHT = 08:00:00 PM)
    fixed_utc = "2026-11-01T12:00:00Z"
    formatted = format_iso_to_pht(fixed_utc)
    assert "08:00:00 PM" in formatted
    formatted_full = format_iso_to_pht(fixed_utc, time_only=False)
    assert "2026-11-01 08:00:00 PM" in formatted_full
