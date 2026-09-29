"""API routes for candidate job applications - submit, search roles, and export Excel."""

import os
import tempfile
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from backend.app.core.logging import get_logger
from backend.app.db.database import get_db_connection, init_db

logger = get_logger(__name__)
router = APIRouter(prefix="/api/applications", tags=["Applications"])

# Ensure table exists on startup
init_db()

# ─── Resumes storage dir ─────────────────────────────────────────────────────
RESUME_DIR = os.path.join(tempfile.gettempdir(), "job_application_resumes")
os.makedirs(RESUME_DIR, exist_ok=True)


# ─── Role category classifier ────────────────────────────────────────────────
ROLE_CATEGORY_MAP: dict[str, list[str]] = {
    "SDE": ["sde", "software development engineer", "software developer", "software engineer", "sde-1", "sde-2", "sde1", "sde2", "member of technical staff", "mts"],
    "Frontend": ["frontend", "front-end", "front end", "react", "angular", "vue", "ui developer", "ui engineer", "javascript developer", "web developer"],
    "Backend": ["backend", "back-end", "back end", "api developer", "server-side", "node.js", "django", "flask", "spring", "golang developer", "rust developer", "java developer", "python developer"],
    "Full Stack": ["full stack", "fullstack", "full-stack", "mean stack", "mern stack", "lamp stack"],
    "DevOps": ["devops", "dev ops", "infrastructure", "sre", "site reliability", "platform engineer", "cloud engineer", "devsecops", "ci/cd", "kubernetes", "docker"],
    "Data / ML": ["data scientist", "data engineer", "machine learning", "ml engineer", "ai engineer", "data analyst", "analytics engineer", "nlp", "deep learning", "computer vision"],
    "Mobile": ["mobile", "android", "ios", "flutter", "react native", "swift", "kotlin"],
    "QA / Testing": ["qa", "quality assurance", "test engineer", "sdet", "automation engineer", "testing"],
    "Security": ["security engineer", "cybersecurity", "appsec", "penetration", "infosec"],
    "Management": ["engineering manager", "product manager", "tech lead", "team lead", "cto", "vp of engineering", "director of engineering", "project manager", "scrum master"],
}


def classify_role(job_role: str) -> str:
    """Return the best-matching role category for a given job role string."""
    lower = job_role.strip().lower()
    for category, keywords in ROLE_CATEGORY_MAP.items():
        if any(kw in lower for kw in keywords):
            return category
    return "Other"


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.get("/search-roles")
async def search_roles(
    q: str = Query("", description="Partial role name to search"),
    limit: int = Query(20, le=50),
) -> dict:
    """
    Live role search from the Instahyre job archive.
    Returns distinct (job_role, company_name, job_url) tuples matching the query.
    """
    search_term = f"%{q.strip()}%" if q.strip() else "%"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT job_role, company_name, job_url
            FROM scraped_jobs
            WHERE source_website LIKE '%instahyre%'
              AND job_role LIKE ?
            ORDER BY job_role ASC
            LIMIT ?;
            """,
            (search_term, limit),
        )
        rows = cursor.fetchall()

    results = [
        {
            "job_role": row["job_role"],
            "company_name": row["company_name"],
            "job_url": row["job_url"],
            "role_category": classify_role(row["job_role"]),
        }
        for row in rows
    ]
    return {"results": results, "total": len(results)}


@router.get("/recent-jobs")
async def get_recent_jobs(
    limit: int = Query(20, ge=1, le=50, description="Number of recent jobs to return (default: 20)"),
    source: str = Query("himalayas", description="Filter source, e.g. 'himalayas', 'instahyre', or 'all'"),
) -> dict:
    """
    Returns the most recently scraped jobs from the master database.
    Defaults to Himalayas source.
    """
    s_lower = source.lower()
    if s_lower == "himalayas":
        where_clause = "WHERE source_website LIKE '%himalayas%'"
    elif s_lower == "instahyre":
        where_clause = "WHERE source_website LIKE '%instahyre%'"
    else:
        where_clause = ""

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT id, fingerprint, job_url, company_name, job_role, number_of_people, source_website, first_seen_at
            FROM scraped_jobs
            {where_clause}
            ORDER BY first_seen_at DESC, id DESC
            LIMIT ?;
            """,
            (limit,),
        )
        rows = cursor.fetchall()

    jobs = [
        {
            "id": row["id"],
            "company_name": row["company_name"],
            "job_role": row["job_role"],
            "number_of_people": row["number_of_people"],
            "job_url": row["job_url"],
            "source_website": row["source_website"],
            "first_seen_at": str(row["first_seen_at"]) if row["first_seen_at"] else None,
            "role_category": classify_role(row["job_role"]),
        }
        for row in rows
    ]
    return {"jobs": jobs, "total": len(jobs)}



