from __future__ import annotations
import asyncio
from typing import Dict, List, Set
from ..models.source import SourceResult, SourceType, FetchStatus
from ..sources import InternetArchiveClient, CommonCrawlClient


class ArchiveLookup:
    def __init__(
        self,
        internet_archive: InternetArchiveClient,
        common_crawl: CommonCrawlClient,
    ) -> None:
        self.ia = internet_archive
        self.cc = common_crawl
        self.semaphore = asyncio.Semaphore(5)

    async def lookup_urls(
        self, urls: Set[str],
    ) -> Dict[str, List[SourceResult]]:
        tasks = []
        for url in urls:
            tasks.append(self._lookup_single(url))

        results: Dict[str, List[SourceResult]] = {}
        batches = [tasks[i:i + 5] for i in range(0, len(tasks), 5)]
        for batch in batches:
            for url, snapshots in await asyncio.gather(*batch, return_exceptions=True):
                if isinstance(snapshots, Exception):
                    continue
                results[url] = snapshots

        return results

    async def check_alive(self, urls: Set[str]) -> Dict[str, bool]:
        import aiohttp
        status: Dict[str, bool] = {}
        async with aiohttp.ClientSession() as session:
            for url in urls:
                async with self.semaphore:
                    try:
                        async with session.head(
                            url, timeout=aiohttp.ClientTimeout(total=10), allow_redirects=True,
                        ) as resp:
                            status[url] = resp.status < 400
                    except Exception:
                        status[url] = False
        return status

    async def _lookup_single(self, url: str):
        async with self.semaphore:
            # Try IA CDX
            ia_results = await self.ia.cdx_search(url)
            if not ia_results:
                ia_results = await self.ia.cdx_search(url.strip("/") + "/*")

            # Try Common Crawl
            cc_results = await self.cc.search(url)
            return url, ia_results + cc_results

    async def mark_archive_only(
        self, sources: List[SourceResult],
    ) -> List[SourceResult]:
        urls_to_check = set()
        for s in sources:
            if s.source_metadata.fetch_status == FetchStatus.NOT_FOUND:
                urls_to_check.add(s.source_metadata.url)

        if not urls_to_check:
            return sources

        alive_status = await self.check_alive(urls_to_check)
        archives = await self.lookup_urls(urls_to_check)

        for s in sources:
            url = s.source_metadata.url
            if url in urls_to_check:
                is_alive = alive_status.get(url, False)
                has_archive = url in archives and bool(archives[url])

                if not is_alive and has_archive:
                    s.source_metadata.fetch_status = FetchStatus.ARCHIVE_ONLY
                    s.is_archive_only = True
                    s.is_disappeared = True
                    if archives[url]:
                        s.archive_url = archives[url][0].archive_url
                elif not is_alive and not has_archive:
                    s.is_disappeared = True

        return sources
