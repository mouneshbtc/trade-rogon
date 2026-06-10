"""Calendar-month arithmetic shared by the ingestion and replay scripts."""

import calendar
from datetime import datetime


def shift_months(dt: datetime, delta: int) -> datetime:
    """Return `dt` shifted by `delta` calendar months, clamping the day if the
    target month is shorter (e.g. Jan 31 - 1 month -> Dec 31, Mar 31 - 1 month -> Feb 28/29)."""
    month_index = dt.month - 1 + delta
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)
