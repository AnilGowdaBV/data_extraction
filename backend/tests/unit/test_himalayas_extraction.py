import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.models.job import ProcessedJobRecord
from backend.app.scraper.crawler import JobCrawler
from backend.app.scraper.browser import BrowserManager
from backend.app.db.repository import JobRepository
from backend.app.utils.date_helpers import unix_to_himalayas_age


def test_himalayas_date_formatting() -> None:
    # 259200 seconds = 3 days
    import time
    now_ts = time.time()
    three_days_ts = now_ts - (3 * 86400)
    assert unix_to_himalayas_age(three_days_ts) == "3 days ago"

    eleven_days_ts = now_ts - (11 * 86400)
    assert unix_to_himalayas_age(eleven_days_ts) == "11 days ago"

    one_day_ts = now_ts - (86400 + 3600)
    assert unix_to_himalayas_age(one_day_ts) == "1 day ago"


@pytest.mark.asyncio
async def test_crawl_himalayas_api_extracts_people_and_date(tmp_path: str) -> None:
    db_path = str(tmp_path) + "/test_himalayas.db"
    repo = JobRepository(db_path=db_path)
    browser_manager = MagicMock(spec=BrowserManager)
    crawler = JobCrawler(browser_manager=browser_manager, repository=repo)

    mock_jobs_data = {
        "jobs": [
            {
                "title": "Altium Designer Specialist",
                "companyName": "micro1",
                "companySlug": "micro1",
                "guid": "https://himalayas.app/companies/micro1/jobs/altium-designer-specialist",
                "applicationLink": "https://himalayas.app/companies/micro1/jobs/altium-designer-specialist",
                "pubDate": 1790652086,
            },
            {
                "title": "Trainee Health and Social Care Assessor",
                "companyName": "T2 Group",
                "companySlug": "t2-group",
                "guid": "https://himalayas.app/companies/t2-group/jobs/trainee-health",
                "applicationLink": "https://himalayas.app/companies/t2-group/jobs/trainee-health",
                "pubDate": 1790652086,
            }
        ]
    }

    mock_mcp_response = MagicMock()
    mock_mcp_response.status_code = 200
    mock_mcp_response.text = 'data: {"result":{"content":[{"type":"text","text":"# micro1\\n\\n**Size:** 11-50\\n"}]}}\n'

    mock_api_response = MagicMock()
    mock_api_response.status_code = 200
    mock_api_response.json.return_value = mock_jobs_data

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        
        mock_get.return_value = mock_api_response
        mock_post.return_value = mock_mcp_response

        records = await crawler._crawl_himalayas_api(
            start_url="https://himalayas.app/jobs?page=4",
            max_records=2,
        )

        assert len(records) >= 1
        micro1_rec = next((r for r in records if r.company_name == "micro1"), None)
        assert micro1_rec is not None
        assert micro1_rec.number_of_people == "11-50"
        assert micro1_rec.posted_date != "Unknown"
        assert "ago" in micro1_rec.posted_date or micro1_rec.posted_date == "Today"
