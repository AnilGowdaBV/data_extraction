"""Job extractor analyzing JSON-LD, hydration state, DOM structures, and detail pages."""

import json
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from backend.app.core.logging import get_logger
from backend.app.models.job import RawJobRecord
from backend.app.processors.cleaner import DataCleaner
from backend.app.processors.validator import DataValidator

logger = get_logger(__name__)


class JobExtractor:
    """
    Autonomous multi-tiered job extractor.
    Tier 1: Structured JSON-LD (Schema.org/JobPosting)
    Tier 2: Embedded JSON Hydration State (__NEXT_DATA__, __INITIAL_STATE__)
    Tier 3: Heuristic DOM Repeated-Card Detector
    Tier 4: Table-based listings
    Tier 5: Detail-page deep extraction fallback
    """

    @classmethod
    def extract_from_html(cls, html_content: str, base_url: str = "") -> list[RawJobRecord]:
        """Orchestrate tiered extraction from rendered HTML content."""
        if not html_content or not html_content.strip():
            return []

        soup = BeautifulSoup(html_content, "lxml")
        records: list[RawJobRecord] = []

        # Tier 1: Extract from JSON-LD
        json_ld_jobs = cls._extract_from_json_ld(soup, base_url)
        if json_ld_jobs:
            logger.info("Extracted %d jobs via JSON-LD", len(json_ld_jobs))
            records.extend(json_ld_jobs)

        # Tier 2: Extract from Hydration State
        hydration_jobs = cls._extract_from_hydration(soup, base_url)
        if hydration_jobs:
            logger.info("Extracted %d jobs via Hydration State", len(hydration_jobs))
            records.extend(hydration_jobs)

        # Tier 3: Extract from DOM repeated-card heuristics
        dom_jobs = cls._extract_from_dom_cards(soup, base_url)
        if dom_jobs:
            logger.info("Extracted %d jobs via DOM card heuristics", len(dom_jobs))
            records.extend(dom_jobs)

        # Tier 4: Fallback to tables if no jobs discovered yet
        if not records:
            table_jobs = cls._extract_from_tables(soup, base_url)
            if table_jobs:
                logger.info("Extracted %d jobs via HTML tables", len(table_jobs))
                records.extend(table_jobs)

        return records

    # -------------------------------------------------------------
    # Tier 1: JSON-LD Structured Data
    # -------------------------------------------------------------
    @classmethod
    def _extract_from_json_ld(cls, soup: BeautifulSoup, base_url: str) -> list[RawJobRecord]:
        records: list[RawJobRecord] = []
        scripts = soup.find_all("script", type="application/ld+json")

        for script in scripts:
            if not script.string:
                continue
            try:
                data = json.loads(script.string.strip())
                records.extend(cls._parse_json_ld_item(data, base_url))
            except (json.JSONDecodeError, TypeError):
                continue

        return records

    @classmethod
    def _parse_json_ld_item(cls, item: Any, base_url: str) -> list[RawJobRecord]:
        records: list[RawJobRecord] = []
        if isinstance(item, list):
            for sub_item in item:
                records.extend(cls._parse_json_ld_item(sub_item, base_url))
            return records

        if not isinstance(item, dict):
            return records

        # Handle @graph
        if "@graph" in item and isinstance(item["@graph"], list):
            for sub_item in item["@graph"]:
                records.extend(cls._parse_json_ld_item(sub_item, base_url))
            return records

        item_type = item.get("@type", "")
        is_job = False
        if (
            isinstance(item_type, str)
            and "jobposting" in item_type.lower()
            or isinstance(item_type, list)
            and any("jobposting" in str(t).lower() for t in item_type)
        ):
            is_job = True

        if is_job:
            role = item.get("title") or item.get("name")
            hiring_org = item.get("hiringOrganization", {})
            company = ""
            employee_count_raw = None
            company_url = None

            if isinstance(hiring_org, dict):
                company = hiring_org.get("name") or hiring_org.get("legalName") or ""
                num_emp = hiring_org.get("numberOfEmployees")
                if isinstance(num_emp, dict):
                    employee_count_raw = str(num_emp.get("value") or "")
                elif num_emp is not None:
                    employee_count_raw = str(num_emp)
                company_url = hiring_org.get("sameAs") or hiring_org.get("url")
            elif isinstance(hiring_org, str):
                company = hiring_org

            job_url = item.get("url") or base_url

            if role and company:
                records.append(
                    RawJobRecord(
                        company_name=str(company),
                        job_role=str(role),
                        employee_count_raw=employee_count_raw,
                        job_url=str(job_url) if job_url else None,
                        company_url=str(company_url) if company_url else None,
                        page_url=base_url,
                        source_type="json_ld",
                    )
                )

        return records

    # -------------------------------------------------------------
    # Tier 2: Next.js / Hydration State
    # -------------------------------------------------------------
    @classmethod
    def _extract_from_hydration(cls, soup: BeautifulSoup, base_url: str) -> list[RawJobRecord]:
        records: list[RawJobRecord] = []
        next_data = soup.find("script", id="__NEXT_DATA__")
        if next_data and next_data.string:
            try:
                data = json.loads(next_data.string.strip())
                records = cls._search_dict_for_jobs(data, base_url)
            except (json.JSONDecodeError, TypeError):
                pass
        return records

    @classmethod
    def _search_dict_for_jobs(cls, node: Any, base_url: str) -> list[RawJobRecord]:
        results: list[RawJobRecord] = []
        if isinstance(node, dict):
            keys = {k.lower() for k in node.keys()}
            role_key = next(
                (k for k in ("title", "jobtitle", "role", "position") if k in keys),
                None,
            )
            comp_key = next(
                (k for k in ("company", "companyname", "organization", "employer") if k in keys),
                None,
            )

            if role_key and comp_key:
                role_val = node.get(role_key)
                comp_val = node.get(comp_key)
                if isinstance(comp_val, dict):
                    comp_val = comp_val.get("name") or comp_val.get("title")

                if (
                    isinstance(role_val, str)
                    and isinstance(comp_val, str)
                    and role_val
                    and comp_val
                ):
                    emp_val = None
                    for ek in (
                        "employeecount",
                        "employees",
                        "teamsize",
                        "headcount",
                        "numberofemployees",
                    ):
                        if ek in keys:
                            emp_val = str(node.get(ek) or "")
                            break
                    results.append(
                        RawJobRecord(
                            company_name=comp_val,
                            job_role=role_val,
                            employee_count_raw=emp_val,
                            page_url=base_url,
                            source_type="hydration",
                        )
                    )
            for v in node.values():
                results.extend(cls._search_dict_for_jobs(v, base_url))
        elif isinstance(node, list):
            for item in node:
                results.extend(cls._search_dict_for_jobs(item, base_url))
        return results

    # -------------------------------------------------------------
    # Tier 3: Heuristic DOM Repeated-Card Detector
    # -------------------------------------------------------------
    @classmethod
    def _extract_from_dom_cards(cls, soup: BeautifulSoup, base_url: str) -> list[RawJobRecord]:
        records: list[RawJobRecord] = []

        card_selectors = [
            ".employer-block",
            ".employer-row",
            "[ng-repeat*='opp']",
            "[ng-repeat*='job']",
            "article.card",
            "article[class*='job']",
            "article",
            "[data-testid*='job']",
            "[class*='job-card']",
            "[class*='jobCard']",
            "[class*='job_card']",
            "[class*='job-item']",
            "[class*='jobItem']",
            "[class*='job_item']",
            "[class*='job-listing']",
            "[class*='jobListing']",
            "[class*='job-post']",
            "[class*='vacancy']",
            "[class*='position-card']",
            "li[class*='job']",
            "div[class*='card'][class*='job']",
            "tr.athing",
            ".athing",
        ]

        elements: list[Tag] = []
        for selector in card_selectors:
            found = soup.select(selector)
            if len(found) >= 2:
                elements = found
                break

        if not elements:
            articles = soup.find_all("article")
            if len(articles) >= 2:
                elements = articles

        for el in elements:
            rec = cls._parse_card_element(el, base_url)
            if rec:
                records.append(rec)

        return records

    @classmethod
    def _parse_card_element(cls, el: Tag, base_url: str) -> RawJobRecord | None:
        """
        Extract individual semantic fields from a job card element.
        Never combines multi-sentence text or descriptions into role/company.
        """
        # 1. Job Role / Title Extraction
        # Look for dedicated heading or role tags
        role = None
        role_el = el.find(["h1", "h2", "h3", "h4", "h5"]) or el.select_one(
            "[class*='title'], [class*='role'], [class*='position'], [data-testid*='title']"
        )

        if not role_el:
            # Look for link pointing to a job detail page
            for a in el.find_all("a", href=True):
                href = a["href"].lower()
                if any(k in href for k in ("/job/", "/position/", "/career/", "/vacancy/")):
                    role_el = a
                    break

        if role_el:
            role = DataCleaner.clean_job_role(role_el.get_text(strip=True))

        # Check for compound "Company - Role" in headers (e.g. Instahyre "Veraxion - Data Enginner")
        compound_header = el.select_one(
            ".employer-job-name, [class*='job-name'], [class*='company-name']"
        )
        if compound_header:
            htext = DataCleaner.clean_text(compound_header.get_text())
            if " - " in htext:
                parts = [p.strip() for p in htext.split(" - ", 1)]
                if len(parts) == 2:
                    cand_comp = DataCleaner.clean_company_name(parts[0])
                    cand_role = DataCleaner.clean_job_role(parts[1])
                    if DataValidator.is_valid_company(cand_comp) and DataValidator.is_valid_role(
                        cand_role
                    ):
                        company = cand_comp
                        role = cand_role

        # 2. Company Name Extraction
        company = None

        # 2a. Check dedicated company selector
        company_el = el.select_one(
            "[class*='company'], [class*='employer'], [class*='organization'], [data-testid*='company'], [itemprop='hiringOrganization']"
        )
        if company_el:
            candidate = DataCleaner.clean_company_name(company_el.get_text(strip=True))
            if DataValidator.is_valid_company(candidate):
                company = candidate

        # 2b. Check dedicated company profile link
        if not company:
            comp_link = el.select_one(
                "a[href*='/company/'], a[href*='/employer/'], a[href*='/organization/'], a[href*='/org/']"
            )
            if comp_link:
                candidate = DataCleaner.clean_company_name(comp_link.get_text(strip=True))
                if DataValidator.is_valid_company(candidate):
                    company = candidate

        # 2c. Check metadata elements (e.g. .meta, .topline, .byline, .subtitle)
        if not company:
            meta_el = el.select_one(
                "[class*='meta'], [class*='topline'], [class*='byline'], [class*='subtitle'], [class*='details'], [class*='info']"
            )
            if meta_el:
                # Check for inner strong/b/span first
                inner_tag = meta_el.find(["strong", "b", "span", "a"])
                if inner_tag:
                    candidate = DataCleaner.clean_company_name(inner_tag.get_text(strip=True))
                    if DataValidator.is_valid_company(candidate) and candidate != role:
                        company = candidate

                # If still not found, split meta text on common delimiters: ·, •, |, /, -, –
                if not company:
                    raw_meta = meta_el.get_text(strip=True)
                    segments = [
                        s.strip() for s in re.split(r"[\u00b7\u2022|\/\-–—]", raw_meta) if s.strip()
                    ]
                    for seg in segments:
                        candidate = DataCleaner.clean_company_name(seg)
                        if (
                            not DataCleaner.is_noise_segment(candidate)
                            and DataValidator.is_valid_company(candidate)
                            and candidate != role
                        ):
                            company = candidate
                            break

        # 2d. Check secondary span elements with company classes
        if not company:
            spans = el.find_all(["span", "div"], recursive=True)
            for s in spans:
                cls_str = " ".join(s.get("class", []))
                # Exclude summary/description/employee/location/salary elements
                if any(
                    noise in cls_str.lower()
                    for noise in (
                        "summary",
                        "desc",
                        "excerpt",
                        "employee",
                        "headcount",
                        "size",
                        "salary",
                        "location",
                        "cat",
                    )
                ):
                    continue
                if any(k in cls_str.lower() for k in ("company", "employer", "hiring", "org-name")):
                    candidate = DataCleaner.clean_company_name(s.get_text(strip=True))
                    if DataValidator.is_valid_company(candidate) and candidate != role:
                        company = candidate
                        break

        # 3. Job URL & Company URL
        job_url = None
        company_url = None

        job_link = (
            el.select_one("a[href*='/job/'], a[href*='/position/'], a[href*='/career/']")
            or (role_el.find("a", href=True) if role_el and role_el.name != "a" else None)
            or el.find("a", href=True)
        )
        if job_link and job_link.get("href"):
            raw_href = job_link["href"].strip()
            job_url = urljoin(base_url, raw_href)

        comp_link = el.select_one("a[href*='/company/'], a[href*='/employer/'], a[href*='/org/']")
        if comp_link and comp_link.get("href"):
            raw_chref = comp_link["href"].strip()
            company_url = urljoin(base_url, raw_chref)

        # 4. Employee Count raw text from dedicated badges
        employee_raw = None
        emp_el = el.select_one(
            "[class*='employee'], [class*='headcount'], [class*='team-size'], [class*='size']"
        )
        if emp_el:
            candidate_emp = emp_el.get_text(strip=True)
            if not DataCleaner.is_location(candidate_emp):
                employee_raw = candidate_emp

        if not employee_raw:
            # Check spans/divs inside info blocks for employee count patterns (e.g. "200 - 500 employees")
            emp_span = el.find(
                lambda t: t.name in ["span", "div", "p"]
                and "employee" in t.get_text().lower()
                and len(t.get_text(strip=True)) < 60
            )
            if emp_span:
                employee_raw = emp_span.get_text(strip=True)

        # If both role and company are completely missing, card cannot be identified
        if not role and not company:
            return None

        return RawJobRecord(
            company_name=company or "",
            job_role=role or "",
            employee_count_raw=employee_raw,
            job_url=job_url,
            company_url=company_url,
            page_url=base_url,
            source_type="dom_card",
        )

    # -------------------------------------------------------------
    # Tier 4: HTML Tables
    # -------------------------------------------------------------
    @classmethod
    def _extract_from_tables(cls, soup: BeautifulSoup, base_url: str) -> list[RawJobRecord]:
        records: list[RawJobRecord] = []
        tables = soup.find_all("table")

        for table in tables:
            headers = [th.get_text().strip().lower() for th in table.find_all("th")]
            if not headers:
                continue

            role_idx = next(
                (
                    i
                    for i, h in enumerate(headers)
                    if any(k in h for k in ("role", "title", "position", "job"))
                ),
                None,
            )
            comp_idx = next(
                (
                    i
                    for i, h in enumerate(headers)
                    if any(k in h for k in ("company", "employer", "org"))
                ),
                None,
            )
            emp_idx = next(
                (
                    i
                    for i, h in enumerate(headers)
                    if any(k in h for k in ("employee", "people", "headcount", "size"))
                ),
                None,
            )

            if role_idx is None or comp_idx is None:
                continue

            rows = table.find_all("tr")[1:]
            for row in rows:
                cols = row.find_all(["td", "th"])
                if len(cols) > max(role_idx, comp_idx):
                    role_text = cols[role_idx].get_text().strip()
                    comp_text = cols[comp_idx].get_text().strip()
                    emp_text = (
                        cols[emp_idx].get_text().strip()
                        if emp_idx is not None and len(cols) > emp_idx
                        else None
                    )

                    if role_text and comp_text:
                        records.append(
                            RawJobRecord(
                                company_name=comp_text,
                                job_role=role_text,
                                employee_count_raw=emp_text,
                                page_url=base_url,
                                source_type="table",
                            )
                        )

        return records

    # -------------------------------------------------------------
    # Tier 5: Detail Page Deep Extraction
    # -------------------------------------------------------------
    @classmethod
    def extract_from_detail_html(
        cls, html_content: str, detail_url: str = ""
    ) -> RawJobRecord | None:
        """
        Deep extract a single job record from a dedicated job detail page.
        Tiers:
        1. Schema.org JSON-LD JobPosting
        2. Detail page DOM (h1, topline strong, etc.)
        """
        if not html_content or not html_content.strip():
            return None

        soup = BeautifulSoup(html_content, "lxml")

        # 1. JSON-LD on detail page
        json_ld_jobs = cls._extract_from_json_ld(soup, detail_url)
        for job in json_ld_jobs:
            if DataValidator.is_valid_company(job.company_name) and DataValidator.is_valid_role(
                job.job_role
            ):
                return job

        # 2. Detail DOM extraction
        # Role: primary h1
        role = None
        h1 = soup.find("h1")
        if h1:
            candidate_role = DataCleaner.clean_job_role(h1.get_text(strip=True))
            if DataValidator.is_valid_role(candidate_role):
                role = candidate_role

        # Company: topline strong, company class, or company link
        company = None
        comp_el = (
            soup.select_one(".topline strong, .topline b, [class*='company-name']")
            or soup.select_one(
                "[class*='company'], [class*='employer'], [itemprop='hiringOrganization']"
            )
            or soup.select_one("a[href*='/company/'], a[href*='/employer/']")
        )
        if comp_el:
            candidate_comp = DataCleaner.clean_company_name(comp_el.get_text(strip=True))
            if DataValidator.is_valid_company(candidate_comp):
                company = candidate_comp

        # Employee count on detail page
        emp_raw = None
        emp_el = soup.select_one(
            "[class*='employee'], [class*='headcount'], [class*='team-size'], [class*='size']"
        )
        if emp_el:
            emp_raw = emp_el.get_text(strip=True)

        if role and company:
            return RawJobRecord(
                company_name=company,
                job_role=role,
                employee_count_raw=emp_raw,
                job_url=detail_url,
                page_url=detail_url,
                source_type="detail_page",
            )

        return None
