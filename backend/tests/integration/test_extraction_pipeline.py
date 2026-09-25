"""Integration test for the extraction and export pipeline."""

import os
import tempfile

from bs4 import BeautifulSoup

from backend.app.exporters.excel import ExcelExporter
from backend.app.extractors.employee_extractor import EmployeeCountExtractor
from backend.app.extractors.job_extractor import JobExtractor
from backend.app.models.job import ExtractionStats, ProcessedJobRecord
from backend.app.processors.cleaner import DataCleaner
from backend.app.processors.deduplicator import JobDeduplicator
from backend.app.processors.validator import DataValidator
from backend.app.scraper.pagination import PaginationHandler


def test_full_extraction_pipeline_on_fixture() -> None:
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "sample_jobs.html")
    with open(fixture_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    base_url = "https://example.com/jobs"

    # 1. Extraction
    raw_records = JobExtractor.extract_from_html(html_content, base_url=base_url)
    assert len(raw_records) >= 5, f"Expected at least 5 raw records, found {len(raw_records)}"

    # 2. Processing (Clean, Dedup, Validate)
    deduplicator = JobDeduplicator()
    processed_records = []
    unique_companies = set()
    missing_emp_count = 0

    for raw in raw_records:
        clean_company = DataCleaner.clean_company_name(raw.company_name)
        clean_role = DataCleaner.clean_job_role(raw.job_role)

        if deduplicator.is_duplicate(clean_company, clean_role, raw.job_url):
            continue

        emp_count = "N/A"
        if raw.employee_count_raw:
            emp_count = EmployeeCountExtractor.parse_count(raw.employee_count_raw)

        if emp_count == "N/A":
            missing_emp_count += 1

        if DataValidator.is_valid_record(clean_company, clean_role, emp_count):
            record = ProcessedJobRecord(
                company_name=clean_company,
                job_role=clean_role,
                number_of_people=emp_count,
                job_url=raw.job_url,
            )
            processed_records.append(record)
            unique_companies.add(DataCleaner.normalize_key(clean_company))

    # 3. Assertions on processed records
    # Notice: Card 5 is an exact duplicate of Card 1 (ABC Technologies / Software Engineer),
    # so duplicates_count should be at least 1!
    assert deduplicator.duplicates_count >= 1
    assert len(processed_records) >= 4

    # Verify known companies extracted
    extracted_companies = {r.company_name for r in processed_records}
    assert "ABC Technologies" in extracted_companies
    assert "XYZ Solutions" in extracted_companies
    assert "Global Data Corp" in extracted_companies

    # Verify employee counts
    abc_job = next(r for r in processed_records if r.company_name == "ABC Technologies")
    assert abc_job.number_of_people == "250 employees"

    xyz_job = next(r for r in processed_records if r.company_name == "XYZ Solutions")
    assert xyz_job.number_of_people == "1,250 employees"

    data_job = next(r for r in processed_records if r.company_name == "Global Data Corp")
    assert data_job.number_of_people == "1,200 employees"

    startup_job = next(r for r in processed_records if r.company_name == "Startup Ventures")
    assert startup_job.number_of_people == "N/A"

    # 4. Verify Pagination Detection on fixture
    soup = BeautifulSoup(html_content, "lxml")
    next_page = PaginationHandler.find_next_page_url(soup, base_url, set())
    assert next_page == "https://example.com/jobs?page=2"

    # 5. Excel Generation
    stats = ExtractionStats(
        pages_processed=1,
        jobs_discovered=len(raw_records),
        jobs_processed=len(processed_records),
        companies_discovered=len(unique_companies),
        duplicates_removed=deduplicator.duplicates_count,
        missing_employee_counts=missing_emp_count,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        excel_path = os.path.join(temp_dir, "jobs.xlsx")
        out = ExcelExporter.export(
            records=processed_records,
            stats=stats,
            source_url=base_url,
            output_path=excel_path,
        )
        assert os.path.exists(out)
        assert os.path.getsize(out) > 0
