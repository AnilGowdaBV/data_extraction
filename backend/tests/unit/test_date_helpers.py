from datetime import datetime, timedelta, timezone

from backend.app.utils.date_helpers import extraction_age_label, source_date_to_age_label


def test_source_date_to_age_label_supports_iso_and_unix_milliseconds() -> None:
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    assert source_date_to_age_label(yesterday.isoformat()) == "Yesterday"
    assert source_date_to_age_label(int(yesterday.timestamp() * 1000)) == "Yesterday"


def test_calendar_yesterday_is_not_today_when_under_24_hours_old() -> None:
    now = datetime.now(timezone.utc)
    previous_calendar_date = now.replace(hour=0, minute=1, second=0, microsecond=0) - timedelta(days=1)

    assert source_date_to_age_label(previous_calendar_date.isoformat()) == "Yesterday"


def test_extraction_age_label_is_today() -> None:
    assert extraction_age_label() == "Today"


def test_source_date_to_age_label_returns_none_for_missing_or_invalid_values() -> None:
    assert source_date_to_age_label(None) is None
    assert source_date_to_age_label("not-a-date") is None
