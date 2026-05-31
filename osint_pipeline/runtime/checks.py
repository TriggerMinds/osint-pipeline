from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..config import get_settings
from ..models.source import SourceMetadata, SourceResult, SourceType, FetchStatus


@dataclass
class RuntimeEnvironment:
    proxy_url: str = ""
    crawl4ai_available: bool = False
    crawl4ai_message: str = ""
    playwright_available: bool = False
    playwright_message: str = ""
    cloakbrowser_available: bool = False
    cloakbrowser_message: str = ""
    browser_engine: str = "playwright"
    has_proxy: bool = False


class RuntimeChecker:
    def __init__(self) -> None:
        self.settings = get_settings()

    def check_all(self) -> RuntimeEnvironment:
        env = RuntimeEnvironment()
        env.proxy_url = self._mask_proxy(self.settings.proxy_url)
        env.has_proxy = bool(self.settings.proxy_url)
        env.browser_engine = self.settings.browser_engine

        # Crawl4AI
        try:
            import crawl4ai  # noqa: F401
            env.crawl4ai_available = True
            env.crawl4ai_message = "crawl4ai installed"
        except ImportError:
            env.crawl4ai_available = False
            env.crawl4ai_message = (
                "crawl4ai not installed — run: pip install osint-pipeline[crawl]"
            )

        # Playwright
        try:
            import playwright  # noqa: F401
            env.playwright_available = True
            env.playwright_message = "playwright installed"
        except ImportError:
            env.playwright_available = False
            env.playwright_message = (
                "playwright not installed — run: pip install osint-pipeline[browser]"
            )

        # CloakBrowser
        exe = self.settings.cloakbrowser_executable
        if exe:
            exe_path = Path(exe)
            if exe_path.exists():
                env.cloakbrowser_available = True
                env.cloakbrowser_message = f"found at: {exe}"
            else:
                env.cloakbrowser_message = f"not found at: {exe}"
        else:
            env.cloakbrowser_message = (
                "not configured (set OSINT_CLOAKBROWSER_EXECUTABLE)"
            )

        return env

    def get_browser_infos(self) -> list[tuple[str, bool, str]]:
        env = self.check_all()
        return [
            ("engine", True, env.browser_engine),
            ("playwright", env.playwright_available, env.playwright_message),
            ("cloakbrowser", env.cloakbrowser_available, env.cloakbrowser_message),
        ]

    @staticmethod
    def _mask_proxy(url: str) -> str:
        if not url:
            return "(none)"
        # Show scheme and host, mask credentials
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if parsed.password:
                return f"{parsed.scheme}://{parsed.username}:***@{parsed.hostname}:{parsed.port or ''}"
            return url
        except Exception:
            return "(invalid)"
