"""Playwright browser lifecycle and page management."""

import asyncio
import sys
import threading
from typing import Any, Callable, Coroutine, Optional

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from backend.app.core.config import settings
from backend.app.core.exceptions import PageNavigationError
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class BrowserManager:
    """
    Manages Playwright Chromium instances and browser contexts.

    On Windows, executes in a dedicated ProactorEventLoop background thread
    so that subprocess execution (Playwright's driver) works seamlessly
    regardless of whether the main process runs with uvicorn reloader,
    SelectorEventLoop, or standard asyncio.
    """

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    def _ensure_event_loop(self) -> None:
        """Ensure a dedicated Proactor loop thread is active for Playwright on Windows."""
        if self._thread is None or not self._thread.is_alive():
            if sys.platform == "win32":
                self._loop = asyncio.ProactorEventLoop()
            else:
                self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(
                target=self._loop.run_forever, daemon=True, name="PlaywrightProactorThread"
            )
            self._thread.start()

    def run_coro(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Future:
        """Execute a coroutine on the managed Proactor loop thread and wrap as awaitable."""
        self._ensure_event_loop()
        assert self._loop is not None
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return asyncio.wrap_future(fut)

    async def _async_init(self) -> None:
        if not self._playwright:
            logger.info("Initializing Playwright and launching Chromium...")
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=settings.HEADLESS_BROWSER,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            self._context = await self._browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York",
            )
            await self._context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            logger.info("Browser initialized successfully.")

    async def initialize(self) -> None:
        """Start Playwright and launch Chromium."""
        await self.run_coro(self._async_init())

    async def fetch_page_content(self, url: str) -> str:
        """Open a URL in a new page, wait for rendering, and return the DOM HTML."""

        async def _fetch() -> str:
            if not self._context:
                await self._async_init()
            assert self._context is not None
            page = await self._context.new_page()
            page.set_default_timeout(settings.PAGE_TIMEOUT_MS)
            try:
                response = await page.goto(url, wait_until="load", timeout=settings.PAGE_TIMEOUT_MS)
                if response and response.status >= 400:
                    logger.warning("HTTP status %d returned for %s", response.status, url)
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass
                await page.wait_for_timeout(settings.REQUEST_DELAY_MS)
                content = await page.content()
                return content
            except Exception as e:
                logger.error("Navigation failed for %s: %s", url, e)
                raise PageNavigationError(f"Failed to navigate to {url}: {str(e)}") from e
            finally:
                await page.close()

        return await self.run_coro(_fetch())

    async def render_and_extract(
        self,
        url: str,
        action_fn: Callable[[Page], Coroutine[Any, Any, Any]],
    ) -> Any:
        """Open page, render DOM, and execute callback within the Proactor thread."""

        async def _run() -> Any:
            if not self._context:
                await self._async_init()
            assert self._context is not None
            page = await self._context.new_page()
            page.set_default_timeout(settings.PAGE_TIMEOUT_MS)
            try:
                await page.goto(
                    url, wait_until="domcontentloaded", timeout=settings.PAGE_TIMEOUT_MS
                )
                await page.wait_for_timeout(settings.REQUEST_DELAY_MS)
                return await action_fn(page)
            finally:
                await page.close()

        return await self.run_coro(_run())

    async def close(self) -> None:
        """Gracefully close all browser contexts and shut down Playwright."""

        async def _close() -> None:
            try:
                if self._context:
                    await self._context.close()
                    self._context = None
                if self._browser:
                    await self._browser.close()
                    self._browser = None
                if self._playwright:
                    await self._playwright.stop()
                    self._playwright = None
                logger.info("Browser resources cleaned up.")
            except Exception as e:
                logger.warning("Error during browser shutdown: %s", e)

        if self._loop and self._loop.is_running():
            await self.run_coro(_close())
