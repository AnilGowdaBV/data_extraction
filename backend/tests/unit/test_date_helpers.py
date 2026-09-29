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


def test_unix_to_himalayas_age_exact_formats() -> None:
    from backend.app.utils.date_helpers import iso_to_himalayas_age, unix_to_himalayas_age

    now = datetime.now(timezone.utc)

    # 1 day ago
    one_day = now - timedelta(days=1, hours=1)
    assert unix_to_himalayas_age(one_day.timestamp()) == "1 day ago"

    # 3 days ago (Image 3 Altium Designer Specialist)
    three_days = now - timedelta(days=3, hours=1)
    assert unix_to_himalayas_age(three_days.timestamp()) == "3 days ago"

    # 4 days ago (Image 3 GitHub Specialist)
    four_days = now - timedelta(days=4, hours=1)
    assert unix_to_himalayas_age(four_days.timestamp()) == "4 days ago"

    # 5 days ago (Image 3 Security Onion Specialist, Image 2 Dementia Adviser)
    five_days = now - timedelta(days=5, hours=1)
    assert unix_to_himalayas_age(five_days.timestamp()) == "5 days ago"

    # 11 days ago (Image 2 Trainee Health and Social Care Assessor)
    eleven_days = now - timedelta(days=11, hours=1)
    assert unix_to_himalayas_age(eleven_days.timestamp()) == "11 days ago"

    # 40 days ago -> 1 month ago
    forty_days = now - timedelta(days=40)
    assert unix_to_himalayas_age(forty_days.timestamp()) == "1 month ago"

    # 70 days ago -> 2 months ago
    seventy_days = now - timedelta(days=70)
    assert unix_to_himalayas_age(seventy_days.timestamp()) == "2 months ago"

    # ISO string support
    assert iso_to_himalayas_age(eleven_days.isoformat()) == "11 days ago"
    assert iso_to_himalayas_age("invalid") == "Unknown"

