"""Time helpers — all datetimes in this project are Beijing wall-clock (UTC+8, naive)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

BEIJING_TZ = timezone(timedelta(hours=8))


def now_beijing() -> datetime:
    """Current Beijing wall-clock time as a naive datetime."""
    return datetime.now(BEIJING_TZ).replace(tzinfo=None)


def timestamp_to_beijing(ts) -> datetime | None:
    """Convert a Unix epoch (seconds or milliseconds) to a naive Beijing datetime.

    Tolerates None / list / non-numeric / out-of-range inputs by returning None.
    """
    if ts is None or isinstance(ts, list):
        return None
    try:
        ts = int(ts)
    except (ValueError, TypeError):
        return None
    if ts > 10**12:
        ts = ts / 1000
    try:
        return datetime.fromtimestamp(ts, BEIJING_TZ).replace(tzinfo=None)
    except (ValueError, OSError, TypeError):
        return None
