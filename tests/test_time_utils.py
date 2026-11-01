from datetime import datetime, timezone, timedelta

from src.utils.time_utils import (
    PHT_TIMEZONE,
    format_iso_to_pht,
    format_utc_to_pht,
    get_utc_now_iso,
    is_session_past_midnight_pht,
)


def test_get_utc_now_iso_returns_timezone_aware_utc_timestamp():
    value = get_utc_now_iso()
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_format_iso_to_pht_converts_utc_to_philippine_time():
    # 00:00 UTC is 08:00 PHT on the same calendar date.
    assert format_iso_to_pht("2026-01-15T00:00:00+00:00") == "08:00:00 AM"


def test_format_iso_to_pht_treats_naive_timestamp_as_utc():
    assert format_iso_to_pht("2026-01-15T00:00:00") == "08:00:00 AM"


def test_format_iso_to_pht_supports_z_suffix_and_date_output():
    assert format_iso_to_pht("2026-01-15T00:00:00Z", time_only=False) == (
        "2026-01-15 08:00:00 AM"
    )


def test_format_alias_matches_canonical_function():
    value = "2026-01-15T00:00:00+00:00"
    assert format_utc_to_pht(value) == format_iso_to_pht(value)


def test_empty_or_invalid_timestamp_is_safe():
    assert format_iso_to_pht(None) == ""
    assert format_iso_to_pht("not-a-timestamp") == "not-a-timestamp"


def test_midnight_detection_uses_pht_calendar_date():
    today_pht = datetime.now(PHT_TIMEZONE).date()
    yesterday_date = today_pht - timedelta(days=1)
    yesterday = datetime.combine(yesterday_date, datetime.min.time(), tzinfo=PHT_TIMEZONE)
    yesterday_utc = yesterday.astimezone(timezone.utc).isoformat()
    assert is_session_past_midnight_pht(yesterday_utc)


def test_midnight_detection_handles_missing_and_invalid_values():
    assert not is_session_past_midnight_pht(None)
    assert not is_session_past_midnight_pht("invalid")
