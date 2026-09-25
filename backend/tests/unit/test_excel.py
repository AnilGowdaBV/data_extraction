"""Unit tests for ExcelExporter with delta tracking and visual highlighting."""

import os
import tempfile

import openpyxl

from backend.app.exporters.excel import ExcelExporter
from backend.app.models.job import ExtractionStats, ProcessedJobRecord


def test_excel_export_structure() -> None:
    records = [
        ProcessedJobRecord(
            "ABC Technologies", "Software Engineer", "10 - 50 employees", is_new=True
        ),
        ProcessedJobRecord(
            "XYZ Solutions", "Backend Developer", "More than 1000 employees", is_new=False
        ),
        ProcessedJobRecord("Global Enterprises", "Product Lead", "N/A", is_new=True),
    ]
    stats = ExtractionStats(
        pages_processed=1,
        jobs_discovered=4,
        jobs_processed=3,
        companies_discovered=3,
        duplicates_removed=1,
        missing_employee_counts=1,
        new_jobs_added=2,
        existing_jobs_seen=1,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        output_file = os.path.join(temp_dir, "test_jobs.xlsx")
        result_path = ExcelExporter.export(
            records=records,
            stats=stats,
            source_url="https://example.com/careers",
            output_path=output_file,
        )

        assert os.path.exists(result_path)

        wb = openpyxl.load_workbook(result_path)

        # Check sheets
        assert "All Jobs" in wb.sheetnames
        assert "New Jobs Only" in wb.sheetnames
        assert "Existing Jobs Only" in wb.sheetnames
        assert "Small (1-50)" in wb.sheetnames
        assert "Medium (50-500)" in wb.sheetnames
        assert "Large (500+)" in wb.sheetnames
        assert "Summary" in wb.sheetnames

        # Check All Jobs sheet headers
        ws_all = wb["All Jobs"]
        headers = [ws_all.cell(row=1, column=col).value for col in range(1, 5)]
        assert headers == ["Company Name", "Job Role", "Number of People", "Status"]

        # Check records on All Jobs
        row2 = [ws_all.cell(row=2, column=col).value for col in range(1, 5)]
        assert row2 == ["ABC Technologies", "Software Engineer", "10 - 50 employees", "NEW"]

        row3 = [ws_all.cell(row=3, column=col).value for col in range(1, 5)]
        assert row3 == [
            "XYZ Solutions",
            "Backend Developer",
            "More than 1000 employees",
            "EXISTING",
        ]

        row4 = [ws_all.cell(row=4, column=col).value for col in range(1, 5)]
        assert row4 == ["Global Enterprises", "Product Lead", "N/A", "NEW"]

        # Check New Jobs Only sheet
        ws_new = wb["New Jobs Only"]
        assert ws_new.max_row == 3  # Header + 2 new records
        new_row1 = [ws_new.cell(row=2, column=col).value for col in range(1, 5)]
        assert new_row1 == ["ABC Technologies", "Software Engineer", "10 - 50 employees", "NEW"]

        # Check Existing Jobs Only sheet
        ws_existing = wb["Existing Jobs Only"]
        assert ws_existing.max_row == 2  # Header + 1 existing record
        exist_row1 = [ws_existing.cell(row=2, column=col).value for col in range(1, 5)]
        assert exist_row1 == [
            "XYZ Solutions",
            "Backend Developer",
            "More than 1000 employees",
            "EXISTING",
        ]
