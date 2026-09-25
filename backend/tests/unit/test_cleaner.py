"""Unit tests for DataCleaner."""

from backend.app.processors.cleaner import DataCleaner


def test_clean_text_whitespace() -> None:
    raw = "   Software    Engineer \n\t  "
    assert DataCleaner.clean_text(raw) == "Software Engineer"


def test_clean_text_html_entities() -> None:
    raw = "R&amp;D Specialist &lt;Lead&gt; &#39;Platform&#39;"
    assert DataCleaner.clean_text(raw) == "R&D Specialist <Lead> 'Platform'"


def test_clean_company_name() -> None:
    assert DataCleaner.clean_company_name(' "ABC Technologies" ') == "ABC Technologies"
    assert DataCleaner.clean_company_name(" - Microsoft - ") == "Microsoft"
    assert DataCleaner.clean_company_name("Amazon Web Services |") == "Amazon Web Services"


def test_clean_job_role() -> None:
    assert (
        DataCleaner.clean_job_role("  'Senior Backend Developer'  ") == "Senior Backend Developer"
    )
    assert DataCleaner.clean_job_role("Full Stack Engineer -") == "Full Stack Engineer"


def test_normalize_key() -> None:
    k1 = DataCleaner.normalize_key("Microsoft, Inc.")
    k2 = DataCleaner.normalize_key("  microsoft inc  ")
    assert k1 == k2
    assert k1 == "microsoftinc"
