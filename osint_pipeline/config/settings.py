from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="OSINT_",
        extra="ignore",
    )

    # LLM
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-reasoner"

    # Connectors
    searxng_instances: str = "http://localhost:8888"
    gdelt_base_url: str = "https://api.gdeltproject.org/api/v2"
    commoncrawl_base_url: str = "https://index.commoncrawl.org"
    archive_cdx_url: str = "https://web.archive.org/cdx/search/cdx"
    archive_wayback_url: str = "https://web.archive.org/web"

    # Retry / timeout
    max_concurrent_fetches: int = 10
    request_timeout: int = 30
    request_retries: int = 3
    request_backoff_factor: float = 1.5
    request_max_backoff: float = 60.0
    request_jitter: float = 0.5
    retry_status_codes: str = "429,500,502,503,504"

    # Pipeline tuning
    max_queries_per_expansion: int = 15
    evidence_min_confidence: float = 0.3

    searxng_timeout: int = 30
    gdelt_timeout: int = 30
    archive_timeout: int = 60
    commoncrawl_timeout: int = 60

    # Network transport
    proxy_url: str = ""

    # Browser runtime
    browser_engine: str = "playwright"
    cloakbrowser_executable: str = ""
    browser_headless: bool = True
    browser_user_data_dir: str = ""
    browser_timeout: int = 30

    # Crawl runtime
    crawl_wait_for_js: bool = True
    crawl_output_format: str = "markdown"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
