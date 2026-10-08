"""Unit tests for GoogleSheetsExporter."""

from unittest.mock import AsyncMock, patch
import pytest
from datetime import datetime

from backend.app.exporters.google_sheets import GoogleSheetsExporter
from backend.app.models.job import ProcessedJobRecord


@pytest.fixture
def sample_jobs():
    return [
        ProcessedJobRecord(
            company_name="Google",
            job_role="Software Engineer",
            number_of_people="100,000+",
            posted_by="Jane Doe (Lead Recruiter, Google)",
            first_seen_at="2026-10-08T09:30:00+05:30",
            location="Bengaluru, India",
        ),
        ProcessedJobRecord(
            company_name="Microsoft",
            job_role="Cloud Architect",
            number_of_people="50,000+",
            posted_by="John Smith (HR, Microsoft)",
            first_seen_at="2026-10-08T14:45:00+05:30",
            location="Hyderabad, India",
        ),
        ProcessedJobRecord(
            company_name="Amazon",
            job_role="Backend Developer",
            number_of_people="1,000+",
            posted_by="Alice (Talent Acquisition, Amazon)",
            first_seen_at="2026-09-24T10:00:00+05:30",
            location="Bengaluru, India",
        ),
    ]


@pytest.mark.asyncio
async def test_sync_jobs_empty():
    result = await GoogleSheetsExporter.sync_jobs_to_sheet([])
    assert result["success"] is True
    assert result["synced_count"] == 0


@pytest.mark.asyncio
async def test_same_day_scrapes_target_same_tab(sample_jobs):
    """Verifies morning and afternoon/evening scrapes on the same day target the exact same date tab."""
    morning_job = sample_jobs[:1]
    evening_job = sample_jobs[1:2]

    now_local = datetime.now().astimezone()
    expected_tab = f"{now_local.strftime('%b')} {now_local.day}"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Morning scrape
        res1 = await GoogleSheetsExporter.sync_jobs_to_sheet(morning_job)
        assert res1["success"] is True
        assert res1["sheet_name"] == expected_tab

        # Evening scrape on the same day
        res2 = await GoogleSheetsExporter.sync_jobs_to_sheet(evening_job)
        assert res2["success"] is True
        assert res2["sheet_name"] == expected_tab

        # Both targeted the exact same tab name (e.g. "Oct 8")
        assert res1["sheet_name"] == res2["sheet_name"]
        assert mock_post.call_count == 2
        call_payloads = [c.kwargs["json"] for c in mock_post.call_args_list]
        assert call_payloads[0]["sheet_name"] == expected_tab
        assert call_payloads[1]["sheet_name"] == expected_tab


@pytest.mark.asyncio
async def test_sync_all_jobs_by_date_grouping(sample_jobs):
    """Verifies that jobs across multiple days are grouped by their first_seen_at date."""
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        res = await GoogleSheetsExporter.sync_all_jobs_by_date(sample_jobs)
        assert res["success"] is True
        assert res["total_synced"] == 3
        # Should have tabs for Sep 24 and Oct 8
        tabs = res["date_tabs"]
        assert "Sep 24" in tabs
        assert "Oct 8" in tabs
        assert tabs["Sep 24"] == 1
        assert tabs["Oct 8"] == 2
