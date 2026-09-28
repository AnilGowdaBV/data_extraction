"""Unit tests for SQLite database persistence and JobRepository delta tracking."""

import os
import tempfile

from backend.app.db.database import get_db_connection, init_db
from backend.app.db.repository import JobRepository


def test_database_initialization() -> None:
    """Verify database schema creation and table structures."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test_jobs.db")
        init_db(db_path)

        assert os.path.exists(db_path)

        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='scraped_jobs';"
            )
            table = cursor.fetchone()
            assert table is not None
            assert table["name"] == "scraped_jobs"


def test_repository_register_new_and_existing() -> None:
    """Verify delta tracking: first insert is NEW, second insert is EXISTING."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test_jobs.db")
        repo = JobRepository(db_path=db_path)

        # 1. First run: Insert Job A
        id1, is_new1, first_seen1 = repo.register_job(
            company_name="Google",
            job_role="Senior Software Engineer",
            number_of_people=100000,
            job_url="https://google.com/careers/123",
            source_website="https://google.com",
        )
        assert id1 > 0
        assert is_new1 is True
        assert first_seen1 is not None

        # 2. First run: Insert Job B
        id2, is_new2, first_seen2 = repo.register_job(
            company_name="Meta",
            job_role="ML Scientist",
            number_of_people=50000,
            job_url="https://meta.com/careers/456",
            source_website="https://meta.com",
        )
        assert id2 > 0
        assert is_new2 is True
        assert id2 != id1

        # 3. Second run: Re-insert Job A (Should be detected as EXISTING)
        id1_repeat, is_new1_repeat, first_seen1_repeat = repo.register_job(
            company_name="Google",
            job_role="Senior Software Engineer",
            number_of_people=100000,
            job_url="https://google.com/careers/123",
            source_website="https://google.com",
        )
        assert id1_repeat == id1
        assert is_new1_repeat is False

        # 4. Check stats
        stats = repo.get_stats()
        assert stats["total_jobs"] == 2
        assert stats["total_companies"] == 2
        assert stats["new_today"] == 2
