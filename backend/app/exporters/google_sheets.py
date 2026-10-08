"""Google Sheets sync integration using Webhook endpoint for daily date-wise tabs."""

import asyncio
from datetime import datetime, timezone
from typing import Optional
import httpx

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.models.job import ProcessedJobRecord

logger = get_logger(__name__)


class GoogleSheetsExporter:
    """Safely synchronizes job records directly into the user's Google Spreadsheet."""

    @classmethod
    async def sync_jobs_to_sheet(
        cls,
        records: list[ProcessedJobRecord],
        sheet_name: Optional[str] = None,
        webhook_url: Optional[str] = None,
    ) -> dict:
        """
        Synchronize a list of ProcessedJobRecords to a specific date tab in Google Sheets.
        If sheet_name is None, defaults to current date (e.g. 'Oct 8').
        Does NOT overwrite or harm any existing tabs or previous rows.
        """
        if not records:
            return {"success": True, "synced_count": 0, "message": "No records to sync."}

        target_url = webhook_url or settings.GOOGLE_SHEETS_WEBHOOK_URL
        if not target_url:
            return {
                "success": False,
                "error": "Google Sheets webhook URL is not configured.",
            }

        # Format tab name by local date if not provided (e.g. 'Oct 8')
        if not sheet_name:
            now_local = datetime.now().astimezone()
            sheet_name = f"{now_local.strftime('%b')} {now_local.day}"  # e.g. "Oct 8"

        # Prepare rows in standard format
        rows = [record.to_row() for record in records]

        # Chunk into batches of 100 for reliable Google Apps Script execution
        batch_size = 100
        total_synced = 0

        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            for i in range(0, len(rows), batch_size):
                chunk = rows[i : i + batch_size]
                payload = {
                    "sheet_name": sheet_name,
                    "rows": chunk,
                }
                try:
                    resp = await client.post(target_url, json=payload)
                    if resp.status_code == 200:
                        total_synced += len(chunk)
                        logger.info(
                            "Synced %d/%d jobs to Google Sheet tab '%s'",
                            total_synced,
                            len(rows),
                            sheet_name,
                        )
                    else:
                        logger.warning(
                            "Google Sheets webhook returned status %d: %s",
                            resp.status_code,
                            resp.text[:200],
                        )
                        return {
                            "success": False,
                            "synced_count": total_synced,
                            "error": f"Webhook returned HTTP {resp.status_code}",
                        }
                except Exception as e:
                    logger.error("Failed to post batch to Google Sheets webhook: %s", e)
                    return {
                        "success": False,
                        "synced_count": total_synced,
                        "error": str(e),
                    }

                # Brief pause between chunks to keep Google Apps Script happy
                if i + batch_size < len(rows):
                    await asyncio.sleep(0.5)

        return {
            "success": True,
            "synced_count": total_synced,
            "sheet_name": sheet_name,
            "spreadsheet_url": settings.GOOGLE_SHEET_URL,
        }

    @classmethod
    async def sync_all_jobs_by_date(
        cls,
        records: list[ProcessedJobRecord],
        webhook_url: Optional[str] = None,
    ) -> dict:
        """
        Groups all records by the date they were scraped (first_seen_at)
        and synchronizes each group into its own date tab in Google Sheets (e.g. 'Sep 23', 'Oct 8').
        """
        if not records:
            return {"success": True, "synced_count": 0, "message": "No records to sync."}

        from collections import defaultdict
        grouped = defaultdict(list)

        for rec in records:
            date_label = "Other"
            if rec.first_seen_at:
                try:
                    raw_str = rec.first_seen_at.strip().replace("Z", "+00:00")
                    if "T" in raw_str:
                        dt = datetime.fromisoformat(raw_str)
                    else:
                        dt = datetime.strptime(raw_str[:10], "%Y-%m-%d")
                    if dt.tzinfo is not None:
                        dt = dt.astimezone()
                    date_label = f"{dt.strftime('%b')} {dt.day}"  # e.g. "Sep 23", "Oct 8"
                except Exception:
                    date_label = "Other"
            grouped[date_label].append(rec)

        total_synced = 0
        date_summaries = {}

        # Sort dates chronologically by earliest record first_seen_at
        def get_earliest_dt(item):
            tab_recs = item[1]
            dates = [r.first_seen_at for r in tab_recs if r.first_seen_at]
            return min(dates) if dates else ""

        for date_tab, date_records in sorted(grouped.items(), key=get_earliest_dt):
            res = await cls.sync_jobs_to_sheet(
                records=date_records,
                sheet_name=date_tab,
                webhook_url=webhook_url,
            )
            synced_in_tab = res.get("synced_count", 0)
            total_synced += synced_in_tab
            date_summaries[date_tab] = synced_in_tab
            await asyncio.sleep(0.5)

        return {
            "success": True,
            "total_synced": total_synced,
            "date_tabs": date_summaries,
            "spreadsheet_url": settings.GOOGLE_SHEET_URL,
        }

