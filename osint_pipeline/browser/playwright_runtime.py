from __future__ import annotations

from ..config import get_settings
from .runtime import BrowserRenderResult, BrowserRuntime, RuntimeCheckResult


class PlaywrightRuntime(BrowserRuntime):
    def __init__(self) -> None:
        self.settings = get_settings()
        self._browser = None

    async def health(self) -> RuntimeCheckResult:
        try:
            import playwright  # noqa: F401
        except ImportError:
            return RuntimeCheckResult(
                available=False,
                message="playwright not installed — run: pip install playwright && playwright install chromium",
            )
        return RuntimeCheckResult(available=True, message="playwright available")

    async def render(self, url: str) -> BrowserRenderResult:
        from playwright.async_api import async_playwright  # type: ignore

        proxy = self.settings.proxy_url or None

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=self.settings.browser_headless,
                proxy={"server": proxy} if proxy else None,
                args=["--no-sandbox"],
            )
            try:
                page = await browser.new_page()
                await page.goto(url, timeout=self.settings.browser_timeout * 1000)
                html = await page.content()
                text = await page.inner_text("body")
                return BrowserRenderResult(html=html, text=text)
            except Exception as exc:
                return BrowserRenderResult(
                    html="", error=f"Playwright render failed: {type(exc).__name__}"
                )
            finally:
                await browser.close()

    async def close(self) -> None:
        pass
