from __future__ import annotations
import asyncio
from typing import Dict, List, Optional
from ..models.source import SourceResult, SourceType, FetchStatus
from ..models.query import QueryBatch, MultilingualQuery
from ..sources import SearXNGSearcher, GDELTClient, CommonCrawlClient, InternetArchiveClient


class FetchLayer:
    def __init__(
        self,
        searxng: Optional[SearXNGSearcher] = None,
        gdelt: Optional[GDELTClient] = None,
        common_crawl: Optional[CommonCrawlClient] = None,
        internet_archive: Optional[InternetArchiveClient] = None,
        max_concurrent: int = 10,
    ) -> None:
        self.searxng = searxng
        self.gdelt = gdelt
        self.common_crawl = common_crawl
        self.internet_archive = internet_archive
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_all(
        self,
        plan: Dict[SourceType, List[str]],
        multilingual_queries: List[MultilingualQuery],
    ) -> Dict[SourceType, List[SourceResult]]:
        tasks = []

        for source_type, queries in plan.items():
            for query in queries:
                tasks.append(self._fetch_single(source_type, query))

        # Also run multilingual queries through SearXNG
        for mq in multilingual_queries:
            if mq.language != "en" and SourceType.SEARXNG in plan:
                tasks.append(self._fetch_single(SourceType.SEARXNG, mq.translated_query, mq.language))

        results: Dict[SourceType, List[SourceResult]] = {}
        batches = [tasks[i:i + self.max_concurrent] for i in range(0, len(tasks), self.max_concurrent)]

        for batch in batches:
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            for source_type, query, lang, res in batch_results if batch_results else []:
                if isinstance(res, Exception):
                    continue
                if source_type not in results:
                    results[source_type] = []
                results[source_type].extend(res)

        return results

    async def _fetch_single(
        self, source_type: SourceType, query: str, language: str = "en",
    ):
        async with self.semaphore:
            if source_type == SourceType.SEARXNG and self.searxng:
                return (source_type, query, language,
                        await self.searxng.search(query, language=language))
            elif source_type == SourceType.GDELT and self.gdelt:
                return (source_type, query, language,
                        await self.gdelt.search(query))
            elif source_type == SourceType.COMMON_CRAWL and self.common_crawl:
                return (source_type, query, language,
                        await self.common_crawl.search(query))
            elif source_type == SourceType.INTERNET_ARCHIVE and self.internet_archive:
                return (source_type, query, language,
                        await self.internet_archive.text_search(query))
            return (source_type, query, language, [])
