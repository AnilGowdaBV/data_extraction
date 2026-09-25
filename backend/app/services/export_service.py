"""Service for managing export generation and file outputs."""

import os
import tempfile

from backend.app.exporters.excel import ExcelExporter
from backend.app.models.job import ExtractionStats, ProcessedJobRecord


class ExportService:
    """Coordinates writing and storing generated output files."""

    EXPORT_DIR = os.path.join(tempfile.gettempdir(), "job_extractor_exports")

    @classmethod
    def get_export_path(cls, job_id: str) -> str:
        """Derive output .xlsx file path for a specific extraction job."""
        job_dir = os.path.join(cls.EXPORT_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        return os.path.join(job_dir, "jobs.xlsx")

    @classmethod
    def generate_excel(
        cls,
        job_id: str,
        records: list[ProcessedJobRecord],
        stats: ExtractionStats,
        source_url: str,
    ) -> str:
        """Produce the Excel workbook and return the local filesystem path."""
        target_path = cls.get_export_path(job_id)
        return ExcelExporter.export(
            records=records,
            stats=stats,
            source_url=source_url,
            output_path=target_path,
        )
