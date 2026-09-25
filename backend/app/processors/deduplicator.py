"""Deduplication component for job records."""

from urllib.parse import urlparse, urlunparse

from backend.app.processors.cleaner import DataCleaner


class JobDeduplicator:
    """Detects and filters duplicate job postings across crawls."""

    def __init__(self) -> None:
        self._seen_urls: set[str] = set()
        self._seen_signatures: set[str] = set()
        self.duplicates_count: int = 0

    @staticmethod
    def normalize_url(url: str) -> str:
        """Strip tracking query parameters and fragments to identify true job URL."""
        if not url:
            return ""
        parsed = urlparse(url)
        # Drop fragment and keep path
        return urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", "")
        ).lower()

    def is_duplicate(
        self,
        company_name: str,
        job_role: str,
        job_url: str | None = None,
    ) -> bool:
        """
        Determine if the given job record has already been encountered.

        Uses normalized Job URL as primary unique identifier when available.
        Falls back to Normalized Company Name + Normalized Job Role.
        """
        # Primary: URL-based deduplication
        if job_url:
            norm_url = self.normalize_url(job_url)
            if norm_url:
                if norm_url in self._seen_urls:
                    self.duplicates_count += 1
                    return True
                self._seen_urls.add(norm_url)
                return False

        # Fallback: Only used when job_url is not available
        norm_company = DataCleaner.normalize_key(company_name)
        norm_role = DataCleaner.normalize_key(job_role)
        signature = f"{norm_company}::{norm_role}"

        if signature in self._seen_signatures:
            self.duplicates_count += 1
            return True

        self._seen_signatures.add(signature)
        return False

    def reset(self) -> None:
        """Reset deduplication caches."""
        self._seen_urls.clear()
        self._seen_signatures.clear()
        self.duplicates_count = 0
