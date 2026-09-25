"""Custom application exceptions."""


class ExtractionError(Exception):
    """Base exception for all extraction pipeline errors."""

    def __init__(self, message: str, details: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class InvalidUrlError(ExtractionError):
    """Raised when the user-provided URL fails validation or security checks."""


class SecurityViolationError(InvalidUrlError):
    """Raised when an SSRF or prohibited internal network access is attempted."""


class PageNavigationError(ExtractionError):
    """Raised when browser fails to navigate to or render a target page."""


class ContentExtractionError(ExtractionError):
    """Raised when extraction from page DOM or structured data fails."""


class ExcelExportError(ExtractionError):
    """Raised when writing or formatting the Excel workbook fails."""
