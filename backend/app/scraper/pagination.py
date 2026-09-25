"""Pagination detection, Load More button handling, and infinite scroll logic."""

import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import Page

from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class PaginationHandler:
    """Detects and navigates pagination structures across heterogeneous websites."""

    # Common 'Next' button/link text patterns
    _NEXT_TEXT_REGEX = re.compile(
        r"^(next(\s*([>›»]|page|\d+))?|[>›»]|continue|siguiente|suivant|weiter)$",
        re.IGNORECASE,
    )

    # Common 'Load More' button patterns
    _LOAD_MORE_REGEX = re.compile(
        r"(load\s*more|show\s*more|view\s*more|more\s*jobs|see\s*more|fetch\s*more)",
        re.IGNORECASE,
    )

    @classmethod
    def find_next_page_url(
        cls, soup: BeautifulSoup, current_url: str, visited_urls: set[str]
    ) -> str | None:
        """
        Locate the next page URL in the rendered HTML.
        Checks:
        1. <link rel="next" href="..."> or <a rel="next" href="...">
        2. Links matching aria-label="Next" or title="Next"
        3. Anchor tags with text like 'Next', 'Next >', '›', '»'
        4. Links matching common query parameter pagination (?page=N, ?p=N)
        """
        # 1. rel="next"
        rel_next = soup.find(["link", "a"], rel=re.compile(r"\bnext\b", re.IGNORECASE))
        if rel_next and rel_next.get("href"):
            candidate = urljoin(current_url, rel_next["href"])
            if candidate not in visited_urls and cls._is_valid_next(candidate, current_url):
                return candidate

        # 2. aria-label or title matching 'Next'
        aria_next = soup.find(
            "a",
            attrs={
                "aria-label": re.compile(r"\bnext\b", re.IGNORECASE),
                "href": True,
            },
        )
        if aria_next and aria_next.get("href"):
            candidate = urljoin(current_url, aria_next["href"])
            if candidate not in visited_urls and cls._is_valid_next(candidate, current_url):
                return candidate

        # 3. Text content matching 'Next'
        for a in soup.find_all("a", href=True):
            text = a.get_text().strip()
            if cls._NEXT_TEXT_REGEX.match(text):
                candidate = urljoin(current_url, a["href"])
                if candidate not in visited_urls and cls._is_valid_next(candidate, current_url):
                    return candidate

        # 4. Check standard pagination blocks for the next numeric page
        nav_containers = soup.find_all(
            ["nav", "ul", "div"],
            class_=re.compile(r"(pagination|pager|page-numbers)", re.IGNORECASE),
        )
        for nav in nav_containers:
            for a in nav.find_all("a", href=True):
                text = a.get_text().strip()
                if cls._NEXT_TEXT_REGEX.match(text):
                    candidate = urljoin(current_url, a["href"])
                    if candidate not in visited_urls and cls._is_valid_next(candidate, current_url):
                        return candidate

        # 5. Check interactive or JS pagination elements (e.g. Instahyre <li ng-click="nextPage()">Next »</li>)
        def _is_active_next(t: Any) -> bool:
            if not hasattr(t, "name") or t.name not in ["li", "span", "button", "a", "div"]:
                return False
            text = t.get_text().strip()
            if not cls._NEXT_TEXT_REGEX.match(text):
                return False
            classes = [c.lower() for c in t.get("class", []) or []]
            if "hidden" in classes or "disabled" in classes or t.get("disabled") is not None:
                return False
            if t.get("aria-disabled") == "true":
                return False
            parent_classes = " ".join(t.parent.get("class", []) if t.parent else [])
            return (
                any(k in t.attrs for k in ("ng-click", "onclick", "data-page", "data-action"))
                or "pagination" in parent_classes
            )

        js_next = soup.find(_is_active_next)
        if js_next:
            parsed = urlparse(current_url)
            from urllib.parse import parse_qs, urlencode, urlunparse

            qs = parse_qs(parsed.query)
            current_page_num = 1
            if "page" in qs and qs["page"]:
                try:
                    current_page_num = int(qs["page"][0])
                except ValueError:
                    current_page_num = 1
            next_page_num = current_page_num + 1
            qs["page"] = [str(next_page_num)]
            new_query = urlencode(qs, doseq=True)
            candidate = urlunparse(
                (
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    new_query,
                    parsed.fragment,
                )
            )
            if candidate not in visited_urls and cls._is_valid_next(candidate, current_url):
                return candidate

        return None

    @classmethod
    async def try_click_load_more(cls, page: Page) -> bool:
        """
        Search for and click dynamic 'Load More' / 'Show More' buttons on the page.
        Returns True if a button was clicked and new content loaded, False otherwise.
        """
        try:
            # Look for buttons or links with Load More text
            buttons = await page.get_by_role("button").all()
            for btn in buttons:
                text = (await btn.text_content() or "").strip()
                if cls._LOAD_MORE_REGEX.search(text):
                    is_visible = await btn.is_visible()
                    is_enabled = await btn.is_enabled()
                    if is_visible and is_enabled:
                        logger.info(
                            "Found 'Load More' button with text: '%s'. Clicking...",
                            text,
                        )
                        await btn.scroll_into_view_if_needed()
                        await btn.click(timeout=5000)
                        await page.wait_for_timeout(settings.REQUEST_DELAY_MS * 2)
                        return True
        except Exception as e:
            logger.debug("Load More click attempt error: %s", e)

        return False

    @classmethod
    async def try_infinite_scroll(cls, page: Page, max_attempts: int = 3) -> bool:
        """
        Execute stepped infinite scrolling down the page.
        Returns True if new content expanded the page height, False if bottom reached.
        """
        try:
            previous_height = await page.evaluate("document.body.scrollHeight")

            for _ in range(max_attempts):
                # Scroll to bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(settings.REQUEST_DELAY_MS * 2)

                current_height = await page.evaluate("document.body.scrollHeight")
                if current_height > previous_height:
                    logger.debug(
                        "Infinite scroll expanded page height: %s -> %s",
                        previous_height,
                        current_height,
                    )
                    return True
                previous_height = current_height

            return False
        except Exception as e:
            logger.debug("Infinite scroll evaluation failed: %s", e)
            return False

    @staticmethod
    def _is_valid_next(candidate_url: str, current_url: str) -> bool:
        """Sanity check that next URL differs from current and stays on same origin."""
        if not candidate_url or candidate_url == current_url:
            return False
        # Strip trailing slashes and fragments for comparison
        c_clean = candidate_url.split("#")[0].rstrip("/")
        curr_clean = current_url.split("#")[0].rstrip("/")
        if c_clean == curr_clean:
            return False

        # Ensure same host
        c_host = urlparse(candidate_url).hostname or ""
        curr_host = urlparse(current_url).hostname or ""
        return c_host.lower() == curr_host.lower()
