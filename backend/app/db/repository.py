from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timezone
from typing import Any, Optional, Tuple

from backend.app.core.logging import get_logger
from backend.app.db.database import get_db_connection, init_db
from backend.app.models.job import ProcessedJobRecord
from backend.app.utils.date_helpers import iso_str_to_age_label, iso_to_himalayas_age, unix_to_himalayas_age

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
        posted_date: Optional[str] = None,
        published_at: Optional[Any] = None,
        location: Optional[str] = "N/A",
        posted_by: Optional[str] = "N/A",
    ) -> Tuple[int, bool, str]:
        """
        Check if the job has been previously recorded:
        - If NEW: Inserts the record with first_seen_at = now, returns (db_id, True, first_seen_at).
        - If EXISTING: Updates last_seen_at = now, increments scrape_count, returns (db_id, False, first_seen_at).
        The third element (first_seen_at) is an ISO datetime string (UTC).
        """
        fingerprint = self.compute_fingerprint(company_name, job_role, job_url)
        str_people = str(number_of_people)
        clean_loc = str(location).strip() if location else "N/A"
        clean_posted_by = str(posted_by).strip() if posted_by else "N/A"

        # Standardize published_at to ISO string format (YYYY-MM-DD HH:MM:SS)
        norm_published_at = None
        if published_at is not None:
            if isinstance(published_at, (int, float)) or (isinstance(published_at, str) and published_at.isdigit()):
                try:
                    norm_published_at = datetime.fromtimestamp(float(published_at), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    norm_published_at = str(published_at)
            elif isinstance(published_at, str) and published_at.strip():
                try:
                    clean_str = published_at.strip().replace("Z", "+00:00")
                    dt = datetime.fromisoformat(clean_str)
                    norm_published_at = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    norm_published_at = published_at.strip()

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
                        number_of_people = CASE
                            WHEN ? != 'N/A' AND ? != '' THEN ?
                            ELSE number_of_people
                        END,
                        location = CASE
                            WHEN ? != 'N/A' AND ? != '' THEN ?
                            ELSE location
                        END,
                        posted_by = CASE
                            WHEN ? != 'N/A' AND ? != '' THEN ?
                            ELSE posted_by
                        END,
                        job_url = COALESCE(?, job_url),
                        posted_date = COALESCE(?, posted_date),
                        published_at = COALESCE(?, published_at)
                    WHERE id = ?;
                    """,
                    (
                        str_people, str_people, str_people,
                        clean_loc, clean_loc, clean_loc,
                        clean_posted_by, clean_posted_by, clean_posted_by,
                        job_url, posted_date, norm_published_at, job_id,
                    ),
                )
                conn.commit()
                return job_id, False, str(first_seen_at)
            else:
                cursor.execute(
                    """
                    INSERT INTO scraped_jobs (
                        fingerprint, job_url, company_name, job_role,
                        number_of_people, source_website, posted_date, published_at,
                        location, posted_by, first_seen_at, last_seen_at, scrape_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1);
                    """,
                    (
                        fingerprint,
                        job_url,
                        company_name,
                        job_role,
                        str_people,
                        source_website,
                        posted_date,
                        norm_published_at,
                        clean_loc,
                        clean_posted_by,
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

    def get_company_employee_count(self, company_slug: str) -> Optional[str]:
        """Fetch cached employee count for a company slug from company_profiles."""
        if not company_slug:
            return None
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT employee_count FROM company_profiles WHERE company_slug = ? LIMIT 1;",
                (company_slug.lower().strip(),),
            )
            row = cursor.fetchone()
            if row and row["employee_count"]:
                return str(row["employee_count"])
        return None

    def save_company_employee_count(
        self, company_slug: str, company_name: str, employee_count: str
    ) -> None:
        """Persist or update employee count in company_profiles table."""
        if not company_slug:
            return
        slug = company_slug.lower().strip()
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO company_profiles (company_slug, company_name, employee_count, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(company_slug) DO UPDATE SET
                    employee_count = excluded.employee_count,
                    company_name = COALESCE(excluded.company_name, company_profiles.company_name),
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (slug, company_name, str(employee_count)),
            )
            conn.commit()

    def get_all_company_profiles(self) -> dict[str, str]:
        """Return a mapping of company_slug -> employee_count."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT company_slug, employee_count FROM company_profiles;")
            return {
                row["company_slug"]: row["employee_count"]
                for row in cursor.fetchall()
                if row["employee_count"]
            }

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

            cursor.execute("SELECT COUNT(*) as himalayas FROM scraped_jobs WHERE source_website LIKE '%himalayas%';")
            himalayas_jobs = cursor.fetchone()["himalayas"]

            cursor.execute("SELECT COUNT(*) as instahyre FROM scraped_jobs WHERE source_website LIKE '%instahyre%';")
            instahyre_jobs = cursor.fetchone()["instahyre"]

            return {
                "total_jobs": total_jobs,
                "new_today": new_today,
                "total_companies": total_companies,
                "sources": {
                    "instahyre": instahyre_jobs,
                    "himalayas": himalayas_jobs,
                    "other": max(0, total_jobs - (instahyre_jobs + himalayas_jobs)),
                },
            }

    def get_all_jobs(self, source_website: Optional[str] = None) -> list[ProcessedJobRecord]:
        """Fetch all stored jobs from the database as ProcessedJobRecords."""
        today = datetime.now(timezone.utc).date()
        company_profiles = self.get_all_company_profiles()

        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            query = """
                SELECT id, company_name, job_role, number_of_people, job_url, first_seen_at,
                       posted_date, published_at, location, posted_by
                FROM scraped_jobs
            """
            params: list[Any] = []
            if source_website:
                query += " WHERE source_website LIKE ?"
                params.append(f"%{source_website}%")
            query += " ORDER BY id DESC;"

            cursor.execute(query, params)
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

            records = []
            for row in rows:
                emp_count = row["number_of_people"]
                url = row["job_url"] or ""

                # If employee count is N/A or empty, check company_profiles cache
                if str(emp_count).strip() in ("N/A", "", "None"):
                    slug = None
                    if "/companies/" in url:
                        m = re.search(r"/companies/([^/]+)", url)
                        if m:
                            slug = m.group(1).lower().strip()
                    if slug and slug in company_profiles:
                        emp_count = company_profiles[slug]
                    elif row["company_name"]:
                        alt_slug = re.sub(r"[^a-z0-9]+", "-", row["company_name"].lower()).strip("-")
                        if alt_slug in company_profiles:
                            emp_count = company_profiles[alt_slug]

                # Determine accurate posted_date
                pub_at = row["published_at"]
                raw_posted = row["posted_date"]
                if pub_at:
                    if str(pub_at).isdigit() or isinstance(pub_at, (int, float)):
                        p_date = unix_to_himalayas_age(float(pub_at))
                    else:
                        p_date = iso_to_himalayas_age(str(pub_at))
                elif raw_posted and str(raw_posted).strip() not in ("Unknown", "N/A", ""):
                    p_date = str(raw_posted)
                else:
                    # Fallback to first_seen_at using accurate relative days
                    p_date = iso_to_himalayas_age(str(row["first_seen_at"]))

                loc_val = row["location"] if "location" in row.keys() and row["location"] else "N/A"
                posted_by_val = row["posted_by"] if "posted_by" in row.keys() and row["posted_by"] else "N/A"

                records.append(
                    ProcessedJobRecord(
                        company_name=row["company_name"],
                        job_role=row["job_role"],
                        number_of_people=emp_count if emp_count else "N/A",
                        job_url=row["job_url"],
                        is_new=_is_new(row["first_seen_at"]),
                        db_id=row["id"],
                        posted_date=p_date,
                        location=loc_val,
                        posted_by=posted_by_val,
                        first_seen_at=str(row["first_seen_at"]) if row["first_seen_at"] else None,
                    )
                )
            return records
