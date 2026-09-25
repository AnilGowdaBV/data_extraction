"""Validation logic for extracted and processed job records."""

import re

from backend.app.models.job import ProcessedJobRecord
from backend.app.processors.cleaner import DataCleaner


class DataValidator:
    """Validates records before inclusion in the final dataset and Excel output."""

    UI_ACTION_WORDS = {
        "apply",
        "apply now",
        "quick apply",
        "easy apply",
        "view job",
        "read more",
        "search",
        "submit",
        "details",
        "share",
        "more info",
        "click here",
        "learn more",
    }

    @classmethod
    def is_valid_company(cls, company_name: str | None) -> bool:
        """Validate company name semantics."""
        if not company_name or not company_name.strip():
            return False

        clean = DataCleaner.clean_company_name(company_name)
        if len(clean) < 2 or len(clean) > 80:
            return False

        # Reject UI actions
        if clean.lower() in cls.UI_ACTION_WORDS:
            return False

        # Reject pure locations (e.g. 'USA', 'Worldwide', 'Remote')
        if DataCleaner.is_location(clean):
            return False

        # Reject descriptions or sentences
        if DataCleaner.is_description_or_sentence(clean):
            return False

        return True

    @classmethod
    def is_valid_role(cls, job_role: str | None) -> bool:
        """Validate job role/title semantics."""
        if not job_role or not job_role.strip():
            return False

        clean = DataCleaner.clean_job_role(job_role)
        if len(clean) < 2 or len(clean) > 120:
            return False

        # Reject UI actions
        if clean.lower() in cls.UI_ACTION_WORDS:
            return False

        # Reject descriptions, paragraphs, or multiple sentences
        if DataCleaner.is_description_or_sentence(clean):
            return False

        # Reject if contains bullet or newline formatting
        if "\n" in clean or re.search(r"^\s*[-•*]\s+", clean):
            return False

        return True

    @classmethod
    def is_valid_employee_count(cls, number_of_people: int | str) -> bool:
        """Validate employee count format."""
        if isinstance(number_of_people, int):
            return number_of_people >= 0
        if isinstance(number_of_people, str):
            clean = number_of_people.strip()
            if clean == "N/A":
                return True
            if re.search(r"\b(approx|about|around|estimate|unknown)\b", clean, re.IGNORECASE):
                return False
            if re.search(
                r"^\d+(?:,\d+)?(?:\s*[-–—]\s*\d+(?:,\d+)?)?\s*(?:employees)?$", clean, re.IGNORECASE
            ) or re.search(r"^more than\s*\d+(?:,\d+)?\s*employees$", clean, re.IGNORECASE):
                return True
        return False

    @classmethod
    def is_valid_record(
        cls,
        company_name: str | None,
        job_role: str | None,
        number_of_people: int | str,
    ) -> bool:
        """
        Validate record criteria:
        1. Company Name must be valid semantic entity (not location, description, or action).
        2. Job Role must be valid job title (not description, paragraph, or action).
        3. Company Name and Job Role must NOT be identical.
        4. Number of People must be a non-negative integer or 'N/A'.
        """
        if not cls.is_valid_company(company_name):
            return False

        if not cls.is_valid_role(job_role):
            return False

        # Company and role must not be identical
        if DataCleaner.normalize_key(company_name or "") == DataCleaner.normalize_key(
            job_role or ""
        ):
            return False

        if not cls.is_valid_employee_count(number_of_people):
            return False

        return True

    @classmethod
    def validate_processed_record(cls, record: ProcessedJobRecord) -> bool:
        """Helper to validate a ProcessedJobRecord instance."""
        return cls.is_valid_record(
            company_name=record.company_name,
            job_role=record.job_role,
            number_of_people=record.number_of_people,
        )
