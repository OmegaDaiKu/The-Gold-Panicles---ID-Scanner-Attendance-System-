""""Timestamp formatting, UTC ISO utilities, and Philippine Standard Time (PHT) converters."""

from datetime import datetime, timezone, timedelta
from typing import Optional

PHT_OFFSET = timedelta(hours=8)
PHT_TIMEZONE = timezone(PHT_OFFSET)


def get_utc_now_iso() -> str:
    """Returns current UTC timestamp in canonical ISO-8601 string format."""
    return datetime.now(timezone.utc).isoformat()


def format_iso_to_pht(iso_str: Optional[str], time_only: bool = True) -> str:
    """Converts ISO UTC string to formatted Philippine Local Time (PHT, UTC+8).

    FIXED THIS SESSION: previously this called `.astimezone(PHT_TIMEZONE)`
    directly on whatever `datetime.fromisoformat()` produced. If `iso_str`
    ever lacked a UTC offset (a naive timestamp), Python's `astimezone()` on
    a naive datetime silently assumes it is already in the *host system's
    local timezone*, not UTC, and converts from there -- producing a wrong
    displayed PHT time with no error raised. Every live write path seen this
    session (get_utc_now_iso(), attendance_repo.py's direct
    `datetime.now(timezone.utc).isoformat()`) always produces a tz-aware
    string, so this was not currently reachable -- but it was inconsistent
    with attendance_service.py's own private _parse_iso_to_utc_datetime(),
    which already guards this exact case (`if dt.tzinfo is None: dt =
    dt.replace(tzinfo=timezone.utc)`). Since this module is the single
    canonical time-formatting utility used across the admin UI, it now
    applies the same guard.
    """
    if not iso_str:
        return ""
    try:
        dt_utc = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        dt_pht = dt_utc.astimezone(PHT_TIMEZONE)
        if time_only:
            return dt_pht.strftime("%I:%M:%S %p")
        return dt_pht.strftime("%Y-%m-%d %I:%M:%S %p")
    except (ValueError, TypeError, AttributeError):
        return str(iso_str)


format_utc_to_pht = format_iso_to_pht


def is_session_past_midnight_pht(time_in_iso: Optional[str]) -> bool:
    """Determines whether a time_in timestamp crossed midnight PHT relative to current time.

    FIXED THIS SESSION: same naive-datetime guard added as format_iso_to_pht()
    above, for the same reason -- this function also calls `.astimezone()`
    on a value that could theoretically be naive.
    """
    if not time_in_iso:
        return False
    try:
        dt_in_utc = datetime.fromisoformat(str(time_in_iso).replace("Z", "+00:00"))
        if dt_in_utc.tzinfo is None:
            dt_in_utc = dt_in_utc.replace(tzinfo=timezone.utc)
        dt_in_pht = dt_in_utc.astimezone(PHT_TIMEZONE)
        dt_now_pht = datetime.now(PHT_TIMEZONE)
        return dt_in_pht.date() < dt_now_pht.date()
    except (ValueError, TypeError, AttributeError):
        return False