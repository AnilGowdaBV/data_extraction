"""Scraper package."""

from backend.app.scraper.browser import BrowserManager
from backend.app.scraper.crawler import JobCrawler
from backend.app.scraper.discovery import UrlDiscoverySecurity
from backend.app.scraper.pagination import PaginationHandler

__all__ = [
    "BrowserManager",
    "JobCrawler",
    "PaginationHandler",
    "UrlDiscoverySecurity",
]
