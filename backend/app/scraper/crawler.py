"""Core crawler orchestrating page traversal, autonomous extraction, and live stats."""

import asyncio
import json
import re
from typing import Callable, Coroutine, List, Optional, Set
from urllib.parse import parse_qs, quote, urlencode, urlparse

import httpx
from bs4 import BeautifulSoup

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.db.repository import JobRepository
from backend.app.extractors.company_extractor import CompanyExtractor
from backend.app.extractors.employee_extractor import EmployeeCountExtractor
from backend.app.extractors.job_extractor import JobExtractor
from backend.app.models.categories import is_eligible_company_size
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
    unix_to_himalayas_age,
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
        self.processed_records: List[ProcessedJobRecord] = []
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
        self.processed_records = []

        clean_url = UrlDiscoverySecurity.validate_url(start_url)

        # Autonomous check: If target is himalayas.app, use its public API stream directly
        if "himalayas.app" in clean_url:
            logger.info("Detected himalayas.app target. Engaging public job stream...")
            return await self._crawl_himalayas_api(
                start_url=clean_url,
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
        await self.browser_manager.initialize()

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

                if str(emp_count).strip() in ("N/A", "Unknown", "", "None"):
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
        start_url: str = "",
        max_records: int = 100000,
        on_progress: Optional[Callable[[ExtractionStats], Coroutine[None, None, None]]] = None,
    ) -> List[ProcessedJobRecord]:
        """Direct stream extractor for Himalayas public job API dataset."""
        processed_records: List[ProcessedJobRecord] = []
        unique_companies: Set[str] = set()
        offset = 0
        limit = 20
        parallel_pages = 2
        page_num = 0
        total_api_count: Optional[int] = None

        search_query: Optional[str] = None
        if start_url:
            try:
                parsed = urlparse(start_url)
                qs = parse_qs(parsed.query)
                if "offset" in qs and qs["offset"][0].isdigit():
                    offset = int(qs["offset"][0])
                elif "page" in qs and qs["page"][0].isdigit():
                    p = max(1, int(qs["page"][0]))
                    offset = (p - 1) * limit
                    page_num = p - 1

                # Detect keyword search from query params or URL subpath
                if "q" in qs and qs["q"][0]:
                    search_query = qs["q"][0].strip()
                elif "aiq" in qs and qs["aiq"][0]:
                    search_query = qs["aiq"][0].strip()
                elif "query" in qs and qs["query"][0]:
                    search_query = qs["query"][0].strip()
                else:
                    path_parts = [part for part in parsed.path.strip("/").split("/") if part]
                    if len(path_parts) >= 2 and path_parts[0] == "jobs":
                        sub = path_parts[1].lower()
                        if sub not in ("api", "search", "all"):
                            search_query = sub.replace("-", " ")
            except Exception as pe:
                logger.warning("Error parsing start_url %s: %s", start_url, pe)

        # Preload cached company sizes from database
        company_sizes: dict[str, str] = self.repository.get_all_company_profiles()

        async def _fetch_company_size_mcp(mcp_client: httpx.AsyncClient, slug: str) -> tuple[str, str]:
            if not slug:
                return (slug, "N/A")
            try:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "get_company_details", "arguments": {"company_slug": slug}},
                }
                resp = await mcp_client.post(
                    "https://mcp.himalayas.app/mcp",
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                        "User-Agent": "Mozilla/5.0",
                    },
                    timeout=8.0,
                )
                if resp.status_code == 200:
                    for line in resp.text.split("\n"):
                        if line.startswith("data: "):
                            data = json.loads(line[6:])
                            text = data.get("result", {}).get("content", [{}])[0].get("text", "")
                            m = re.search(r"\*\*Size:\*\*\s*([^\n\r]+)", text)
                            if m:
                                val = m.group(1).strip()
                                if val.lower() not in ("not specified", "unknown", "n/a", "none"):
                                    return (slug, val)
            except Exception:
                pass
            return (slug, "N/A")

        target_desc = f"'{search_query}' jobs" if search_query else "jobs"

        async with httpx.AsyncClient(timeout=20.0) as client:
            while not self._is_stopped and len(processed_records) < max_records:
                page_offsets = [offset + (index * limit) for index in range(parallel_pages)]
                page_num += len(page_offsets)
                self.stats.pages_processed = page_num
                self.stats.current_action = (
                    f"Streaming {target_desc} from Himalayas API (Offsets: {offset}-{page_offsets[-1]})..."
                )
                if on_progress:
                    await on_progress(self.stats)

                try:
                    def _build_api_url(page_off: int) -> str:
                        if search_query:
                            return f"https://himalayas.app/jobs/api/search?q={quote(search_query)}&offset={page_off}&limit={limit}"
                        return f"https://himalayas.app/jobs/api?offset={page_off}&limit={limit}"

                    while True:
                        responses = await asyncio.gather(
                            *(
                                client.get(
                                    _build_api_url(page_offset),
                                    headers={"User-Agent": "Mozilla/5.0"},
                                )
                                for page_offset in page_offsets
                            )
                        )
                        rate_limited = [response for response in responses if response.status_code == 429]
                        if not rate_limited:
                            break

                        retry_after = min(
                            max([int(response.headers.get("retry-after", "0")) for response in rate_limited] + [5]),
                            15,
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

                        for _ in range(int(retry_after * 2)):
                            if self._is_stopped:
                                break
                            await asyncio.sleep(0.5)

                        if self._is_stopped:
                            break

                    raw_jobs = []
                    for page_offset, resp in zip(page_offsets, responses):
                        if resp.status_code != 200:
                            logger.warning(
                                "Himalayas API returned status %s at offset %d",
                                resp.status_code,
                                page_offset,
                            )
                            continue
                        data = resp.json()
                        if total_api_count is None and data.get("totalCount") is not None:
                            total_api_count = data.get("totalCount")
                            logger.info("Himalayas reported total result count: %d", total_api_count)
                        raw_jobs.extend(data.get("jobs", []))

                    if not raw_jobs:
                        logger.info("No further jobs returned from Himalayas API.")
                        break

                    if total_api_count is not None and offset >= total_api_count:
                        logger.info("Offset %d reached total reported count %d. Completing search crawl.", offset, total_api_count)
                        break

                    # Extract all cards
                    jobs = raw_jobs
                    self.stats.jobs_discovered += len(jobs)

                    # Resolve company sizes concurrently for any unseen company slugs
                    batch_slug_map = {
                        j.get("companySlug"): j.get("companyName")
                        for j in jobs
                        if j.get("companySlug")
                    }
                    missing_slugs = [slug for slug in batch_slug_map if slug not in company_sizes]
                    if missing_slugs:
                        size_results = await asyncio.gather(*(
                            _fetch_company_size_mcp(client, slug)
                            for slug in missing_slugs
                        ))
                        for slug, size in size_results:
                            company_sizes[slug] = size
                            comp_name = batch_slug_map.get(slug) or slug
                            self.repository.save_company_employee_count(slug, comp_name, size)

                    for j in jobs:
                        if self._is_stopped or len(processed_records) >= max_records:
                            break

                        company_raw = j.get("companyName")
                        role_raw = j.get("title")
                        job_url = j.get("applicationLink") or j.get("guid")
                        pub_date_raw = j.get("pubDate")  # Unix timestamp int from Himalayas API
                        company_slug = j.get("companySlug")

                        clean_company = DataCleaner.clean_company_name(company_raw)
                        clean_role = DataCleaner.clean_job_role(role_raw)

                        if self.deduplicator.is_duplicate(clean_company, clean_role, job_url):
                            self.stats.duplicates_removed = self.deduplicator.duplicates_count
                            continue

                        # Resolve employee count
                        emp_count = company_sizes.get(company_slug) or "N/A"
                        if str(emp_count).strip() in ("N/A", "Unknown", "", "None"):
                            self.stats.missing_employee_counts += 1

                        # Derive accurate Himalayas posted date relative label (e.g. '11 days ago', '1 day ago', '5 days ago')
                        if pub_date_raw:
                            posted_date = unix_to_himalayas_age(pub_date_raw)
                        else:
                            posted_date = "Unknown"

                        if DataValidator.is_valid_record(clean_company, clean_role, emp_count):
                            db_id, is_new, first_seen_at = self.repository.register_job(
                                company_name=clean_company,
                                job_role=clean_role,
                                number_of_people=emp_count,
                                job_url=job_url,
                                source_website="himalayas.app",
                                posted_date=posted_date,
                                published_at=pub_date_raw,
                            )
                            if is_new:
                                self.stats.new_jobs_added += 1
                            else:
                                self.stats.existing_jobs_seen += 1

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
                            self.processed_records = processed_records
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
        High-speed stream extractor for Instahyre job dataset.
        Extracts up to 8,063+ active jobs with live rate-limit cooldown management,
        preserving user filters (industry, company size, functions, locations).
        """
        processed_records: List[ProcessedJobRecord] = []
        self.processed_records = processed_records
        unique_companies: Set[str] = set()
        page_num = 0

        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
        ]

        def get_headers(attempt_idx: int) -> dict[str, str]:
            ua = user_agents[attempt_idx % len(user_agents)]
            return {
                "User-Agent": ua,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.instahyre.com/search-jobs/",
                "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }

        # Parse user query params from input URL
        parsed = urlparse(start_url)
        params = parse_qs(parsed.query)

        # Build query string forwarding user filters (industry_types, company_size, etc.)
        query_dict: dict[str, str] = {
            "isLandingPage": "true",
            "job_type": "0",
            "limit": "20",
        }

        # Forward all user-supplied query filters
        for k, v in params.items():
            if k not in ("offset", "limit"):
                query_dict[k] = v[0] if len(v) == 1 else ",".join(v)

        # Default to industry_types=13 (Software / IT) if neither is set
        if "industry_types" not in query_dict and "industry_type" not in query_dict:
            query_dict["industry_types"] = "13"
        if "company_size" not in query_dict:
            query_dict["company_size"] = "0"

        offset = 0
        total_target_jobs: Optional[int] = None

        async with httpx.AsyncClient(timeout=25.0, headers=get_headers(0)) as client:
            while not self._is_stopped and len(processed_records) < max_records:
                query_dict["offset"] = str(offset)
                encoded_params = urlencode(query_dict)
                api_url = f"https://www.instahyre.com/api/v1/job_search?{encoded_params}"

                page_num += 1
                self.stats.pages_processed = page_num
                target_str = f" of {total_target_jobs}" if total_target_jobs else ""
                self.stats.current_action = (
                    f"Streaming Instahyre jobs (Offset {offset}{target_str}, Extracted: {len(processed_records)})..."
                )
                if on_progress:
                    await on_progress(self.stats)

                data = None
                request_attempt = 0

                while data is None and not self._is_stopped:
                    request_attempt += 1
                    try:
                        req_headers = get_headers(page_num + request_attempt)
                        resp = await client.get(api_url, headers=req_headers)

                        if resp.status_code == 200:
                            data = resp.json()
                        elif resp.status_code == 429:
                            # Instahyre returns a ~42s rate-limit window when burst limit is hit.
                            # Countdown politely and resume automatically without losing place!
                            retry_after_str = resp.headers.get("retry-after", "45")
                            try:
                                retry_after = int(retry_after_str)
                            except ValueError:
                                retry_after = 45

                            cooldown = max(10, min(retry_after + 2, 60))
                            logger.info(
                                "Instahyre rate limit cooldown (%ds) at offset %d. Total extracted so far: %d",
                                cooldown,
                                offset,
                                len(processed_records),
                            )

                            # Live second-by-second countdown in UI
                            for remaining in range(cooldown, 0, -2):
                                if self._is_stopped:
                                    break
                                target_str = f" of {total_target_jobs}" if total_target_jobs else ""
                                self.stats.current_action = (
                                    f"Instahyre cooldown: resuming in {remaining}s... "
                                    f"({len(processed_records)}{target_str} extracted)"
                                )
                                if on_progress:
                                    await on_progress(self.stats)
                                await asyncio.sleep(2.0)

                        else:
                            logger.warning(
                                "Instahyre API returned status %s at offset %d",
                                resp.status_code,
                                offset,
                            )
                            if request_attempt >= 5:
                                break
                            await asyncio.sleep(2.0)

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
                    logger.info("No further data returned at offset %d. Wrapping up stream.", offset)
                    break

                meta = data.get("meta", {})
                if total_target_jobs is None:
                    total_target_jobs = meta.get("total_count")
                    logger.info("Instahyre reported total active jobs: %s", total_target_jobs)

                objs = data.get("objects", [])
                if not objs:
                    logger.info("Empty objects array received at offset %d. Dataset fully exhausted.", offset)
                    break

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
                    if not is_eligible_company_size(emp_count):
                        continue

                    if DataValidator.is_valid_record(clean_comp, clean_role, emp_count):
                        db_id, is_new, first_seen_at = self.repository.register_job(
                            company_name=clean_comp,
                            job_role=clean_role,
                            number_of_people=emp_count,
                            job_url=job_url,
                            source_website="instahyre.com",
                            posted_date=source_posted_date,
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
                        self.processed_records = processed_records
                        self.stats.jobs_processed = len(processed_records)
                        self.stats.recent_jobs = [
                            rec.to_dict() for rec in processed_records[-25:]
                        ]

                        norm_comp = DataCleaner.normalize_key(clean_comp)
                        if norm_comp not in unique_companies:
                            unique_companies.add(norm_comp)
                            self.stats.companies_discovered = len(unique_companies)

                offset += len(objs)
                if on_progress:
                    await on_progress(self.stats)

                # Check if next URL exists in meta
                meta_next = meta.get("next")
                if not meta_next:
                    logger.info("Pagination reached final page (meta.next is None).")
                    break

                # Pacing between batch requests
                await asyncio.sleep(0.5)

        self.stats.current_action = (
            f"Extraction completed. Total jobs extracted: {len(processed_records)}"
        )
        if on_progress:
            await on_progress(self.stats)

        return processed_records
