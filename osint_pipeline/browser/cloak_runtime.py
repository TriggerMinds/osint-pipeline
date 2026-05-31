from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from ..config import get_settings
from .runtime import BrowserRenderResult, BrowserRuntime, RuntimeCheckResult

# Only http/https URLs are allowed through to the browser binary.
_ALLOWED_URL_SCHEMES = frozenset(["http", "https"])
# Reject control characters and shell-significant chars in the URL value.
_URL_REJECT_RE = re.compile(r"[\x00-\x1f\x7f\"'`$<>|&;()]")


class CloakBrowserRuntime(BrowserRuntime):
    def __init__(self) -> None:
        self.settings = get_settings()

    async def health(self) -> RuntimeCheckResult:
        exe = self.settings.cloakbrowser_executable
        if not exe:
            return RuntimeCheckResult(
                available=False,
                message="OSINT_CLOAKBROWSER_EXECUTABLE not set — point it to the CloakBrowser binary",
            )
        exe_path = Path(exe)
        if not exe_path.exists():
            return RuntimeCheckResult(
                available=False,
                message=f"CloakBrowser executable not found at: {exe}",
            )
        return RuntimeCheckResult(
            available=True,
            message=f"CloakBrowser found at: {exe}",
        )

    async def render(self, url: str) -> BrowserRenderResult:
        exe = self.settings.cloakbrowser_executable
        if not exe:
            return BrowserRenderResult(
                html="", error="CloakBrowser executable not configured"
            )

        # Validate URL before passing to an external binary.
        parsed = urlparse(url)
        if parsed.scheme not in _ALLOWED_URL_SCHEMES:
            return BrowserRenderResult(
                html="",
                error=f"CloakBrowser render rejected URL: unsupported scheme '{parsed.scheme}'",
            )
        if _URL_REJECT_RE.search(url):
            return BrowserRenderResult(
                html="",
                error="CloakBrowser render rejected URL: contains disallowed characters",
            )

        try:
            result = subprocess.run(
                [exe, "--url", url, "--headless"],
                capture_output=True,
                text=True,
                timeout=self.settings.browser_timeout,
            )
            return BrowserRenderResult(
                html=result.stdout,
                error=result.stderr if result.returncode != 0 else None,
            )
        except FileNotFoundError:
            return BrowserRenderResult(
                html="",
                error=f"CloakBrowser binary not found at: {exe}",
            )
        except subprocess.TimeoutExpired:
            return BrowserRenderResult(
                html="", error="CloakBrowser timed out"
            )

    async def close(self) -> None:
        pass
