from __future__ import annotations
import aiohttp
from typing import Any, Dict, List, Optional
from ..models.source import SourceResult, SourceMetadata, SourceType, FetchStatus


class SearXNGSearcher:
    def __init__(self, instances: List[str], max_results: int = 20, timeout: int = 30) -> None:
        self.instances = instances
        self.max_results = max_results
        self.timeout = timeout

    async def search(self, query: str, language: str = "en", categories: Optional[List[str]] = None) -> List[SourceResult]:
        results = []
        for instance in self.instances:
            try:
                batch = await self._search_instance(instance, query, language, categories)
                results.extend(batch)
                if len(results) >= self.max_results:
                    break
            except Exception:
                continue
        return results[:self.max_results]

    async def _search_instance(
        self, instance: str, query: str, language: str, categories: Optional[List[str]] = None
    ) -> List[SourceResult]:
        params: Dict[str, Any] = {
            "q": query,
            "format": "json",
            "language": language,
            "limit": self.max_results,
        }
        if categories:
            params["categories"] = ",".join(categories)

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{instance}/search",
                params=params,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()

        results = []
        for item in data.get("results", []):
            metadata = SourceMetadata(
                url=item.get("url", ""),
                timestamp=item.get("publishedDate", "") or "",
                language=item.get("language", language),
                source_type=SourceType.SEARXNG,
                query_used=query,
                title=item.get("title", ""),
                domain=item.get("parsed_url", {}).get("netloc", ""),
                fetch_status=FetchStatus.SUCCESS,
            )
            results.append(SourceResult(
                source_metadata=metadata,
                content_text=item.get("content", ""),
                raw_response=item,
            ))

        return results
