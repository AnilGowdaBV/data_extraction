"""Data cleaner for normalizing textual fields extracted from websites."""

import html
import re


class DataCleaner:
    """Normalizes and sanitizes extracted strings without altering meaning."""

    _WHITESPACE_REGEX = re.compile(r"[\r\n\t\s]+")
    _NON_PRINTABLE_REGEX = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")

    # Curated locations and region indicators
    KNOWN_LOCATIONS = {
        "usa",
        "us",
        "united states",
        "u.s.",
        "u.s.a.",
        "uk",
        "united kingdom",
        "u.k.",
        "canada",
        "germany",
        "france",
        "india",
        "australia",
        "europe",
        "emea",
        "apac",
        "americas",
        "worldwide",
        "remote",
        "global",
        "anywhere",
        "latam",
        "spain",
        "italy",
        "netherlands",
        "brazil",
        "mexico",
        "philippines",
        "singapore",
        "ireland",
        "poland",
        "japan",
        "china",
        "northern america",
        "north america",
        "south america",
        "european timezones",
        "cst timezone",
        "est timezone",
        "pst timezone",
    }

    COMPANY_AFFIXES = {
        "corp",
        "corporation",
        "inc",
        "incorporated",
        "llc",
        "ltd",
        "limited",
        "technologies",
        "technology",
        "tech",
        "systems",
        "solutions",
        "data",
        "software",
        "digital",
        "labs",
        "media",
        "group",
        "studio",
        "studios",
        "health",
        "wellness",
        "consulting",
        "partners",
        "capital",
        "ventures",
        "interactive",
        "network",
    }

    LOCATION_WORDS = {
        "remote",
        "worldwide",
        "global",
        "anywhere",
        "usa",
        "us",
        "uk",
        "canada",
        "europe",
        "european",
        "emea",
        "latam",
        "apac",
        "asia",
        "asian",
        "africa",
        "african",
        "timezone",
        "timezones",
        "cst",
        "est",
        "pst",
        "cet",
        "gmt",
        "utc",
        "france",
        "germany",
        "spain",
        "italy",
        "india",
        "australia",
        "mexico",
        "brazil",
        "ireland",
        "netherlands",
        "poland",
        "philippines",
        "singapore",
        "america",
        "northern",
        "southern",
        "eastern",
        "western",
    }

    DATE_KEYWORDS = re.compile(
        r"\b(?:posted|ago|today|yesterday|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{4})\b",
        re.IGNORECASE,
    )

    SALARY_KEYWORDS = re.compile(
        r"(?:\$|€|£|usd|eur|gbp|\b(?:k|yr|year|hour|hr|month|mo)\b)",
        re.IGNORECASE,
    )

    JOB_TYPE_KEYWORDS = re.compile(
        r"\b(?:full[- ]?time|part[- ]?time|contract|contractor|freelance|internship|temporary|entry[- ]?level)\b",
        re.IGNORECASE,
    )

    DESCRIPTION_STARTERS = re.compile(
        r"^(?:looking for|we are looking for|we are hiring|who we'?re looking for|who we are|are you a|are you looking|join our|about us|about the role|the ideal candidate|company description|role:|a day in the life|in this role|as a|our organization is seeking|overview:)\b",
        re.IGNORECASE,
    )

    @classmethod
    def clean_text(cls, text: str | None) -> str:
        """Sanitize generic string: unescape HTML, collapse whitespace, strip edges."""
        if not text:
            return ""

        cleaned = html.unescape(text)
        cleaned = cleaned.replace("\xa0", " ")
        cleaned = cls._NON_PRINTABLE_REGEX.sub("", cleaned)
        cleaned = cls._WHITESPACE_REGEX.sub(" ", cleaned)

        return cleaned.strip()

    @classmethod
    def is_location(cls, text: str | None) -> bool:
        """Return True if text represents a pure location or geographic indicator."""
        if not text:
            return False
        clean = cls.clean_text(text).lower()
        if clean in cls.KNOWN_LOCATIONS:
            return True

        tokens = re.findall(r"[a-z]+", clean)
        if not tokens:
            return False

        # If any token is a known company affix (like Corp, Inc, Data, Tech), it is NOT a location
        if any(t in cls.COMPANY_AFFIXES for t in tokens):
            return False

        # If all tokens are location words
        if all(t in cls.LOCATION_WORDS for t in tokens):
            return True

        # Matches city/state patterns like "San Francisco, CA" or "New York, NY"
        if re.search(r"^[a-zA-Z\s]+,\s*[A-Z]{2}$", clean.upper()):
            return True

        return False

    @classmethod
    def is_noise_segment(cls, text: str | None) -> bool:
        """Return True if a metadata segment is noise (location, date, salary, or job type)."""
        if not text:
            return True
        clean = cls.clean_text(text)
        if not clean:
            return True
        if cls.is_location(clean):
            return True
        words = clean.split()
        if cls.DATE_KEYWORDS.search(clean) and len(words) <= 5:
            return True
        if cls.SALARY_KEYWORDS.search(clean) and len(words) <= 5:
            return True
        if cls.JOB_TYPE_KEYWORDS.search(clean) and len(words) <= 4:
            return True
        return False

    @classmethod
    def is_description_or_sentence(cls, text: str | None) -> bool:
        """Check if text looks like a full sentence or job description paragraph."""
        if not text:
            return False
        clean = cls.clean_text(text)
        if cls.DESCRIPTION_STARTERS.search(clean):
            return True
        if re.search(r"\.\s+[A-Z]", clean):
            return True
        if len(clean) > 120:
            return True
        return False

    @classmethod
    def clean_company_name(cls, company_name: str | None) -> str:
        """Normalize company name, removing excess surrounding punctuation and delimiters."""
        cleaned = cls.clean_text(company_name)
        # Strip leading numbering like '1. ', '2) ', requiring whitespace after dot/paren
        cleaned = re.sub(r"^\d+[\.\)]\s+", "", cleaned)
        # Strip trailing/leading quotes, dashes, dots, or delimiters
        cleaned = cleaned.strip("\"'’` -–—|·•/\\:;,")
        return cleaned

    @classmethod
    def clean_job_role(cls, job_role: str | None) -> str:
        """Normalize job title/role."""
        cleaned = cls.clean_text(job_role)
        # Strip leading numbering if present
        cleaned = re.sub(r"^\d+[\.\)]\s+", "", cleaned)
        # Strip trailing/leading quotes, dashes, dots
        cleaned = cleaned.strip("\"'’` -–—|·•/\\:;,")
        return cleaned

    @classmethod
    def normalize_key(cls, text: str) -> str:
        """Normalize a string for case-insensitive and punctuation-agnostic comparison."""
        cleaned = cls.clean_text(text).lower()
        return re.sub(r"[^a-z0-9]", "", cleaned)
