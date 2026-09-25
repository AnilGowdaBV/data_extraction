"""Core crawler orchestrating page traversal, autonomous extraction, and live stats."""

import asyncio
from typing import Callable, Coroutine, List, Optional, Set
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.db.repository import JobRepository
from backend.app.extractors.company_extractor import CompanyExtractor
from backend.app.extractors.employee_extractor import EmployeeCountExtractor
from backend.app.extractors.job_extractor import JobExtractor
from backend.app.models.job import ExtractionStats, ProcessedJobRecord
from backend.app.processors.cleaner import DataCleaner
from backend.app.processors.deduplicator import JobDeduplicator
from backend.app.processors.validator import DataValidator
from backend.app.scraper.browser import BrowserManager
from backend.app.scraper.discovery import UrlDiscoverySecurity
from backend.app.scraper.pagination import PaginationHandler
from backend.app.utils.date_helpers import (
    iso_str_to_age_label,
    source_date_to_age_label,
    unix_to_age_label,
)

logger = get_logger(__name__)


class JobCrawler:
    INSTAHYRE_INDUSTRY_ID = 13  # Computer Software / IT / Internet
    ENGINEERING_ROLE_TERMS = (
        "engineer",
        "developer",
        "software",
        "backend",
        "frontend",
        "full stack",
        "full-stack",
        "devops",
        "sre",
        "programmer",
        "qa engineer",
        "test engineer",
        "technical architect",
    )

    @classmethod
    def _is_engineering_job(cls, job: dict) -> bool:
        """Keep developer and software-engineering roles from Himalayas results."""
        parent_categories = {str(value).lower() for value in job.get("parentCategories", [])}
        if parent_categories.intersection({"developer", "engineering", "software engineering"}):
            return True

        searchable_text = " ".join(
            [
                str(job.get("title") or ""),
                *(str(value) for value in job.get("categories", [])),
            ]
        ).lower().replace("-", " ")
        return any(term in searchable_text for term in cls.ENGINEERING_ROLE_TERMS)

    """
    Crawls job boards across pagination, load-more, infinite scroll, and public APIs.
    Extracts, normalizes, deduplicates, and caches company employee counts in memory.
    """

    def __init__(
        self,
        browser_manager: BrowserManager,
        repository: Optional[JobRepository] = None,
    ) -> None:
        self.browser_manager = browser_manager
        self.repository = repository or JobRepository()
        self.deduplicator = JobDeduplicator()
        self.company_extractor = CompanyExtractor()
        self.visited_urls: Set[str] = set()
        self.stats = ExtractionStats()
        self._is_stopped = False

    def stop(self) -> None:
        """Signal crawler to stop traversing further pages."""
        self._is_stopped = True
        self.stats.current_action = "Stopping extraction as requested..."
        logger.info("Crawler received stop signal.")

    async def crawl(
        self,
        start_url: str,
        max_records: int = 100000,
        max_pages: int = 1000,
        on_progress: Optional[Callable[[ExtractionStats], Coroutine[None, None, None]]] = None,
    ) -> List[ProcessedJobRecord]:
        """
        Execute full extraction run starting at start_url until dataset exhausted
        or safety limit reached.
        """
        self._is_stopped = False
        self.visited_urls.clear()
        self.deduplicator.reset()
        self.company_extractor.clear()
        self.stats = ExtractionStats()

        clean_url = UrlDiscoverySecurity.validate_url(start_url)

        # Autonomous check: If target is himalayas.app, use its public API stream directly
        if "himalayas.app" in clean_url:
            logger.info("Detected himalayas.app target. Engaging public job stream...")
            return await self._crawl_himalayas_api(
                max_records=max_records,
                on_progress=on_progress,
            )

        # Autonomous check: If target is instahyre.com, use its high-speed public job stream directly
        if "instahyre.com" in clean_url:
            logger.info("Detected instahyre.com target. Engaging high-speed public job stream...")
            return await self._crawl_instahyre_api(
                start_url=clean_url,
                max_records=max_records,
                on_progress=on_progress,
            )

        processed_records: List[ProcessedJobRecord] = []
        unique_companies: Set[str] = set()

        current_url: Optional[str] = clean_url
        page_num = 0
        consecutive_empty_attempts = 0

        # Helper to fetch company profile HTML when needed
        async def fetch_company_profile(profile_url: str) -> Optional[str]:
            try:
                if UrlDiscoverySecurity.is_in_scope(profile_url, clean_url):
                    return await self.browser_manager.fetch_page_content(profile_url)
            except Exception as e:
                logger.warning("Failed company profile fetch: %s", e)
            return None

        # Main traversal loop
        while current_url and page_num < max_pages and not self._is_stopped:
            if len(processed_records) >= max_records:
                logger.info("Reached maximum record limit (%d). Stopping.", max_records)
                break

            page_num += 1
            self.stats.pages_processed = page_num
            self.stats.current_action = f"Opening page {page_num} ({current_url})..."
            if on_progress:
                await on_progress(self.stats)

            self.visited_urls.add(current_url)

            try:
                html_content = await self.browser_manager.fetch_page_content(current_url)
            except Exception as e:
                logger.warning("Failed to load page %s: %s", current_url, e)
                self.stats.current_action = f"Navigation issue on page {page_num}: {e}"
                break

            soup = BeautifulSoup(html_content, "lxml")

            # 2. Extract job records from current page
            self.stats.current_action = (
                f"Analyzing page {page_num} structure and extracting jobs..."
            )
            if on_progress:
                await on_progress(self.stats)

            raw_jobs = JobExtractor.extract_from_html(html_content, base_url=current_url)
            self.stats.jobs_discovered += len(raw_jobs)
            logger.info("Page %d yielded %d candidate jobs", page_num, len(raw_jobs))

            # 3. Process each raw job
            for raw_job in raw_jobs:
                if self._is_stopped or len(processed_records) >= max_records:
                    break

                clean_company = DataCleaner.clean_company_name(raw_job.company_name)
                clean_role = DataCleaner.clean_job_role(raw_job.job_role)

                # Deduplication check
                if self.deduplicator.is_duplicate(clean_company, clean_role, raw_job.job_url):
                    self.stats.duplicates_removed = self.deduplicator.duplicates_count
                    continue

                # Employee count resolution
                emp_count = "N/A"
                if raw_job.employee_count_raw:
                    emp_count = EmployeeCountExtractor.parse_count(raw_job.employee_count_raw)

                company_url = raw_job.company_url

                # If fields from card are incomplete or invalid, follow job detail link when available
                if (
                    not DataValidator.is_valid_company(clean_company)
                    or not DataValidator.is_valid_role(clean_role)
                ) and raw_job.job_url:
                    if UrlDiscoverySecurity.is_in_scope(raw_job.job_url, clean_url):
                        try:
                            logger.info(
                                "Following job detail page for deeper extraction: %s",
                                raw_job.job_url,
                            )
                            detail_html = await self.browser_manager.fetch_page_content(
                                raw_job.job_url
                            )
                            if detail_html:
                                detail_rec = JobExtractor.extract_from_detail_html(
                                    detail_html, raw_job.job_url
                                )
                                if detail_rec:
                                    clean_company = DataCleaner.clean_company_name(
                                        detail_rec.company_name
                                    )
                                    clean_role = DataCleaner.clean_job_role(detail_rec.job_role)
                                    if detail_rec.company_url:
                                        company_url = detail_rec.company_url
                                    if detail_rec.employee_count_raw and emp_count == "N/A":
                                        emp_count = EmployeeCountExtractor.parse_count(
                                            detail_rec.employee_count_raw
                                        )
                        except Exception as e:
                            logger.warning(
                                "Failed detail page extraction for %s: %s", raw_job.job_url, e
                            )

                # If missing from card, try cached company lookup or profile page
                if emp_count == "N/A":
                    emp_count = await self.company_extractor.resolve_employee_count(
                        company_name=clean_company,
                        company_profile_url=company_url,
                        profile_fetcher=fetch_company_profile,
                    )

                if emp_count == "N/A":
                    self.stats.missing_employee_counts += 1

                # Validation
                if DataValidator.is_valid_record(clean_company, clean_role, emp_count):
                    db_id, is_new, first_seen_at = self.repository.register_job(
                        company_name=clean_company,
                        job_role=clean_role,
                        number_of_people=emp_count,
                        job_url=raw_job.job_url,
                        source_website=clean_url,
                    )
                    if is_new:
                        self.stats.new_jobs_added += 1
                    else:
                        self.stats.existing_jobs_seen += 1

                    record = ProcessedJobRecord(
                        company_name=clean_company,
                        job_role=clean_role,
                        number_of_people=emp_count,
                        job_url=raw_job.job_url,
                        is_new=is_new,
                        db_id=db_id,
                        posted_date=iso_str_to_age_label(first_seen_at),
                    )
                    processed_records.append(record)
                    self.stats.jobs_processed = len(processed_records)
                    self.stats.recent_jobs = [rec.to_dict() for rec in processed_records[-25:]]

                    norm_comp = DataCleaner.normalize_key(clean_company)
                    if norm_comp not in unique_companies:
                        unique_companies.add(norm_comp)
                        self.stats.companies_discovered = len(unique_companies)

            if on_progress:
                await on_progress(self.stats)

            # Track whether this iteration discovered new records
            if not raw_jobs:
                consecutive_empty_attempts += 1
            else:
                consecutive_empty_attempts = 0

            if consecutive_empty_attempts >= 3:
                logger.info("3 consecutive attempts yielded 0 new records. Concluding crawl.")
                current_url = None
                continue

            # 4. Check Pagination: Next Page link
            next_url = PaginationHandler.find_next_page_url(soup, current_url, self.visited_urls)
            if next_url and UrlDiscoverySecurity.is_in_scope(next_url, clean_url):
                logger.info("Found next page link: %s", next_url)
                current_url = next_url
                continue

            # No further pagination found
            logger.info("No further pagination detected on %s.", current_url)
            current_url = None

        self.stats.current_action = (
            f"Extraction completed. Total jobs extracted: {len(processed_records)}"
        )
        if on_progress:
            await on_progress(self.stats)

        return processed_records

    async def _crawl_himalayas_api(
        self,
        max_records: int,
        on_progress: Optional[Callable[[ExtractionStats], Coroutine[None, None, None]]] = None,
    ) -> List[ProcessedJobRecord]:
        """Direct stream extractor for Himalayas public job API dataset."""
        processed_records: List[ProcessedJobRecord] = []
        unique_companies: Set[str] = set()
        offset = 0
        limit = 20
        parallel_pages = 2
        page_num = 0

        async with httpx.AsyncClient(timeout=20.0) as client:
            while not self._is_stopped and len(processed_records) < max_records:
                page_offsets = [offset + (index * limit) for index in range(parallel_pages)]
                page_num += len(page_offsets)
                self.stats.pages_processed = page_num
                self.stats.current_action = (
                    f"Streaming records from Himalayas API (Offsets: {offset}-{page_offsets[-1]})..."
                )
                if on_progress:
                    await on_progress(self.stats)

                try:
                    while True:
                        responses = await asyncio.gather(
                            *(
                                client.get(
                                    f"https://himalayas.app/jobs/api?offset={page_offset}&limit={limit}",
                                    headers={"User-Agent": "Mozilla/5.0"},
                                )
                                for page_offset in page_offsets
                            )
                        )
                        rate_limited = [response for response in responses if response.status_code == 429]
                        if not rate_limited:
                            break

                        retry_after = max(
                            [int(response.headers.get("retry-after", "0")) for response in rate_limited]
                            + [60]
                        )
                        logger.warning(
                            "Himalayas rate limit hit. Retrying offsets %d-%d after %ds.",
                            page_offsets[0],
                            page_offsets[-1],
                            retry_after,
                        )
                        self.stats.current_action = (
                            f"Himalayas rate limit pause ({retry_after}s) before retrying..."
                        )
                        if on_progress:
                            await on_progress(self.stats)
                        await asyncio.sleep(retry_after)

                    raw_jobs = []
                    for page_offset, resp in zip(page_offsets, responses):
                        if resp.status_code != 200:
                            logger.warning(
                                "Himalayas API returned status %s at offset %d",
                                resp.status_code,
                                page_offset,
                            )
                            continue
                        raw_jobs.extend(resp.json().get("jobs", []))

                    if not raw_jobs:
                        logger.info("No further jobs returned from Himalayas API.")
                        break

                    jobs = [job for job in raw_jobs if self._is_engineering_job(job)]

                    self.stats.jobs_discovered += len(jobs)

                    for j in jobs:
                        if self._is_stopped or len(processed_records) >= max_records:
                            break

                        company_raw = j.get("companyName")
                        role_raw = j.get("title")
                        job_url = j.get("applicationLink") or j.get("guid")
                        pub_date_raw = j.get("pubDate")  # Unix timestamp int from Himalayas API

                        clean_company = DataCleaner.clean_company_name(company_raw)
                        clean_role = DataCleaner.clean_job_role(role_raw)

                        if self.deduplicator.is_duplicate(clean_company, clean_role, job_url):
                            self.stats.duplicates_removed = self.deduplicator.duplicates_count
                            continue

                        # Strict N/A when employee count is absent on listing
                        emp_count = "N/A"
                        self.stats.missing_employee_counts += 1

                        # Derive posted_date: prefer actual publish timestamp from API
                        if pub_date_raw:
                            posted_date = unix_to_age_label(int(pub_date_raw))
                        else:
                            posted_date = "Unknown"

                        if DataValidator.is_valid_record(clean_company, clean_role, emp_count):
                            db_id, is_new, first_seen_at = self.repository.register_job(
                                company_name=clean_company,
                                job_role=clean_role,
                                number_of_people=emp_count,
                                job_url=job_url,
                                source_website="himalayas.app",
                            )
                            if is_new:
                                self.stats.new_jobs_added += 1
                            else:
                                self.stats.existing_jobs_seen += 1

                            # For existing jobs where we stored a real pub_date, keep it;
                            # otherwise fall back to our first_seen_at from DB
                            if posted_date == "Unknown":
                                posted_date = iso_str_to_age_label(first_seen_at)

                            rec = ProcessedJobRecord(
                                company_name=clean_company,
                                job_role=clean_role,
                                number_of_people=emp_count,
                                job_url=job_url,
                                is_new=is_new,
                                db_id=db_id,
                                posted_date=posted_date,
                            )
                            processed_records.append(rec)
                            self.stats.jobs_processed = len(processed_records)
                            self.stats.recent_jobs = [r.to_dict() for r in processed_records[-25:]]

                            norm_comp = DataCleaner.normalize_key(clean_company)
                            if norm_comp not in unique_companies:
                                unique_companies.add(norm_comp)
                                self.stats.companies_discovered = len(unique_companies)

                    offset += len(raw_jobs)
                    if on_progress:
                        await on_progress(self.stats)

                    # Controlled delay between batch requests
                    await asyncio.sleep(settings.REQUEST_DELAY_MS / 1000.0)

                except Exception as e:
                    logger.error("Himalayas API fetch failed at offset %d: %s", offset, e)
                    break

        self.stats.current_action = (
            f"Extraction completed. Total jobs extracted: {len(processed_records)}"
        )
        if on_progress:
            await on_progress(self.stats)

        return processed_records

    async def _crawl_instahyre_api(
        self,
        start_url: str,
        max_records: int,
        on_progress: Optional[Callable[[ExtractionStats], Coroutine[None, None, None]]] = None,
    ) -> List[ProcessedJobRecord]:
        """
        High-speed public stream extractor for Instahyre job dataset.
        Segments across company size buckets [1, 2, 3] (Small, Large, Medium)
        to cleanly retrieve all 13,350+ jobs without hitting Elasticsearch's 10,000-window cutoff.
        """
        processed_records: List[ProcessedJobRecord] = []
        unique_companies: Set[str] = set()
        page_num = 0
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }

        # Check if user specified a specific company_size in start_url
        parsed = urlparse(start_url)
        params = parse_qs(parsed.query)
        user_cs = params.get("company_size", [None])[0]
        if user_cs and user_cs != "0":
            company_sizes = [int(user_cs)]
        else:
            # 1: Small (~3,877), 2: Large (~7,264), 3: Medium (~2,211) -> 13,352 total
            company_sizes = [1, 2, 3]

        bucket_labels = {1: "Small", 2: "Large", 3: "Medium"}
        offsets = {cs: 0 for cs in company_sizes}
        exhausted = {cs: False for cs in company_sizes}

        async with httpx.AsyncClient(timeout=25.0, headers=headers) as client:
            while not self._is_stopped and len(processed_records) < max_records:
                if all(exhausted.values()):
                    break

                for cs in company_sizes:
                    if self._is_stopped or len(processed_records) >= max_records:
                        break
                    if exhausted[cs]:
                        continue

                    offset = offsets[cs]
                    cs_label = bucket_labels.get(cs, f"Size {cs}")
                    page_num += 1
                    self.stats.pages_processed = page_num
                    self.stats.current_action = f"Streaming Instahyre {cs_label} companies (Offset {offset}, Total: {len(processed_records)} jobs)..."
                    if on_progress:
                        await on_progress(self.stats)

                    api_url = (
                        f"https://www.instahyre.com/api/v1/job_search?"
                        f"company_size={cs}&industry_type={self.INSTAHYRE_INDUSTRY_ID}"
                        f"&isLandingPage=true&job_type=0&limit=100&offset={offset}"
                    )
                    data = None
                    request_attempt = 0

                    # Instahyre rate-limits rapid pagination; wait and retry the same batch.
                    while data is None and not self._is_stopped:
                        request_attempt += 1
                        try:
                            resp = await client.get(api_url)
                            if resp.status_code == 200:
                                data = resp.json()
                            elif resp.status_code == 429:
                                try:
                                    retry_after_seconds = int(resp.headers.get("retry-after", "0"))
                                except ValueError:
                                    retry_after_seconds = 0
                                wait_sec = max(60, retry_after_seconds)
                                logger.info(
                                    "Instahyre rate limit hit (429). Pausing for %ds before retrying the same batch...",
                                    wait_sec,
                                )
                                self.stats.current_action = f"Rate limit pause ({int(wait_sec)}s) before fetching next batch..."
                                if on_progress:
                                    await on_progress(self.stats)
                                await asyncio.sleep(wait_sec)
                            else:
                                logger.warning(
                                    "Instahyre API returned status %s at offset %d (bucket %s)",
                                    resp.status_code,
                                    offset,
                                    cs,
                                )
                                break
                        except Exception as req_err:
                            logger.warning(
                                "Instahyre request error at offset %d: %s. Retrying...",
                                offset,
                                req_err,
                            )
                            if request_attempt >= 5:
                                break
                            await asyncio.sleep(2.0)

                    if not data:
                        exhausted[cs] = True
                        continue

                    objs = data.get("objects", [])
                    if not objs:
                        exhausted[cs] = True
                        continue

                    self.stats.jobs_discovered += len(objs)

                    for obj in objs:
                        if self._is_stopped or len(processed_records) >= max_records:
                            break

                        employer = obj.get("employer") or {}
                        comp_raw = employer.get("company_name")
                        role_raw = obj.get("title") or obj.get("candidate_title")
                        emp_raw = employer.get("employee_count")
                        job_url = obj.get("public_url")
                        source_posted_date = next(
                            (
                                source_date_to_age_label(obj.get(key))
                                for key in (
                                    "posted_at",
                                    "posted_on",
                                    "posted_date",
                                    "published_at",
                                    "published_on",
                                    "publish_date",
                                    "date_posted",
                                    "created_at",
                                    "created_on",
                                    "created_date",
                                )
                                if obj.get(key) is not None
                            ),
                            None,
                        )

                        clean_comp = DataCleaner.clean_company_name(comp_raw)
                        clean_role = DataCleaner.clean_job_role(role_raw)

                        if self.deduplicator.is_duplicate(clean_comp, clean_role, job_url):
                            self.stats.duplicates_removed = self.deduplicator.duplicates_count
                            continue

                        emp_count = (
                            EmployeeCountExtractor.parse_count(str(emp_raw))
                            if emp_raw is not None
                            else "N/A"
                        )
                        if emp_count == "N/A":
                            self.stats.missing_employee_counts += 1

                        if DataValidator.is_valid_record(clean_comp, clean_role, emp_count):
                            db_id, is_new, first_seen_at = self.repository.register_job(
                                company_name=clean_comp,
                                job_role=clean_role,
                                number_of_people=emp_count,
                                job_url=job_url,
                                source_website="instahyre.com",
                            )
                            if is_new:
                                self.stats.new_jobs_added += 1
                            else:
                                self.stats.existing_jobs_seen += 1

                            r = ProcessedJobRecord(
                                company_name=clean_comp,
                                job_role=clean_role,
                                number_of_people=emp_count,
                                job_url=job_url,
                                is_new=is_new,
                                db_id=db_id,
                                posted_date=source_posted_date or iso_str_to_age_label(first_seen_at),
                            )
                            processed_records.append(r)
                            self.stats.jobs_processed = len(processed_records)
                            self.stats.recent_jobs = [
                                rec.to_dict() for rec in processed_records[-25:]
                            ]

                            norm_comp = DataCleaner.normalize_key(clean_comp)
                            if norm_comp not in unique_companies:
                                unique_companies.add(norm_comp)
                                self.stats.companies_discovered = len(unique_companies)

                    offsets[cs] += len(objs)
                    if on_progress:
                        await on_progress(self.stats)

                    # Check if next URL is provided in metadata
                    meta_next = data.get("meta", {}).get("next")
                    if not meta_next:
                        exhausted[cs] = True

                    await asyncio.sleep(1.0)

        self.stats.current_action = (
            f"Extraction completed. Total jobs extracted: {len(processed_records)}"
        )
        if on_progress:
            await on_progress(self.stats)

        return processed_records
