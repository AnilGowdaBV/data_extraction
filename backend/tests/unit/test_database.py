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


def test_repository_himalayas_posted_date_and_company_profiles() -> None:
    """Verify Himalayas posted_date, published_at, and company_profiles caching."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test_jobs.db")
        repo = JobRepository(db_path=db_path)

        # 1. Save company profile
        repo.save_company_employee_count("micro1", "micro1", "501-1000")
        assert repo.get_company_employee_count("micro1") == "501-1000"

        # 2. Register job with real posted date and pubDate
        job_id, is_new, _ = repo.register_job(
            company_name="micro1",
            job_role="Altium Designer Specialist",
            number_of_people="501-1000",
            job_url="https://himalayas.app/companies/micro1/jobs/altium-designer-specialist",
            source_website="himalayas.app",
            posted_date="3 days ago",
            published_at=1790652086,
        )
        assert is_new is True

        # 3. Retrieve all jobs and verify posted_date and number_of_people
        jobs = repo.get_all_jobs(source_website="himalayas")
        assert len(jobs) == 1
        rec = jobs[0]
        assert rec.company_name == "micro1"
        assert rec.number_of_people == "501-1000"
        assert rec.posted_date != "Unknown"
        assert "ago" in rec.posted_date or rec.posted_date == "Today"


def test_repository_published_at_normalization_and_sources() -> None:
    """Verify that published_at integers are normalized to ISO string text and get_stats includes sources."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test_jobs.db")
        repo = JobRepository(db_path=db_path)

        # Insert 1 Himalayas job with unix timestamp
        repo.register_job(
            company_name="Acme Startup",
            job_role="Fullstack Engineer",
            number_of_people="11-50",
            job_url="https://himalayas.app/jobs/acme-fullstack",
            source_website="himalayas.app",
            posted_date="Just now",
            published_at=1790740000,
        )

        # Insert 1 Instahyre job
        repo.register_job(
            company_name="Beta Corp",
            job_role="DevOps Engineer",
            number_of_people="1-10",
            job_url="https://instahyre.com/job/123",
            source_website="instahyre.com",
            posted_date="1 day ago",
            published_at="2026-09-29 10:00:00",
        )

        # Check typeof in SQLite to ensure text
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT published_at, typeof(published_at) FROM scraped_jobs WHERE company_name = 'Acme Startup';")
            row = cursor.fetchone()
            assert row[1] == "text"
            assert "2026-" in str(row[0])

        # Check stats
        stats = repo.get_stats()
        assert stats["total_jobs"] == 2
        assert stats["sources"]["himalayas"] == 1
        assert stats["sources"]["instahyre"] == 1
        assert stats["sources"]["other"] == 0

