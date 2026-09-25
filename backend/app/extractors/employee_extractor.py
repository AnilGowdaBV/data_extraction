"""Extractor and normalizer for employee counts / number of people."""

import re
from typing import Union

from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class EmployeeCountExtractor:
    """
    Extracts and normalizes company employee counts and ranges.

    Supports:
    - Standard tiers: e.g. 1 -> '1 - 10 employees', 200 -> '200 - 500 employees', 1000 -> 'More than 1000 employees'
    - Text ranges: e.g. '200 - 500 employees', 'Founded in 2012 • 200 - 500 employees'
    - Explicit counts: e.g. '250 employees', '1,250 staff'
    - If unavailable or ambiguous, return 'N/A'
    """

    INSTAHYRE_TIERS = {
        1: "1 - 10 employees",
        10: "10 - 50 employees",
        50: "50 - 200 employees",
        200: "200 - 500 employees",
        500: "500 - 1000 employees",
        1000: "More than 1000 employees",
    }

    # Matches "More than 1000", "Over 500", "1000+"
    _MORE_THAN_PATTERN = re.compile(
        r"(?:more than|over|>)\s*([0-9,]+)\s*(?:employees|people|staff)?|"
        r"([0-9,]+)\+\s*(?:employees|people|staff)?",
        re.IGNORECASE,
    )

    # Matches "200 - 500 employees", "10 - 50", "50-200 staff"
    _RANGE_PATTERN = re.compile(
        r"([0-9,]+)\s*(?:[-–—]|to)\s*([0-9,]+)\s*(?:employees|people|staff|members)?",
        re.IGNORECASE,
    )

    # Matches explicit counts like "250 employees", "1,250 staff", "Employees: 250"
    _LABEL_PATTERNS = [
        re.compile(
            r"(?:employees|headcount|team\s*size|company\s*size|staff|people|workforce)\s*[:\-–]?\s*([0-9,]+(?:\.\d+)?\s*[kmbKMB]?)(?:\s*(?:employees|people|staff|members))?",
            re.IGNORECASE,
        ),
        re.compile(
            r"([0-9,]+(?:\.\d+)?\s*[kmbKMB]?)\s+(?:employees|people|staff|team\s*members|workers)",
            re.IGNORECASE,
        ),
    ]

    _PURE_NUMBER_PATTERN = re.compile(r"^\s*([0-9,]+(?:\.\d+)?\s*[kmbKMB]?)\s*$")

    @classmethod
    def parse_count(cls, raw_text: Union[str, int, float, None]) -> str:
        """
        Parse raw text or numeric tier into a formatted employee count string (e.g. '200 - 500 employees') or 'N/A'.
        """
        if raw_text is None:
            return "N/A"

        text = str(raw_text).strip()
        if not text:
            return "N/A"

        # 1. Check if direct integer or float matching standard tier
        try:
            val = int(float(text))
            if val in cls.INSTAHYRE_TIERS:
                return cls.INSTAHYRE_TIERS[val]
        except (ValueError, OverflowError):
            pass

        # 2. Check "More than X employees" or "X+ employees"
        more_match = cls._MORE_THAN_PATTERN.search(text)
        if more_match:
            count = more_match.group(1) or more_match.group(2)
            return f"More than {count} employees"

        # 3. Check range pattern "X - Y employees"
        range_match = cls._RANGE_PATTERN.search(text)
        if range_match:
            c1 = range_match.group(1).strip()
            c2 = range_match.group(2).strip()
            return f"{c1} - {c2} employees"

        # 4. Check labeled patterns like "250 employees"
        for pattern in cls._LABEL_PATTERNS:
            match = pattern.search(text)
            if match:
                norm = cls._normalize_numeric_string(match.group(1))
                if norm is not None:
                    if norm in cls.INSTAHYRE_TIERS:
                        return cls.INSTAHYRE_TIERS[norm]
                    return f"{norm:,} employees"

        # 5. Check if pure number
        pure_match = cls._PURE_NUMBER_PATTERN.match(text)
        if pure_match:
            norm = cls._normalize_numeric_string(pure_match.group(1))
            if norm is not None:
                if norm in cls.INSTAHYRE_TIERS:
                    return cls.INSTAHYRE_TIERS[norm]
                return f"{norm:,} employees"

        return "N/A"

    @classmethod
    def _normalize_numeric_string(cls, num_str: str) -> int | None:
        """Convert '1,250', '250', '1.2K' into a clean integer if unambiguous."""
        if not num_str:
            return None

        clean = num_str.strip().replace(",", "")
        unit_multiplier = 1

        if clean.lower().endswith("k"):
            unit_multiplier = 1_000
            clean = clean[:-1].strip()
        elif clean.lower().endswith("m"):
            unit_multiplier = 1_000_000
            clean = clean[:-1].strip()
        elif clean.lower().endswith("b"):
            unit_multiplier = 1_000_000_000
            clean = clean[:-1].strip()

        try:
            val = float(clean) * unit_multiplier
            int_val = int(round(val))
            if int_val >= 0:
                return int_val
            return None
        except (ValueError, OverflowError):
            return None
