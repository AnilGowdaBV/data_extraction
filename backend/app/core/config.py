"""Application configuration settings loaded from environment or defaults."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for the Bulk Job Extractor."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"
    APP_NAME: str = "Bulk Job Extractor"
    PORT: int = 8000
    HOST: str = "127.0.0.1"
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Scraper & Crawler
    HEADLESS_BROWSER: bool = True
    PAGE_TIMEOUT_MS: int = 30000
    MAX_RECORDS: int = 100000
    MAX_CONCURRENT_PAGES: int = 3
    REQUEST_DELAY_MS: int = 500
    MAX_SCROLL_ATTEMPTS: int = 5
    MAX_PAGINATION_DEPTH: int = 1000

    # Security
    ALLOW_PRIVATE_IPS: bool = False

    # Persistence / Database
    DB_PATH: str = "backend/data/jobs.db"

    # Google Sheets Integration
    GOOGLE_SHEETS_WEBHOOK_URL: str = (
        "https://script.google.com/macros/s/AKfycbx2cFrtQBimzhlJem5ZRA_PPDgvq0vMvEw-grXRqNXLIVIDeWn3MSbqwZdijO3-mv6r/exec"
    )
    GOOGLE_SHEET_URL: str = (
        "https://docs.google.com/spreadsheets/d/1wrwZlp3kJRDdRvwIgCrrbd3rCJFHEsIigLop-hwHPSs/edit?usp=sharing"
    )


settings = Settings()
