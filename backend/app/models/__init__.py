"""Domain models package."""

from backend.app.models.job import (
    ExtractionStats,
    ExtractionStatus,
    ProcessedJobRecord,
    RawJobRecord,
)

__all__ = [
    "ExtractionStats",
    "ExtractionStatus",
    "ProcessedJobRecord",
    "RawJobRecord",
]
