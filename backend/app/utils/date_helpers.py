"""Date/time utility helpers for converting raw timestamps to human-readable age labels."""

from datetime import datetime, timezone
from typing import Any


def unix_to_age_label(unix_ts: int | float) -> str:
    """
    Convert a Unix timestamp (integer seconds) to a human-readable age label.
    Examples: 'Today', '2 days ago', '1 week ago', '3 weeks ago', 'Older than 1 month'.
    """
    now = datetime.now(timezone.utc)
    try:
        posted = datetime.fromtimestamp(int(unix_ts), tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return "Unknown"
    # Age labels represent calendar days, not rolling 24-hour periods.
    days = max(0, (now.date() - posted.date()).days)

    if days == 0:
        return "Today"
    elif days == 1:
        return "Yesterday"
    elif days <= 6:
        return f"{days} days ago"
    elif days <= 13:
        return "1 week ago"
    elif days <= 20:
        return "2 weeks ago"
    elif days <= 27:
        return "3 weeks ago"
    elif days <= 60:
        return "1 month ago"
    else:
        months = days // 30
        return f"{months} months ago"


def datetime_to_age_label(dt: datetime) -> str:
    """Convert an aware/naive datetime object to a human-readable age label."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return unix_to_age_label(dt.timestamp())


def iso_str_to_age_label(iso_str: str) -> str:
    """
    Parse an ISO 8601 date string and return a human-readable age label.
    Falls back to 'Unknown' on parse errors.
    """
    if not iso_str:
        return "Unknown"
    try:
        # Handle 'Z' suffix (Python <3.11 doesn't support it directly)
        clean = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        return datetime_to_age_label(dt)
    except (ValueError, TypeError):
        return "Unknown"


def source_date_to_age_label(value: Any) -> str | None:
    """Convert a source posting date in ISO or Unix format to an age label."""
    if value is None or value == "":
        return None

    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 100_000_000_000:
            timestamp /= 1000
        label = unix_to_age_label(timestamp)
        return label if label != "Unknown" else None

    if isinstance(value, str):
        normalized = value.strip()
        if normalized.isdigit():
            return source_date_to_age_label(int(normalized))
        label = iso_str_to_age_label(normalized)
        return label if label != "Unknown" else None

    return None


def unix_to_himalayas_age(unix_ts: int | float) -> str:
    """
    Format a Unix timestamp (seconds or milliseconds) to Himalayas-style relative age string:
    'Just now', '1 hour ago', '4 hours ago', '1 day ago', '3 days ago', '11 days ago', '1 month ago', '2 months ago'.
    """
    now = datetime.now(timezone.utc)
    try:
        ts = float(unix_ts)
        if ts > 100_000_000_000:
            ts /= 1000
        posted = datetime.fromtimestamp(ts, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return "Unknown"

    total_seconds = max(0, (now - posted).total_seconds())
    days = (now.date() - posted.date()).days
    hours = int(total_seconds // 3600)

    if days == 0:
        if hours < 1:
            return "Today"
        elif hours == 1:
            return "1 hour ago"
        else:
            return f"{hours} hours ago"
    elif days == 1:
        return "1 day ago"
    elif days < 30:
        return f"{days} days ago"
    elif days < 60:
        return "1 month ago"
    else:
        months = max(1, days // 30)
        return f"{months} months ago"


def iso_to_himalayas_age(iso_str: str) -> str:
    """Parse an ISO 8601 date string and return a Himalayas-style relative age label."""
    if not iso_str:
        return "Unknown"
    try:
        clean = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return unix_to_himalayas_age(dt.timestamp())
    except (ValueError, TypeError):
        return "Unknown"


def datetime_to_himalayas_age(dt: datetime) -> str:
    """Convert a datetime object to a Himalayas-style relative age label."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return unix_to_himalayas_age(dt.timestamp())


def extraction_age_label() -> str:
    """Return the age label for the current extraction time."""
    return datetime_to_age_label(datetime.now(timezone.utc))

