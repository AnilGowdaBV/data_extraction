"""Company extractor and in-memory profile cache."""

from collections.abc import Callable, Coroutine

from backend.app.core.logging import get_logger
from backend.app.extractors.employee_extractor import EmployeeCountExtractor
from backend.app.processors.cleaner import DataCleaner

logger = get_logger(__name__)


class CompanyExtractor:
    """
    Manages company profile data and in-memory employee count caching during a crawl.

    Ensures that if 100 jobs belong to the same company, the company profile page
    is visited at most ONCE during the extraction session.
    """

    def __init__(self) -> None:
        # Maps normalized company name -> employee count (int | 'N/A')
        self._cache: dict[str, int | str] = {}

    def get_cached_count(self, company_name: str) -> int | str | None:
        """Look up employee count in the session cache."""
        norm_name = DataCleaner.normalize_key(company_name)
        return self._cache.get(norm_name)

    def cache_count(self, company_name: str, count: int | str) -> None:
        """Store employee count in the session cache."""
        norm_name = DataCleaner.normalize_key(company_name)
        if norm_name:
            self._cache[norm_name] = count
            logger.debug("Cached employee count for '%s': %s", company_name, count)

    async def resolve_employee_count(
        self,
        company_name: str,
        company_profile_url: str | None = None,
        profile_fetcher: Callable[[str], Coroutine[None, None, str | None]] | None = None,
    ) -> int | str:
        """
        Resolve employee count for a company:
        1. Check in-memory cache first.
        2. If absent and a profile URL & fetcher are supplied, fetch profile HTML once.
        3. Parse and cache result.
        4. Return count or 'N/A'.
        """
        cached = self.get_cached_count(company_name)
        if cached is not None:
            return cached

        # If profile URL is available and fetcher provided
        if company_profile_url and profile_fetcher:
            try:
                logger.info(
                    "Visiting company profile for '%s': %s",
                    company_name,
                    company_profile_url,
                )
                html_content = await profile_fetcher(company_profile_url)
                if html_content:
                    extracted = EmployeeCountExtractor.parse_count(html_content)
                    self.cache_count(company_name, extracted)
                    return extracted
            except Exception as e:
                logger.warning("Failed to fetch company profile for %s: %s", company_name, e)

        # Cache default 'N/A' so we don't retry failed lookups repeatedly
        self.cache_count(company_name, "N/A")
        return "N/A"

    def clear(self) -> None:
        """Clear session cache."""
        self._cache.clear()
