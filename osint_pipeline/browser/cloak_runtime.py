from __future__ import annotations

import subprocess
from pathlib import Path

from ..config import get_settings
from .runtime import BrowserRenderResult, BrowserRuntime, RuntimeCheckResult


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
