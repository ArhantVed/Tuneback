"""
utils/formatting.py — Display formatting helpers for Tuneback.

All functions are pure (no side effects, no I/O) so they can be called
from any page or tested independently.

Python concepts demonstrated: f-strings, integer arithmetic, conditional
expressions, datetime formatting.

Functions
---------
ms_to_human(ms)           → "3 days, 2 hours"  (duration display)
ms_to_short(ms)           → "3d 2h"            (compact duration)
short_number(n)           → "1.2k" / "3.4M"    (large-number abbreviation)
date_label(dt, granularity) → "Jan 2022" / "2022" / "15 Jan 2022"
month_label(yyyy_mm)      → "Jan 2022"         (from "YYYY-MM" string)
pct_label(value, total)   → "34.2%"
"""

from __future__ import annotations

from datetime import datetime


def ms_to_human(ms: int) -> str:
    """Convert milliseconds into a human-readable duration string.

    Examples
    --------
    >>> ms_to_human(0)
    '0 minutes'
    >>> ms_to_human(3_600_000)
    '1 hour'
    >>> ms_to_human(90_000_000)
    '1 day, 1 hour'
    >>> ms_to_human(360_000_000)
    '4 days, 4 hours'
    """
    total_seconds = int(ms) // 1_000
    total_minutes = total_seconds // 60
    total_hours   = total_minutes // 60
    days          = total_hours   // 24
    hours         = total_hours   %  24

    if days == 0 and hours == 0:
        # Show minutes for very short durations
        mins = total_minutes % 60
        return f"{mins} minute{'s' if mins != 1 else ''}"

    parts: list[str] = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")

    return ", ".join(parts)


def ms_to_short(ms: int) -> str:
    """Compact duration: '3d 2h', '45m', '2h 30m'.

    Useful in tight UI spaces like stat cards.

    Examples
    --------
    >>> ms_to_short(5_400_000)
    '1h 30m'
    >>> ms_to_short(300_000_000)
    '3d 11h'
    """
    total_minutes = int(ms) // 60_000
    total_hours   = total_minutes // 60
    days          = total_hours   // 24
    hours         = total_hours   %  24
    mins          = total_minutes %  60

    if days > 0:
        return f"{days}d {hours}h" if hours else f"{days}d"
    if hours > 0:
        return f"{hours}h {mins}m" if mins else f"{hours}h"
    return f"{mins}m"


def short_number(n: int | float) -> str:
    """Abbreviate large numbers with K / M suffixes.

    Examples
    --------
    >>> short_number(999)
    '999'
    >>> short_number(1_500)
    '1.5k'
    >>> short_number(2_300_000)
    '2.3M'
    """
    n = float(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(int(n))


def date_label(dt: datetime, granularity: str = "month") -> str:
    """Format a datetime as a readable label for charts and headings.

    Parameters
    ----------
    dt          : The datetime to format.
    granularity : "day" → "15 Jan 2022"
                  "month" → "Jan 2022"   (default)
                  "year"  → "2022"

    Examples
    --------
    >>> date_label(datetime(2022, 3, 15), "month")
    'Mar 2022'
    >>> date_label(datetime(2022, 3, 15), "day")
    '15 Mar 2022'
    >>> date_label(datetime(2022, 3, 15), "year")
    '2022'
    """
    if granularity == "year":
        return dt.strftime("%Y")
    if granularity == "day":
        # %-d (no zero-pad) is Linux-only; use %d and strip the leading zero manually
        return dt.strftime("%d %b %Y").lstrip("0")
    # default: month
    return dt.strftime("%b %Y")


def month_label(yyyy_mm: str) -> str:
    """Convert a 'YYYY-MM' key string to a short display label.

    Used to convert analyser keys (e.g. from plays_over_time) into
    human-readable axis labels.

    Examples
    --------
    >>> month_label("2022-03")
    'Mar 2022'
    >>> month_label("2022-12")
    'Dec 2022'
    """
    year, month = yyyy_mm.split("-")
    dt = datetime(int(year), int(month), 1)
    return dt.strftime("%b %Y")


def pct_label(value: int | float, total: int | float) -> str:
    """Return a percentage string, safely handling zero total.

    Examples
    --------
    >>> pct_label(25, 100)
    '25.0%'
    >>> pct_label(1, 0)
    '—'
    """
    if not total:
        return "—"
    return f"{(value / total) * 100:.1f}%"
