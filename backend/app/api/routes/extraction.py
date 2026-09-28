"""API routes for extraction triggers, real-time SSE progress, and downloads."""

import asyncio
import json
import os
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse

from backend.app.core.exceptions import InvalidUrlError, SecurityViolationError
from backend.app.core.logging import get_logger
from backend.app.models.job import ExtractionStatus
from backend.app.schemas.extraction import (
    ExtractionResponse,
    ExtractionSummaryResponse,
    StartExtractionRequest,
)
from backend.app.schemas.job import JobRecordSchema
from backend.app.scraper.discovery import UrlDiscoverySecurity
from backend.app.services.extraction_service import extraction_service

logger = get_logger(__name__)
router = APIRouter(prefix="/api/extraction", tags=["Extraction"])


@router.post("/start", response_model=ExtractionResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_extraction(
    request_payload: StartExtractionRequest,
) -> ExtractionResponse:
    """Initiate an autonomous job extraction process for a provided URL."""
    url_str = str(request_payload.url)

    try:
        validated_url = UrlDiscoverySecurity.validate_url(url_str)
    except SecurityViolationError as e:
        logger.warning("SSRF block on URL: %s - %s", url_str, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security restriction: {e!s}",
        )
    except InvalidUrlError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid website URL: {e!s}",
        )

    job_id = await extraction_service.start_extraction(
        url=validated_url,
        max_records=request_payload.max_records,
        max_pages=request_payload.max_pages,
    )

    return ExtractionResponse(
        job_id=job_id,
        status=ExtractionStatus.RUNNING,
        message="Extraction process initiated successfully.",
    )


@router.get("/progress/{job_id}")
async def stream_progress(job_id: str, request: Request) -> StreamingResponse:
    """Stream real-time extraction progress updates over Server-Sent Events (SSE)."""
    session = extraction_service.get_session(job_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction session '{job_id}' not found.",
        )

    async def event_generator() -> AsyncGenerator[str, None]:
        # Emit current state snapshot immediately upon connection
        initial_payload = {
            "job_id": session.job_id,
            "status": session.status.value,
            "website": session.source_url,
            "pages_processed": session.stats.pages_processed,
            "jobs_discovered": session.stats.jobs_discovered,
            "jobs_processed": session.stats.jobs_processed,
            "companies_discovered": session.stats.companies_discovered,
            "duplicates_removed": session.stats.duplicates_removed,
            "missing_employee_counts": session.stats.missing_employee_counts,
            "new_jobs_added": session.stats.new_jobs_added,
            "existing_jobs_seen": session.stats.existing_jobs_seen,
            "recent_jobs": session.stats.recent_jobs,
            "current_action": session.stats.current_action,
            "download_url": (
                f"/api/extraction/download/{session.job_id}"
                if session.excel_path or session.status in (ExtractionStatus.COMPLETED, ExtractionStatus.STOPPED)
                else None
            ),
            "error": session.error_message,
        }
        yield f"data: {json.dumps(initial_payload)}\n\n"

        while True:
            if await request.is_disconnected():
                logger.info("Client disconnected from SSE progress for job %s", job_id)
                break

            try:
                # Wait for next update with timeout to allow keepalive pings
                update = await asyncio.wait_for(session.progress_queue.get(), timeout=1.0)
                payload_json = update.model_dump_json()
                yield f"data: {payload_json}\n\n"

                # If job reached terminal state, send final event and close stream
                if update.status in (
                    ExtractionStatus.COMPLETED,
                    ExtractionStatus.STOPPED,
                    ExtractionStatus.FAILED,
                ):
                    break
            except asyncio.TimeoutError:
                # Send periodic SSE comment ping to prevent connection timeout
                yield ": ping\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/stop/{job_id}", status_code=status.HTTP_200_OK)
async def stop_extraction(job_id: str) -> dict:
    """Halt an ongoing extraction run gracefully."""
    success = extraction_service.stop_extraction(job_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active extraction session '{job_id}' not found.",
        )
    return {"job_id": job_id, "message": "Extraction stop signal sent."}


@router.get("/summary/{job_id}", response_model=ExtractionSummaryResponse)
async def get_summary(job_id: str) -> ExtractionSummaryResponse:
    """Retrieve full summary statistics and preview rows for a completed extraction."""
    session = extraction_service.get_session(job_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction session '{job_id}' not found.",
        )

    preview_items = [
        JobRecordSchema(
            company_name=r.company_name,
            job_role=r.job_role,
            number_of_people=r.number_of_people,
            job_url=r.job_url,
            status="NEW" if r.is_new else "EXISTING",
            is_new=r.is_new,
        )
        for r in session.records[:25]
    ]

    return ExtractionSummaryResponse(
        job_id=session.job_id,
        status=session.status,
        source_url=session.source_url,
        total_jobs=len(session.records),
        total_companies=session.stats.companies_discovered,
        duplicates_removed=session.stats.duplicates_removed,
        missing_employee_counts=session.stats.missing_employee_counts,
        new_jobs_added=session.stats.new_jobs_added,
        existing_jobs_seen=session.stats.existing_jobs_seen,
        pages_processed=session.stats.pages_processed,
        download_url=f"/api/extraction/download/{session.job_id}",
        preview_records=preview_items,
    )


@router.get("/download/{job_id}")
async def download_excel(job_id: str) -> FileResponse:
    """Download the generated jobs.xlsx workbook."""
    session = extraction_service.get_session(job_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction session '{job_id}' not found.",
        )

    if not session.excel_path or not os.path.exists(session.excel_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Excel file is not yet generated or extraction is still in progress.",
        )

    return FileResponse(
        path=session.excel_path,
        filename="jobs.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