@router.post("/apply", status_code=status.HTTP_201_CREATED)
async def submit_application(
    name: str = Form(...),
    contact: str = Form(...),
    linkedin_url: Optional[str] = Form(None),
    job_role: str = Form(...),
    company_name: Optional[str] = Form(None),
    job_url: Optional[str] = Form(None),
    current_salary: Optional[str] = Form(None),
    expected_salary: Optional[str] = Form(None),
    notice_period: Optional[str] = Form(None),
    resume: Optional[UploadFile] = File(None),
) -> dict:
    """Submit a candidate job application. Stores details + resume in DB."""
    role_category = classify_role(job_role)

    # Save resume file if provided
    resume_filename = None
    resume_path = None
    if resume and resume.filename:
        safe_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in resume.filename)
        resume_filename = f"{safe_ts}_{safe_name}"
        resume_path = os.path.join(RESUME_DIR, resume_filename)
        content = await resume.read()
        with open(resume_path, "wb") as f:
            f.write(content)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO job_applications
                (name, contact, linkedin_url, resume_filename, resume_path,
                 job_role, company_name, job_url, role_category,
                 current_salary, expected_salary, notice_period, applied_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
            """,
            (
                name.strip(),
                contact.strip(),
                linkedin_url.strip() if linkedin_url else None,
                resume_filename,
                resume_path,
                job_role.strip(),
                company_name.strip() if company_name else None,
                job_url.strip() if job_url else None,
                role_category,
                current_salary.strip() if current_salary else None,
                expected_salary.strip() if expected_salary else None,
                notice_period.strip() if notice_period else None,
            ),
        )
        conn.commit()
        new_id = cursor.lastrowid

    logger.info(
        "New application saved: id=%s name=%s role=%s category=%s",
        new_id, name, job_role, role_category,
    )
    return {
        "id": new_id,
        "message": f"Application submitted successfully! Category: {role_category}",
        "role_category": role_category,
    }


@router.get("/stats")
async def get_application_stats() -> dict:
    """Return total application count and breakdown by role category."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM job_applications;")
        total = cursor.fetchone()["total"]

        cursor.execute(
            """
            SELECT role_category, COUNT(*) as count
            FROM job_applications
            GROUP BY role_category
            ORDER BY count DESC;
            """
        )
        breakdown = {row["role_category"]: row["count"] for row in cursor.fetchall()}

    return {"total_applications": total, "by_category": breakdown}


@router.get("/export")
async def export_applications_excel() -> FileResponse:
    """
    Generate and download an Excel workbook where each sheet = one role category.
    Incremental: each download reflects all applications ever submitted.
    """
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, name, contact, linkedin_url, resume_filename,
                   job_role, company_name, job_url, role_category,
                   current_salary, expected_salary, notice_period, applied_at
            FROM job_applications
            ORDER BY role_category ASC, applied_at ASC;
            """
        )
        rows = cursor.fetchall()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No applications found to export.",
        )

    # Group by category
    from collections import defaultdict
    by_category: dict[str, list] = defaultdict(list)
    for row in rows:
        by_category[row["role_category"]].append(dict(row))

    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # Remove default empty sheet

    HEADER_FILL = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
    NEW_FILL = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
    HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
    HEADERS = ["#", "Name", "Contact", "LinkedIn URL", "Job Role Applied", "Company", "Job URL",
               "Current Salary", "Expected Salary", "Notice Period", "Resume File", "Applied At"]
    COL_WIDTHS = [5, 25, 18, 38, 32, 28, 42, 18, 18, 16, 28, 22]

    for category, apps in sorted(by_category.items()):
        # Excel sheet names cannot contain: / \ ? * [ ] :
        safe_title = category.replace("/", "-").replace("\\", "-").replace("?", "").replace("*", "").replace("[", "").replace("]", "").replace(":", "-")
        ws = wb.create_sheet(title=safe_title[:31])

        # Header row
        for col_idx, (header, width) in enumerate(zip(HEADERS, COL_WIDTHS), start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.column_dimensions[cell.column_letter].width = width

        ws.row_dimensions[1].height = 20

        # Data rows
        for row_idx, app in enumerate(apps, start=2):
            fill = NEW_FILL if row_idx % 2 == 0 else None
            values = [
                row_idx - 1,
                app["name"],
                app["contact"],
                app["linkedin_url"] or "",
                app["job_role"],
                app["company_name"] or "",
                app["job_url"] or "",
                app.get("current_salary") or "",
                app.get("expected_salary") or "",
                app.get("notice_period") or "",
                app["resume_filename"] or "No resume",
                app["applied_at"],
            ]
            for col_idx, value in enumerate(values, start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.alignment = Alignment(vertical="center", wrap_text=False)
                if fill:
                    cell.fill = fill

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

    # Summary sheet
    ws_summary = wb.create_sheet(title="Summary", index=0)
    ws_summary.column_dimensions["A"].width = 30
    ws_summary.column_dimensions["B"].width = 18
    ws_summary.column_dimensions["C"].width = 25

    sum_headers = ["Role Category", "Applications", "Last Applied At"]
    for col_idx, header in enumerate(sum_headers, start=1):
        cell = ws_summary.cell(row=1, column=col_idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")

    for row_idx, (category, apps) in enumerate(sorted(by_category.items()), start=2):
        last_applied = max(a["applied_at"] for a in apps)
        ws_summary.cell(row=row_idx, column=1, value=category)
        ws_summary.cell(row=row_idx, column=2, value=len(apps)).alignment = Alignment(horizontal="center")
        ws_summary.cell(row=row_idx, column=3, value=last_applied)

    total_row = len(by_category) + 2
    total_cell = ws_summary.cell(row=total_row, column=1, value="TOTAL")
    total_cell.font = Font(bold=True)
    count_cell = ws_summary.cell(row=total_row, column=2, value=len(rows))
    count_cell.font = Font(bold=True)
    count_cell.alignment = Alignment(horizontal="center")

    export_dir = os.path.join(tempfile.gettempdir(), "applications_exports")
    os.makedirs(export_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"Job_Applications_{len(rows)}_{ts}.xlsx"
    output_path = os.path.join(export_dir, filename)
    wb.save(output_path)

    return FileResponse(
        path=output_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
