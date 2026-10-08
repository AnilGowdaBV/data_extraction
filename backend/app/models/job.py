"""Data models for jobs and extraction state."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ExtractionStatus(str, Enum):
    """Lifecycle status of an extraction job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class RawJobRecord:
    """Unprocessed job record extracted directly from source page/JSON."""

    company_name: str
    job_role: str
    employee_count_raw: str | None = None
    job_url: str | None = None
    company_url: str | None = None
    page_url: str | None = None
    source_type: str = "dom"  # "json_ld", "hydration", "dom_card", "table"


@dataclass
class ProcessedJobRecord:
    """Cleaned, validated, and normalized job record ready for Excel output."""

    company_name: str
    job_role: str
    number_of_people: int | str  # numeric count or "N/A"
    job_url: str | None = None
    is_new: bool = True
    db_id: int | None = None
    posted_date: str = "Unknown"  # Human-readable age label e.g. "3 days ago"
    location: str = "N/A"
    posted_by: str = "N/A"
    first_seen_at: str | None = None

    def to_row(self) -> list[str | int]:
        """Convert to row format for Excel sheet."""
        status_label = "NEW" if self.is_new else "EXISTING"
        return [
            self.company_name,
            self.job_role,
            self.location or "N/A",
            self.number_of_people,
            self.posted_by or "N/A",
            self.posted_date,
            status_label,
        ]

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "company_name": self.company_name,
            "job_role": self.job_role,
            "location": self.location or "N/A",
            "number_of_people": self.number_of_people,
            "posted_by": self.posted_by or "N/A",
            "job_url": self.job_url,
            "posted_date": self.posted_date,
            "status": "NEW" if self.is_new else "EXISTING",
            "is_new": self.is_new,
        }


@dataclass
class ExtractionStats:
    """Real-time metrics accumulated during an extraction run."""

    pages_processed: int = 0
    jobs_discovered: int = 0
    jobs_processed: int = 0
    companies_discovered: int = 0
    duplicates_removed: int = 0
    missing_employee_counts: int = 0
    new_jobs_added: int = 0
    existing_jobs_seen: int = 0
    recent_jobs: list[dict] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: datetime | None = None
    current_action: str = "Initializing..."
    error_message: str | None = None
