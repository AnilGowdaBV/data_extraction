"""API routes for database master export, analytics, and instant download."""

import os
import tempfile
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from backend.app.core.logging import get_logger
from backend.app.db.repository import JobRepository
from backend.app.exporters.excel import ExcelExporter
from backend.app.models.categories import CATEGORIES, filter_jobs_for_category
from backend.app.models.job import ExtractionStats

logger = get_logger(__name__)
router = APIRouter(prefix="/api/database", tags=["Database"])
repository = JobRepository()


@router.get("/stats")
async def get_database_stats() -> dict:
    """Return high-level summary stats of all accumulated jobs in SQLite."""
    return repository.get_stats()


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


@router.get("/categories")
async def get_categories_overview(
    source: Optional[str] = Query("himalayas", description="Filter source e.g. himalayas, instahyre, or all"),
) -> list[dict]:
    """Return overview of all 8 domain categories, keywords, and job counts."""
    src_filter = source if source and source.lower() != "all" else None
    all_jobs = repository.get_all_jobs(source_website=src_filter)
    results = []

    for cat_id, cat_info in CATEGORIES.items():
        filtered = filter_jobs_for_category(all_jobs, cat_id)
        results.append({
            "id": cat_id,
            "name": cat_info["name"],
            "filename": cat_info["filename"],
            "icon": cat_info["icon"],
            "color": cat_info["color"],
            "keywords": [kw["name"] for kw in cat_info["keywords"]],
            "total_jobs": len(filtered["all_category_jobs"]),
            "under_100_jobs": len(filtered["all_under_100"]),
            "keyword_breakdown": {
                kw_name: {
                    "total": len(data["all"]),
                    "under_100": len(data["under_100"]),
                }
                for kw_name, data in filtered["keywords"].items()
            },
        })

    return results


@router.get("/export/category")
async def export_category_database(
    category_id: str = Query(..., description="Category ID e.g. qa_automation, devops_cloud"),
    source: Optional[str] = Query("himalayas", description="Filter source e.g. himalayas, instahyre, or all"),
) -> FileResponse:
    """
    Generate and download a multi-tab Excel workbook for a specific domain category.
    Includes:
    - Tab 1: All Category Jobs
    - Tab 2: Under 100 People (All in category)
    - Dedicated tabs for each keyword (e.g. Selenium, Playwright, Cypress)
    - Dedicated tabs for each keyword under 100 people (e.g. Selenium (<100))
    - Summary Tab
    """
    cat_info = CATEGORIES.get(category_id)
    if not cat_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category '{category_id}' not found.",
        )

    src_filter = source if source and source.lower() != "all" else None
    all_jobs = repository.get_all_jobs(source_website=src_filter)
    category_data = filter_jobs_for_category(all_jobs, category_id)

    export_dir = os.path.join(tempfile.gettempdir(), "category_database_exports")
    os.makedirs(export_dir, exist_ok=True)

    prefix = f"{source.capitalize()}_" if source and source.lower() != "all" else ""
    filename = f"{prefix}{cat_info['filename']}"
    output_path = os.path.join(export_dir, filename)

    ExcelExporter.export_category_workbook(
        category_meta=cat_info,
        category_data=category_data,
        output_path=output_path,
    )

    return FileResponse(
        path=output_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/sync-google-sheet")
async def sync_database_to_google_sheet(
    source: Optional[str] = Query(None, description="Filter source e.g. instahyre, himalayas, or all"),
    by_date: bool = Query(True, description="Group all jobs by their scraped date tabs"),
    limit: Optional[int] = Query(None, description="Optional max jobs to sync"),
) -> dict:
    """
    Safely sync jobs directly into the user's Google Spreadsheet.
    If by_date is True, groups all jobs by their scraped date (e.g. Sep 23, Sep 24, Oct 8)
    and dumps each group into its own date tab.
    Existing tabs and data are completely untouched.
    """
    src_filter = source if source and source.lower() != "all" else None
    all_recs = repository.get_all_jobs(source_website=src_filter)
    if not all_recs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No job records found to sync.",
        )

    if limit and limit > 0:
        all_recs = all_recs[:limit]

    from backend.app.exporters.google_sheets import GoogleSheetsExporter
    if by_date:
        res = await GoogleSheetsExporter.sync_all_jobs_by_date(all_recs)
    else:
        new_today = [r for r in all_recs if r.is_new]
        recs_to_sync = new_today if new_today else all_recs
        res = await GoogleSheetsExporter.sync_jobs_to_sheet(recs_to_sync)

    return res

