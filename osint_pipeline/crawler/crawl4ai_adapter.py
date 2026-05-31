from __future__ import annotations

from typing import Optional

from ..models.source import SourceResult


class Crawl4AIAdapter:
    def __init__(self) -> None:
        self._available = False
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

    async def crawl(self, url: str) -> Optional[SourceResult]:
        if not self._available:
            return None

        from crawl4ai import AsyncWebCrawler  # type: ignore

        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)

        return SourceResult(
            metadata=result.metadata if hasattr(result, "metadata") else None,  # type: ignore
            content=result.markdown if hasattr(result, "markdown") else str(result),
        )
