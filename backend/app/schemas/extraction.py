"""Schemas for extraction endpoints and real-time SSE progress events."""

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from backend.app.models.job import ExtractionStatus
from backend.app.schemas.job import JobRecordSchema


class StartExtractionRequest(BaseModel):
    """Payload to initiate a new extraction job."""

    model_config = ConfigDict(extra="forbid")

    url: HttpUrl = Field(..., description="Target job website URL to extract from")
    max_records: int = Field(
        default=100000,
        ge=1,
        le=500000,
        description="Safety ceiling for total records extracted",
    )
    max_pages: int = Field(
        default=1000,
        ge=1,
        le=5000,
        description="Safety ceiling for total pages crawled",
    )


class ExtractionResponse(BaseModel):
    """Initial response returned upon starting an extraction."""

    job_id: str
    status: ExtractionStatus
    message: str


class ProgressUpdate(BaseModel):
    """Payload emitted over Server-Sent Events (SSE) during extraction."""

    job_id: str
    status: ExtractionStatus
    website: str
    pages_processed: int
    jobs_discovered: int
    jobs_processed: int
    companies_discovered: int
    duplicates_removed: int
    missing_employee_counts: int
    new_jobs_added: int = 0
    existing_jobs_seen: int = 0
    recent_jobs: list[JobRecordSchema] = []
    current_action: str
    download_url: str | None = None
    error: str | None = None


class ExtractionSummaryResponse(BaseModel):
    """Final summary returned upon completion."""

    job_id: str
    status: ExtractionStatus
    source_url: str
    total_jobs: int
    total_companies: int
    duplicates_removed: int
    missing_employee_counts: int
    new_jobs_added: int = 0
    existing_jobs_seen: int = 0
    pages_processed: int
    download_url: str
    preview_records: list[JobRecordSchema] = []
