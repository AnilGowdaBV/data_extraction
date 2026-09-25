"""Orchestrates extraction background tasks, progress streaming, and lifecycle."""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from backend.app.core.logging import get_logger
from backend.app.models.job import ExtractionStats, ExtractionStatus, ProcessedJobRecord
from backend.app.schemas.extraction import ProgressUpdate
from backend.app.schemas.job import JobRecordSchema
from backend.app.scraper.browser import BrowserManager
from backend.app.scraper.crawler import JobCrawler
from backend.app.services.export_service import ExportService

logger = get_logger(__name__)


@dataclass
class ExtractionSession:
    """In-memory state tracking a single extraction run."""

    job_id: str
    source_url: str
    max_records: int
    max_pages: int
    status: ExtractionStatus = ExtractionStatus.PENDING
    stats: ExtractionStats = field(default_factory=ExtractionStats)
    records: list[ProcessedJobRecord] = field(default_factory=list)
    crawler: JobCrawler | None = None
    excel_path: str | None = None
    progress_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    error_message: str | None = None
    task: asyncio.Task | None = None


class ExtractionService:
    """Manages active extraction sessions and handles real-time SSE broadcasts."""

    def __init__(self) -> None:
        self._sessions: dict[str, ExtractionSession] = {}
        self._browser_manager = BrowserManager()

    async def initialize(self) -> None:
        """Initialize shared browser manager."""
        await self._browser_manager.initialize()

    async def shutdown(self) -> None:
        """Clean up all active jobs and browser resources."""
        for session in self._sessions.values():
            if session.crawler:
                session.crawler.stop()
            if session.task and not session.task.done():
                session.task.cancel()
        await self._browser_manager.close()

    def get_session(self, job_id: str) -> ExtractionSession | None:
        """Look up session by ID."""
        return self._sessions.get(job_id)

    async def start_extraction(
        self, url: str, max_records: int = 100000, max_pages: int = 1000
    ) -> str:
        """Initiate background extraction and return assigned job_id."""
        job_id = str(uuid.uuid4())
        session = ExtractionSession(
            job_id=job_id,
            source_url=url,
            max_records=max_records,
            max_pages=max_pages,
            status=ExtractionStatus.RUNNING,
        )
        self._sessions[job_id] = session

        # Launch background worker
        task = asyncio.create_task(self._run_extraction(session))
        session.task = task
        return job_id

    def stop_extraction(self, job_id: str) -> bool:
        """Signal an active extraction to halt."""
        session = self._sessions.get(job_id)
        if session and session.crawler:
            session.crawler.stop()
            session.status = ExtractionStatus.STOPPED
            return True
        return False

    async def _emit_progress(self, session: ExtractionSession, stats: ExtractionStats) -> None:
        """Push a progress snapshot to the session SSE queue."""
        download_url = (
            f"/api/extraction/download/{session.job_id}"
            if session.status == ExtractionStatus.COMPLETED
            else None
        )
        recent_items = [
            JobRecordSchema(
                company_name=j.get("company_name", ""),
                job_role=j.get("job_role", ""),
                number_of_people=j.get("number_of_people", "N/A"),
                job_url=j.get("job_url"),
                status=j.get("status", "NEW"),
                is_new=j.get("is_new", True),
            )
            for j in (stats.recent_jobs or [])
        ]
        update = ProgressUpdate(
            job_id=session.job_id,
            status=session.status,
            website=session.source_url,
            pages_processed=stats.pages_processed,
            jobs_discovered=stats.jobs_discovered,
            jobs_processed=stats.jobs_processed,
            companies_discovered=stats.companies_discovered,
            duplicates_removed=stats.duplicates_removed,
            missing_employee_counts=stats.missing_employee_counts,
            new_jobs_added=stats.new_jobs_added,
            existing_jobs_seen=stats.existing_jobs_seen,
            recent_jobs=recent_items,
            current_action=stats.current_action,
            download_url=download_url,
            error=session.error_message,
        )
        await session.progress_queue.put(update)

    async def _run_extraction(self, session: ExtractionSession) -> None:
        """Async worker executing crawler, data processing, and excel generation."""
        logger.info("Extraction started for job %s [%s]", session.job_id, session.source_url)
        crawler = JobCrawler(self._browser_manager)
        session.crawler = crawler

        async def progress_callback(stats: ExtractionStats) -> None:
            session.stats = stats
            await self._emit_progress(session, stats)

        try:
            # Execute crawler
            records = await crawler.crawl(
                start_url=session.source_url,
                max_records=session.max_records,
                max_pages=session.max_pages,
                on_progress=progress_callback,
            )
            session.records = records

            if session.status != ExtractionStatus.STOPPED:
                session.stats.current_action = "Generating professional Excel file..."
                await self._emit_progress(session, session.stats)

                # Generate Excel
                excel_path = ExportService.generate_excel(
                    job_id=session.job_id,
                    records=records,
                    stats=session.stats,
                    source_url=session.source_url,
                )
                session.excel_path = excel_path
                session.status = ExtractionStatus.COMPLETED
                session.stats.current_action = "Extraction complete! Excel file ready for download."
                session.stats.end_time = datetime.now(timezone.utc)
                await self._emit_progress(session, session.stats)
                logger.info(
                    "Job %s completed successfully with %d records",
                    session.job_id,
                    len(records),
                )

        except asyncio.CancelledError:
            session.status = ExtractionStatus.STOPPED
            session.stats.current_action = "Extraction cancelled."
            await self._emit_progress(session, session.stats)
            logger.info("Job %s was cancelled", session.job_id)
        except Exception as e:
            session.status = ExtractionStatus.FAILED
            session.error_message = str(e)
            session.stats.current_action = f"Extraction failed: {e!s}"
            await self._emit_progress(session, session.stats)
            logger.error("Job %s encountered error: %s", session.job_id, e, exc_info=True)


# Global singleton instance
extraction_service = ExtractionService()
