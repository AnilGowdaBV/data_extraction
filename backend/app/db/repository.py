from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Optional, Tuple

from backend.app.core.logging import get_logger
from backend.app.db.database import get_db_connection, init_db
from backend.app.models.job import ProcessedJobRecord
from backend.app.utils.date_helpers import iso_str_to_age_label

logger = get_logger(__name__)


class JobRepository:
    """Manages job persistence, deduplication fingerprinting, and delta tracking."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path
        init_db(self.db_path)

    @staticmethod
    def compute_fingerprint(company_name: str, job_role: str, job_url: Optional[str] = None) -> str:
        """
        Generate a deterministic SHA-256 hash identifying the unique job listing.
        Normalizes company, role, and URL to prevent trivial formatting variations.
        """
        norm_company = company_name.strip().lower()
        norm_role = job_role.strip().lower()
        raw_key = f"{norm_company}||{norm_role}"

        if job_url:
            clean_url = job_url.split("?")[0].rstrip("/").lower()
            raw_key += f"||{clean_url}"

        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def register_job(
        self,
        company_name: str,
        job_role: str,
        number_of_people: str | int,
        job_url: Optional[str] = None,
        source_website: Optional[str] = None,
    ) -> Tuple[int, bool, str]:
        """
        Check if the job has been previously recorded:
        - If NEW: Inserts the record with first_seen_at = now, returns (db_id, True, first_seen_at).
        - If EXISTING: Updates last_seen_at = now, increments scrape_count, returns (db_id, False, first_seen_at).
        The third element (first_seen_at) is an ISO datetime string (UTC).
        """
        fingerprint = self.compute_fingerprint(company_name, job_role, job_url)
        str_people = str(number_of_people)

        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()

            # 1. Check if already exists by fingerprint
            cursor.execute(
                "SELECT id, first_seen_at FROM scraped_jobs WHERE fingerprint = ? LIMIT 1;",
                (fingerprint,),
            )
            row = cursor.fetchone()

            if row:
                job_id = row["id"]
                first_seen_at = row["first_seen_at"]
                cursor.execute(
                    """
                    UPDATE scraped_jobs
                    SET last_seen_at = CURRENT_TIMESTAMP,
                        scrape_count = scrape_count + 1,
                        number_of_people = ?,
                        job_url = COALESCE(?, job_url)
                    WHERE id = ?;
                    """,
                    (str_people, job_url, job_id),
                )
                conn.commit()
                return job_id, False, str(first_seen_at)
            else:
                cursor.execute(
                    """
                    INSERT INTO scraped_jobs (
                        fingerprint, job_url, company_name, job_role,
                        number_of_people, source_website,
                        first_seen_at, last_seen_at, scrape_count
                    ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1);
                    """,
                    (
                        fingerprint,
                        job_url,
                        company_name,
                        job_role,
                        str_people,
                        source_website,
                    ),
                )
                conn.commit()
                new_id = cursor.lastrowid
                # Fetch the timestamp just written
                cursor.execute(
                    "SELECT first_seen_at FROM scraped_jobs WHERE id = ?;", (new_id,)
                )
                first_seen_at = cursor.fetchone()["first_seen_at"]
                return new_id, True, str(first_seen_at)

    def get_stats(self) -> dict:
        """Return high-level database metrics."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total FROM scraped_jobs;")
            total_jobs = cursor.fetchone()["total"]

            cursor.execute("""
                SELECT COUNT(*) as new_today
                FROM scraped_jobs
                WHERE date(first_seen_at) = date('now');
                """)
            new_today = cursor.fetchone()["new_today"]

            cursor.execute("""
                SELECT COUNT(DISTINCT company_name) as total_companies
                FROM scraped_jobs;
                """)
            total_companies = cursor.fetchone()["total_companies"]

            return {
                "total_jobs": total_jobs,
                "new_today": new_today,
                "total_companies": total_companies,
            }

    def get_all_jobs(self, source_website: Optional[str] = None) -> list[ProcessedJobRecord]:
        """Fetch all stored jobs from the database as ProcessedJobRecords."""
        today = datetime.now(timezone.utc).date()

        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            if source_website:
                cursor.execute(
                    """
                    SELECT id, company_name, job_role, number_of_people, job_url, first_seen_at
                    FROM scraped_jobs
                    WHERE source_website LIKE ?
                    ORDER BY id DESC;
                    """,
                    (f"%{source_website}%",),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, company_name, job_role, number_of_people, job_url, first_seen_at
                    FROM scraped_jobs
                    ORDER BY id DESC;
                    """
                )
            rows = cursor.fetchall()

            def _is_new(first_seen_at_str: str) -> bool:
                """True only if this job was first added today (UTC)."""
                try:
                    # SQLite stores as 'YYYY-MM-DD HH:MM:SS' or ISO format
                    raw = str(first_seen_at_str).strip()
                    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    return dt.date() == today
                except Exception:
                    return False

            return [
                ProcessedJobRecord(
                    company_name=row["company_name"],
                    job_role=row["job_role"],
                    number_of_people=row["number_of_people"],
                    job_url=row["job_url"],
                    is_new=_is_new(row["first_seen_at"]),
                    db_id=row["id"],
                    posted_date=iso_str_to_age_label(str(row["first_seen_at"])),
                )
                for row in rows
            ]
