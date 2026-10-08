"""SQLite database connection and schema initialization."""

import os
import sqlite3
from contextlib import contextmanager
from typing import Generator, Optional

from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


def get_db_path(custom_path: Optional[str] = None) -> str:
    """Resolve absolute path to the SQLite database file."""
    path = custom_path or os.getenv("DB_PATH") or settings.DB_PATH
    if not os.path.isabs(path):
        base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        path = os.path.join(base_dir, path)
    norm_path = os.path.normpath(path)

    # Ensure parent directory exists and is writable
    parent_dir = os.path.dirname(norm_path)
    try:
        os.makedirs(parent_dir, exist_ok=True)
        # Test writability of norm_path directory
        test_file = os.path.join(parent_dir, ".write_test")
        with open(test_file, "w") as f:
            f.write("1")
        os.remove(test_file)
        return norm_path
    except Exception:
        # Fallback to /tmp only when local directory is strictly read-only (e.g. AWS Lambda / Vercel Serverless)
        cloud_db_dir = "/tmp/data"
        os.makedirs(cloud_db_dir, exist_ok=True)
        cloud_db_path = os.path.join(cloud_db_dir, "jobs.db")
        if not os.path.exists(cloud_db_path) and os.path.exists(norm_path):
            import shutil
            try:
                shutil.copy2(norm_path, cloud_db_path)
                logger.info("Copied seed SQLite database to /tmp fallback path %s", cloud_db_path)
            except Exception as e:
                logger.warning("Could not copy seed database to /tmp path: %s", e)
        return cloud_db_path


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Establish and configure an SQLite connection with WAL mode and fast synchronous flush."""
    target_path = get_db_path(db_path)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    conn = sqlite3.connect(target_path, timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@contextmanager
def get_db_connection(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager providing an SQLite connection that always commits and flushes WAL on exit."""
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        try:
            conn.execute("PRAGMA wal_checkpoint(FULL);")
        except Exception:
            pass
        conn.close()


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database schema and required indexes."""
    target_path = get_db_path(db_path)
    logger.info("Initializing SQLite database at: %s", target_path)

    with get_db_connection(target_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS scraped_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint TEXT UNIQUE NOT NULL,
                job_url TEXT,
                company_name TEXT NOT NULL,
                job_role TEXT NOT NULL,
                number_of_people TEXT,
                source_website TEXT,
                first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                scrape_count INTEGER DEFAULT 1,
                posted_date TEXT,
                published_at TIMESTAMP,
                location TEXT,
                posted_by TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_fingerprint ON scraped_jobs(fingerprint);
            CREATE INDEX IF NOT EXISTS idx_jobs_url ON scraped_jobs(job_url);
            CREATE INDEX IF NOT EXISTS idx_jobs_company ON scraped_jobs(company_name);
            CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON scraped_jobs(first_seen_at);

            CREATE TABLE IF NOT EXISTS company_profiles (
                company_slug TEXT PRIMARY KEY,
                company_name TEXT,
                employee_count TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_company_profiles_slug ON company_profiles(company_slug);
            CREATE INDEX IF NOT EXISTS idx_company_profiles_name ON company_profiles(company_name);

            CREATE TABLE IF NOT EXISTS job_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                contact TEXT NOT NULL,
                linkedin_url TEXT,
                resume_filename TEXT,
                resume_path TEXT,
                job_role TEXT NOT NULL,
                company_name TEXT,
                job_url TEXT,
                role_category TEXT NOT NULL DEFAULT 'Other',
                current_salary TEXT,
                expected_salary TEXT,
                notice_period TEXT,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_apps_role_category ON job_applications(role_category);
            CREATE INDEX IF NOT EXISTS idx_apps_applied_at ON job_applications(applied_at);
            """)

        # Auto-migrate existing scraped_jobs table if needed
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(scraped_jobs);")
        existing_cols = {row["name"] for row in cursor.fetchall()}
        if "posted_date" not in existing_cols:
            cursor.execute("ALTER TABLE scraped_jobs ADD COLUMN posted_date TEXT;")
        if "published_at" not in existing_cols:
            cursor.execute("ALTER TABLE scraped_jobs ADD COLUMN published_at TIMESTAMP;")
        if "location" not in existing_cols:
            cursor.execute("ALTER TABLE scraped_jobs ADD COLUMN location TEXT;")
        if "posted_by" not in existing_cols:
            cursor.execute("ALTER TABLE scraped_jobs ADD COLUMN posted_by TEXT;")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_location ON scraped_jobs(location);")

        # Auto-migrate any integer/unix published_at to standard ISO string format
        try:
            cursor.execute("SELECT id, published_at FROM scraped_jobs WHERE typeof(published_at) = 'integer';")
            int_rows = cursor.fetchall()
            if int_rows:
                from datetime import datetime, timezone
                for r in int_rows:
                    try:
                        dt_str = datetime.fromtimestamp(int(r["published_at"]), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                        cursor.execute("UPDATE scraped_jobs SET published_at = ? WHERE id = ?;", (dt_str, r["id"]))
                    except Exception:
                        pass
        except Exception:
            pass

        conn.commit()
    logger.info("Database schema initialized successfully.")

