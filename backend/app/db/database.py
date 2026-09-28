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
    path = custom_path or settings.DB_PATH
    if not os.path.isabs(path):
        # Resolve relative to project root (where pyproject.toml is)
        base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        path = os.path.join(base_dir, path)
    return os.path.normpath(path)


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Establish and configure an SQLite connection with WAL mode."""
    target_path = get_db_path(db_path)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    conn = sqlite3.connect(target_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    # Fast, concurrent-safe settings
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@contextmanager
def get_db_connection(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager providing an SQLite connection that always closes cleanly upon exit."""
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
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
                scrape_count INTEGER DEFAULT 1
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_fingerprint ON scraped_jobs(fingerprint);
            CREATE INDEX IF NOT EXISTS idx_jobs_url ON scraped_jobs(job_url);
            CREATE INDEX IF NOT EXISTS idx_jobs_company ON scraped_jobs(company_name);
            CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON scraped_jobs(first_seen_at);

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
        conn.commit()
    logger.info("Database schema initialized successfully.")

