"""Bulk Job Website -> Excel Extractor Backend Application."""

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

__version__ = "1.0.0"
