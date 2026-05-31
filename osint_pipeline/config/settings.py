from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="OSINT_",
        extra="ignore",
    )

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-reasoner"

    searxng_instances: str = "http://localhost:8888"
    gdelt_base_url: str = "https://api.gdeltproject.org/api/v2"
    commoncrawl_base_url: str = "https://index.commoncrawl.org"
    archive_cdx_url: str = "https://web.archive.org/cdx/search/cdx"
    archive_wayback_url: str = "https://web.archive.org/web"

    max_concurrent_fetches: int = 10
    request_timeout: int = 30
    max_queries_per_expansion: int = 15
    evidence_min_confidence: float = 0.3


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
