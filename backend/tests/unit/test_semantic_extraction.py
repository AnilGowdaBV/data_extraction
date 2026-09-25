"""Unit tests for semantic field extraction, noise filtering, and validation."""

from bs4 import BeautifulSoup

from backend.app.extractors.job_extractor import JobExtractor
from backend.app.processors.cleaner import DataCleaner
from backend.app.processors.validator import DataValidator


def test_remoterise_card_extraction() -> None:
    card_html = """
    <article class="card">
      <span class="cat">Community Moderation</span>
      <h3>
        <a href="/job/content-reviewer-us-telus-digital-2089990">Content Reviewer - US</a>
      </h3>
      <div class="meta">
        TELUS Digital · USA
      </div>
      <p class="summary">
        Looking for a freelance opportunity where you can make an impact on technology from the comfort of your home?…
      </p>
    </article>
    """
    soup = BeautifulSoup(card_html, "lxml")
    card = soup.select_one("article.card")
    record = JobExtractor._parse_card_element(card, "https://remoterisehq.com/")

    assert record is not None
    assert record.company_name == "TELUS Digital"
    assert record.job_role == "Content Reviewer - US"
    assert record.employee_count_raw is None
    assert (
        record.job_url == "https://remoterisehq.com/job/content-reviewer-us-telus-digital-2089990"
    )


def test_metadata_delimiter_isolation() -> None:
    card_html = """
    <article class="card">
      <h3><a href="/jobs/1">Copywriter</a></h3>
      <div class="meta">
        Coalition Technologies • Worldwide • Full-time • $50,000/yr
      </div>
      <p class="summary">Write great content for SEO.</p>
    </article>
    """
    soup = BeautifulSoup(card_html, "lxml")
    card = soup.select_one("article.card")
    record = JobExtractor._parse_card_element(card, "https://example.com")

    assert record is not None
    assert record.company_name == "Coalition Technologies"
    assert record.job_role == "Copywriter"


def test_location_never_becomes_company() -> None:
    assert DataCleaner.is_location("USA") is True
    assert DataCleaner.is_location("Worldwide") is True
    assert DataCleaner.is_location("Remote") is True
    assert DataCleaner.is_location("Europe, European timezones") is True
    assert DataCleaner.is_location("San Francisco, CA") is True

    # Real companies with tech/corp words are NOT locations
    assert DataCleaner.is_location("TELUS Digital") is False
    assert DataCleaner.is_location("Global Data Corp") is False
    assert DataCleaner.is_location("Worldwide Studios") is False

    # Validator rejects pure locations as company names
    assert DataValidator.is_valid_company("USA") is False
    assert DataValidator.is_valid_company("Worldwide") is False
    assert DataValidator.is_valid_company("Remote") is False
    assert DataValidator.is_valid_company("TELUS Digital") is True


def test_description_never_becomes_company_or_role() -> None:
    desc = (
        "Looking for a freelance opportunity where you can make an impact on technology "
        "from the comfort of your home? Join our community today."
    )
    assert DataCleaner.is_description_or_sentence(desc) is True
    assert DataValidator.is_valid_company(desc) is False
    assert DataValidator.is_valid_role(desc) is False


def test_company_role_identical_rejected() -> None:
    assert (
        DataValidator.is_valid_record(
            company_name="TELUS Digital",
            job_role="TELUS Digital",
            number_of_people="N/A",
        )
        is False
    )


def test_employee_count_validation() -> None:
    assert DataValidator.is_valid_employee_count(250) is True
    assert DataValidator.is_valid_employee_count(0) is True
    assert DataValidator.is_valid_employee_count("N/A") is True
    assert DataValidator.is_valid_employee_count(-5) is False
    assert DataValidator.is_valid_employee_count("approx 50") is False
    assert DataValidator.is_valid_employee_count("Unknown") is False


def test_detail_page_extraction() -> None:
    detail_html = """
    <!DOCTYPE html>
    <html>
    <head>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Content Reviewer - US",
        "hiringOrganization": {
          "@type": "Organization",
          "name": "TELUS Digital"
        }
      }
      </script>
    </head>
    <body>
      <h1>Content Reviewer - US</h1>
      <div class="topline"><strong>TELUS Digital</strong> · USA</div>
    </body>
    </html>
    """
    rec = JobExtractor.extract_from_detail_html(
        detail_html, "https://remoterisehq.com/job/content-reviewer-us-telus-digital-2089990"
    )
    assert rec is not None
    assert rec.company_name == "TELUS Digital"
    assert rec.job_role == "Content Reviewer - US"
