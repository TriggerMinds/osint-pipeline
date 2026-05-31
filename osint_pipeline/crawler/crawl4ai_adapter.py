from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from ..models.source import SourceMetadata, SourceResult, SourceType, FetchStatus


class Crawl4AIAdapter:
    def __init__(self) -> None:
        self._available: bool = False
        self._check_available()

    def _check_available(self) -> None:
        try:
            import crawl4ai  # noqa: F401
            self._available = True
        except ImportError:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    @property
    def install_hint(self) -> str:
        return (
            "crawl4ai not installed\n"
            "  pip install osint-pipeline[crawl]\n"
            "  # or: pip install crawl4ai"
        )

    async def crawl_url(
        self,
        url: str,
        proxy_url: str | None = None,
        wait_for_js: bool = True,
        output_format: str = "markdown",
    ) -> Optional[SourceResult]:
        if not self._available:
            return None

        from crawl4ai import AsyncWebCrawler  # type: ignore

        now = datetime.now(timezone.utc).isoformat()
        domain = self._extract_domain(url)

        crawler_kwargs = {}
        if proxy_url:
            crawler_kwargs["proxy"] = proxy_url

        async with AsyncWebCrawler(**crawler_kwargs) as crawler:
            try:
                result = await crawler.arun(
                    url=url,
                    wait_for_js=wait_for_js,
                    output_format=output_format,
                )
            except Exception as exc:
                return SourceResult(
                    metadata=SourceMetadata(
                        url=url,
                        source_type=SourceType.CRAWL4AI,
                        language="unknown",
                        discovered_by_query=url,
                        discovered_at=now,
                        domain=domain,
                        fetch_status=FetchStatus.ERROR,
                    ),
                    error=f"Crawl4AI crawl failed: {type(exc).__name__}",
                )

        content = None
        if hasattr(result, "markdown") and result.markdown:
            content = result.markdown
        elif hasattr(result, "html") and result.html:
            content = result.html
        elif hasattr(result, "text") and result.text:
            content = result.text
        elif result and isinstance(result, str):
            content = result

        return SourceResult(
            metadata=SourceMetadata(
                url=url,
                source_type=SourceType.CRAWL4AI,
                language="unknown",
                discovered_by_query=url,
                discovered_at=now,
                domain=domain,
                status_code=200 if content else None,
                fetch_status=FetchStatus.SUCCESS if content else FetchStatus.ERROR,
            ),
            content=content,
        )

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            return urlparse(url).netloc
        except Exception:
            return ""
