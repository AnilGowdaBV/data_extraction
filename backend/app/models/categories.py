"""Domain categories and keywords configuration for multi-tab Excel workbooks."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from backend.app.models.job import ProcessedJobRecord


def is_under_100_people(value: Any) -> bool:
    """Check if the employee count represents fewer than 100 people."""
    if value is None or str(value).strip() in ("N/A", "Unknown", "", "None"):
        return False
    if isinstance(value, (int, float)):
        return value < 100
    s = str(value).lower().strip()
    m_range = re.search(r"(\d+)\s*[-–—to]+\s*(\d+)", s)
    if m_range:
        low, high = int(m_range.group(1)), int(m_range.group(2))
        return high <= 100
    m_plus = re.search(r"(\d+)\+", s)
    if m_plus:
        return False
    m_num = re.search(r"(\d+)", s)
    if m_num:
        return int(m_num.group(1)) < 100
    return False


CATEGORIES: Dict[str, Dict[str, Any]] = {
    "qa_automation": {
        "id": "qa_automation",
        "name": "QA & Test Automation",
        "filename": "QA_Automation_Jobs.xlsx",
        "icon": "CheckSquare",
        "color": "emerald",
        "keywords": [
            {"name": "Selenium", "terms": ["selenium"]},
            {"name": "Playwright", "terms": ["playwright"]},
            {"name": "Cypress", "terms": ["cypress"]},
            {"name": "Appium", "terms": ["appium"]},
            {"name": "WebDriverIO", "terms": ["webdriverio", "webdriver.io", "webdriver io"]},
            {"name": "Rest Assured", "terms": ["rest assured", "restassured", "rest-assured"]},
        ],
    },
    "devops_cloud": {
        "id": "devops_cloud",
        "name": "DevOps & Cloud Infrastructure",
        "filename": "DevOps_Cloud_Jobs.xlsx",
        "icon": "Cloud",
        "color": "sky",
        "keywords": [
            {"name": "Kubernetes", "terms": ["kubernetes", "k8s"]},
            {"name": "Terraform", "terms": ["terraform"]},
        ],
    },
    "frontend_mobile": {
        "id": "frontend_mobile",
        "name": "Frontend & Mobile Development",
        "filename": "Frontend_Mobile_Jobs.xlsx",
        "icon": "Layout",
        "color": "cyan",
        "keywords": [
            {"name": "React", "terms": ["react", "react.js", "reactjs"]},
            {"name": "iOS", "terms": ["ios", "swift", "objective-c"]},
            {"name": "Angular", "terms": ["angular", "angularjs"]},
            {"name": "React Native", "terms": ["react native", "react-native"]},
            {"name": "Android", "terms": ["android", "kotlin"]},
            {"name": "Flutter", "terms": ["flutter", "dart"]},
            {"name": "Vue", "terms": ["vue", "vue.js", "vuejs"]},
            {"name": "Svelte", "terms": ["svelte", "sveltekit"]},
        ],
    },
    "backend": {
        "id": "backend",
        "name": "Backend Development",
        "filename": "Backend_Jobs.xlsx",
        "icon": "Server",
        "color": "indigo",
        "keywords": [
            {"name": "Java", "terms": ["java ", "java/", "java-", "java,", "java engineer", "java developer", "spring boot", "springboot"]},
            {"name": "Node", "terms": ["node", "nodejs", "node.js", "express"]},
            {"name": "Golang", "terms": ["golang", "go developer", "go engineer", "go software"]},
            {"name": "Python", "terms": ["python", "django", "fastapi", "flask"]},
            {"name": "Rust", "terms": ["rust", "rustlang"]},
        ],
    },
    "data_analytics": {
        "id": "data_analytics",
        "name": "Data Analytics",
        "filename": "Data_Analytics_Jobs.xlsx",
        "icon": "BarChart3",
        "color": "amber",
        "keywords": [
            {"name": "Data Analyst", "terms": ["data analyst", "business intelligence", "bi analyst", "analytics engineer"]},
        ],
    },
    "data_engineering": {
        "id": "data_engineering",
        "name": "Data Engineering",
        "filename": "Data_Engineering_Jobs.xlsx",
        "icon": "Database",
        "color": "orange",
        "keywords": [
            {"name": "Data Engineering", "terms": ["data engineer", "data engineering", "etl", "big data", "spark", "hadoop", "databricks"]},
        ],
    },
    "ux_design": {
        "id": "ux_design",
        "name": "UX & Product Design",
        "filename": "UX_Design_Jobs.xlsx",
        "icon": "Palette",
        "color": "purple",
        "keywords": [
            {"name": "UX Designer", "terms": ["ux designer", "ui/ux", "product designer", "user experience", "interaction design"]},
        ],
    },
    "fde": {
        "id": "fde",
        "name": "Forward Deployed Engineering",
        "filename": "FDE_Jobs.xlsx",
        "icon": "Zap",
        "color": "rose",
        "keywords": [
            {"name": "FDE", "terms": ["forward deployed", "forward-deployed", "fde", "solutions engineer", "deployment engineer"]},
        ],
    },
}


def matches_keyword(job_role: str, terms: List[str]) -> bool:
    """Check if a job role contains any of the search terms."""
    role_lower = f" {job_role.lower()} "
    for term in terms:
        t_clean = term.strip().lower()
        if t_clean in role_lower:
            return True
        pattern = r"\b" + re.escape(t_clean) + r"\b"
        if re.search(pattern, role_lower):
            return True
    return False


def filter_jobs_for_category(
    all_jobs: List[ProcessedJobRecord], category_id: str
) -> Dict[str, Dict[str, List[ProcessedJobRecord]]]:
    """
    Given a list of job records and category_id, filter jobs into keyword buckets:
    Returns:
    {
        "all_category_jobs": list,
        "all_under_100": list,
        "keywords": {
            "Selenium": {
                "all": [...],
                "under_100": [...]
            },
            ...
        }
    }
    """
    cat = CATEGORIES.get(category_id)
    if not cat:
        return {"all_category_jobs": [], "all_under_100": [], "keywords": {}}

    cat_jobs: List[ProcessedJobRecord] = []
    seen_ids = set()
    keyword_map: Dict[str, Dict[str, List[ProcessedJobRecord]]] = {}

    for kw in cat["keywords"]:
        kw_name = kw["name"]
        terms = kw["terms"]
        matched_all = []
        matched_under_100 = []

        for j in all_jobs:
            if matches_keyword(j.job_role, terms):
                matched_all.append(j)
                if is_under_100_people(j.number_of_people):
                    matched_under_100.append(j)
                
                job_key = (j.company_name.lower(), j.job_role.lower())
                if job_key not in seen_ids:
                    seen_ids.add(job_key)
                    cat_jobs.append(j)

        keyword_map[kw_name] = {
            "all": matched_all,
            "under_100": matched_under_100,
        }

    cat_under_100 = [j for j in cat_jobs if is_under_100_people(j.number_of_people)]

    return {
        "all_category_jobs": cat_jobs,
        "all_under_100": cat_under_100,
        "keywords": keyword_map,
    }
