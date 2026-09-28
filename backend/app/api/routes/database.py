"""API routes for database master export, analytics, and instant download."""

import os
import tempfile
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from backend.app.core.logging import get_logger
from backend.app.db.repository import JobRepository
from backend.app.exporters.excel import ExcelExporter
from backend.app.models.job import ExtractionStats

logger = get_logger(__name__)
router = APIRouter(prefix="/api/database", tags=["Database"])
repository = JobRepository()


@router.get("/stats")
async def get_database_stats() -> dict:
    """Return high-level summary stats of all accumulated jobs in SQLite."""
    stats = repository.get_stats()
    # Also get breakdown by source
    instahyre_jobs = len(repository.get_all_jobs(source_website="instahyre"))
    himalayas_jobs = len(repository.get_all_jobs(source_website="himalayas"))
    
    return {
        "total_jobs": stats["total_jobs"],
        "new_today": stats["new_today"],
        "total_companies": stats["total_companies"],
        "sources": {
            "instahyre": instahyre_jobs,
            "himalayas": himalayas_jobs,
            "other": stats["total_jobs"] - (instahyre_jobs + himalayas_jobs),
        },
    }


@router.get("/export")
async def export_master_database(
    source: Optional[str] = Query(None, description="Filter by source website e.g. instahyre.com"),
) -> FileResponse:
    """
    Generate and download a master multi-tab Excel spreadsheet containing all
    accumulated jobs stored in the database.
    """
    records = repository.get_all_jobs(source_website=source)
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No job records found in the database to export.",
        )

    unique_companies = len(set(r.company_name.lower() for r in records))
    stats = ExtractionStats(
        jobs_discovered=len(records),
        jobs_processed=len(records),
        new_jobs_added=len(records),
        companies_discovered=unique_companies,
    )

    export_dir = os.path.join(tempfile.gettempdir(), "master_database_exports")
    os.makedirs(export_dir, exist_ok=True)
    
    filename = (
        f"Instahyre_Jobs_Master_{len(records)}.xlsx"
        if source and "instahyre" in source.lower()
        else f"All_Scraped_Jobs_Master_{len(records)}.xlsx"
    )
    output_path = os.path.join(export_dir, filename)

    source_label = f"https://www.instahyre.com (Master Archive)" if source else "Master Database Archive"
    ExcelExporter.export(
        records=records,
        stats=stats,
        source_url=source_label,
        output_path=output_path,
    )

    return FileResponse(
        path=output_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
