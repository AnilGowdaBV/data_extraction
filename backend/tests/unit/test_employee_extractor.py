"""Unit tests for EmployeeCountExtractor."""

import pytest

from backend.app.extractors.employee_extractor import EmployeeCountExtractor


@pytest.mark.parametrize(
    "raw_input, expected",
    [
        ("200 - 500 employees", "200 - 500 employees"),
        ("Founded in 2012 • 200 - 500 employees", "200 - 500 employees"),
        ("Founded in 2015 • More than 1000 employees", "More than 1000 employees"),
        ("1000+ staff", "More than 1000 employees"),
        ("Over 500 employees", "More than 500 employees"),
        ("10", "10 - 50 employees"),
        ("1", "1 - 10 employees"),
        ("50", "50 - 200 employees"),
        ("200", "200 - 500 employees"),
        ("500", "500 - 1000 employees"),
        ("1000", "More than 1000 employees"),
        (200, "200 - 500 employees"),
        ("250 employees", "250 employees"),
        ("1,250 employees", "1,250 employees"),
    ],
)
def test_valid_employee_counts(raw_input: str | int, expected: str) -> None:
    assert EmployeeCountExtractor.parse_count(raw_input) == expected


@pytest.mark.parametrize(
    "raw_input",
    [
        (None),
        (""),
        ("   "),
        ("Unknown"),
        ("Competitive"),
        ("Competitive Salary"),
        ("Not specified"),
        ("Full-time"),
        ("Remote"),
    ],
)
def test_missing_or_invalid_employee_counts(raw_input: str | None) -> None:
    assert EmployeeCountExtractor.parse_count(raw_input) == "N/A"
