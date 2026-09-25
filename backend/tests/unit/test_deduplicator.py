"""Unit tests for JobDeduplicator."""

from backend.app.processors.deduplicator import JobDeduplicator


def test_url_based_deduplication() -> None:
    dedup = JobDeduplicator()
    assert not dedup.is_duplicate("ABC Tech", "Software Engineer", "https://example.com/jobs/1")
    # Same URL is duplicate
    assert dedup.is_duplicate("ABC Tech", "Software Engineer", "https://example.com/jobs/1")
    assert dedup.duplicates_count == 1


def test_url_normalization_with_query_params() -> None:
    dedup = JobDeduplicator()
    assert not dedup.is_duplicate(
        "ABC Tech", "Software Engineer", "https://example.com/jobs/1?utm_source=feed"
    )
    # Same canonical URL
    assert dedup.is_duplicate("ABC Tech", "Software Engineer", "https://example.com/jobs/1#top")
    assert dedup.duplicates_count == 1


def test_company_role_fallback_deduplication() -> None:
    dedup = JobDeduplicator()
    # Without URL, combination of Company + Role is used
    assert not dedup.is_duplicate("ABC Technologies", "Software Engineer", None)
    # Exact duplicate
    assert dedup.is_duplicate("ABC Technologies", "Software Engineer", None)
    # Case and punctuation variation
    assert dedup.is_duplicate("abc technologies", "software engineer", None)
    assert dedup.duplicates_count == 2


def test_different_roles_are_not_duplicates() -> None:
    dedup = JobDeduplicator()
    assert not dedup.is_duplicate("ABC Technologies", "Software Engineer", None)
    assert not dedup.is_duplicate("ABC Technologies", "Senior Software Engineer", None)
    assert not dedup.is_duplicate("ABC Technologies", "Backend Developer", None)
    assert dedup.duplicates_count == 0
