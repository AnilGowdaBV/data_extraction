import asyncio
import os
import re
import sqlite3
import httpx
import json
from backend.app.db.database import init_db
from backend.app.utils.date_helpers import unix_to_himalayas_age

DB_PATH = "backend/data/jobs.db"
if not os.path.exists(DB_PATH):
    DB_PATH = "data/jobs.db"

init_db(DB_PATH)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. Find all distinct companies with the most jobs in himalayas.app
cur.execute("""
    SELECT company_name, job_url, COUNT(*) as cnt
    FROM scraped_jobs
    WHERE source_website = 'himalayas.app' AND (number_of_people = 'N/A' OR number_of_people IS NULL)
    GROUP BY company_name
    ORDER BY cnt DESC
    LIMIT 150
""")
top_companies = cur.fetchall()
print(f"Top {len(top_companies)} companies to resolve sizes for...")

slug_map = {}
for row in top_companies:
    cname = row["company_name"]
    url = row["job_url"] or ""
    m = re.search(r"/companies/([^/]+)", url)
    if m:
        slug = m.group(1).lower().strip()
        slug_map[slug] = cname
    else:
        alt_slug = re.sub(r"[^a-z0-9]+", "-", cname.lower()).strip("-")
        slug_map[alt_slug] = cname

print(f"Found {len(slug_map)} unique slugs among top companies.")

async def fetch_company_size(client: httpx.AsyncClient, slug: str) -> tuple[str, str]:
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "get_company_details", "arguments": {"company_slug": slug}},
        }
        resp = await client.post(
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

async def main():
    async with httpx.AsyncClient(timeout=15.0) as client:
        slug_items = list(slug_map.items())
        batch_size = 20
        resolved_count = 0
        
        for i in range(0, len(slug_items), batch_size):
            chunk = slug_items[i:i + batch_size]
            results = await asyncio.gather(*(fetch_company_size(client, s) for s, _ in chunk))
            for s, sz in results:
                cname = slug_map[s]
                if sz != "N/A":
                    resolved_count += 1
                    cur.execute("""
                        INSERT INTO company_profiles (company_slug, company_name, employee_count)
                        VALUES (?, ?, ?)
                        ON CONFLICT(company_slug) DO UPDATE SET employee_count = excluded.employee_count
                    """, (s, cname, sz))
                    # Update all existing jobs for this company
                    cur.execute("""
                        UPDATE scraped_jobs
                        SET number_of_people = ?
                        WHERE source_website = 'himalayas.app' AND (company_name = ? OR job_url LIKE ?)
                    """, (sz, cname, f"%{s}%"))
            conn.commit()
            print(f"Processed {min(i + batch_size, len(slug_items))}/{len(slug_items)} companies (Resolved sizes: {resolved_count})...")

    # 2. Also fetch recent jobs from Himalayas API to update pubDate/posted_date for recent jobs
    print("Updating pubDates from Himalayas API stream...")
    async with httpx.AsyncClient(timeout=15.0) as client:
        updated_jobs = 0
        for offset in range(0, 200, 20):
            try:
                r = await client.get(f"https://himalayas.app/jobs/api?offset={offset}&limit=20")
                if r.status_code == 200:
                    api_jobs = r.json().get("jobs", [])
                    for j in api_jobs:
                        pub_ts = j.get("pubDate")
                        url = j.get("applicationLink") or j.get("guid")
                        title = j.get("title")
                        cname = j.get("companyName")
                        if pub_ts and url:
                            p_date = unix_to_himalayas_age(pub_ts)
                            cur.execute("""
                                UPDATE scraped_jobs
                                SET published_at = ?, posted_date = ?
                                WHERE job_url = ? OR (company_name = ? AND job_role = ?)
                            """, (pub_ts, p_date, url, cname, title))
                            if cur.rowcount > 0:
                                updated_jobs += cur.rowcount
            except Exception as e:
                print(f"Error fetching API jobs at offset {offset}: {e}")
                break
        conn.commit()
        print(f"Updated {updated_jobs} matching jobs with real pubDate and Himalayas posted_date.")

    conn.close()
    print("Backfill complete!")

asyncio.run(main())
