"""Value formatters shared by the PC report sections and page shell."""
from __future__ import annotations

import datetime
import re

_MSJSON = re.compile(r"/Date\((-?\d+)\)/")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def bytes_human(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return n
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    f = float(n)
    while f >= 1024 and i < len(units) - 1:
        f /= 1024
        i += 1
    return f"{f:.1f} {units[i]}"


def kb_human(kilobytes):
    try:
        return bytes_human(int(float(kilobytes)) * 1024)
    except (TypeError, ValueError):
        return kilobytes


def bitrate_to_mbps(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "Unknown"
    if n <= 0 or n >= 9_000_000_000_000_000_000:
        return "Unknown"
    return f"{n / 1_000_000:.1f} Mbps"


def parse_datetime(value) -> datetime.datetime | None:
    """Naive local datetime from the shapes PowerShell JSON produces, else None.

    Handles ``{"value": ..., "DateTime": ...}`` wrappers, ``/Date(ms)/``, CIM
    ``yyyymmddHHMMSS.ffffff+zzz``, ``yyyymmdd``, ISO-8601, and epoch
    seconds or milliseconds.
    """
    if isinstance(value, dict):
        for key in ("value", "DateTime"):
            dt = parse_datetime(value.get(key))
            if dt is not None:
                return dt
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            seconds = value / 1000.0 if value > 10_000_000_000 else float(value)
            return datetime.datetime.fromtimestamp(seconds)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    m = _MSJSON.search(s)
    if m:
        try:
            return datetime.datetime.fromtimestamp(int(m.group(1)) / 1000.0)
        except (OverflowError, OSError, ValueError):
            return None
    if len(s) >= 14 and s[:14].isdigit():
        try:
            return datetime.datetime(int(s[0:4]), int(s[4:6]), int(s[6:8]),
                                     int(s[8:10]), int(s[10:12]), int(s[12:14]))
        except ValueError:
            return None
    if len(s) == 8 and s.isdigit():
        try:
            return datetime.datetime(int(s[0:4]), int(s[4:6]), int(s[6:8]))
        except ValueError:
            return None
    if _ISO_DATE.match(s):
        try:
            dt = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    return None


def fmt_datetime(value, fmt: str = "%Y-%m-%d %H:%M"):
    """Formatted datetime, or the input unchanged when it cannot be parsed."""
    dt = parse_datetime(value)
    if dt is None:
        return "" if value is None or isinstance(value, dict) else value
    return dt.strftime(fmt)


def fmt_date(value):
    return fmt_datetime(value, "%Y-%m-%d")


def uptime_human(since) -> str:
    dt = parse_datetime(since)
    if dt is None:
        return ""
    delta = datetime.datetime.now() - dt
    if delta.total_seconds() < 0:
        return ""
    days = delta.days
    hours, rem = divmod(delta.seconds, 3600)
    minutes = rem // 60
    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    return ", ".join(parts)


def percent(part, whole, digits: int = 1) -> str:
    try:
        part = float(part)
        whole = float(whole)
    except (TypeError, ValueError):
        return ""
    if whole <= 0:
        return ""
    return f"{100.0 * part / whole:.{digits}f} %"


def duration(seconds) -> str:
    """'1 h 02 m 03 s' style, for elapsed and CPU times."""
    try:
        total = int(float(seconds))
    except (TypeError, ValueError):
        return ""
    hours, rem = divmod(max(0, total), 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours} h {minutes:02d} m {secs:02d} s"
    if minutes:
        return f"{minutes} m {secs:02d} s"
    return f"{secs} s"


def mhz(value) -> str:
    try:
        v = int(float(value))
    except (TypeError, ValueError):
        return ""
    return f"{v} MHz" if v < 10_000 else f"{v / 1000:.2f} GHz"


def yes_no(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("true", "yes", "1", "on", "enabled"):
            return "Yes"
        if low in ("false", "no", "0", "off", "disabled"):
            return "No"
        return value
    return "Yes" if value else "No"
