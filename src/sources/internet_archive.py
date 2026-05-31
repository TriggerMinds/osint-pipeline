from __future__ import annotations
import aiohttp
from datetime import datetime
from typing import Any, Dict, List, Optional
from ..models.source import SourceResult, SourceMetadata, SourceType, FetchStatus


class InternetArchiveClient:
    CDX_URL = "https://web.archive.org/cdx/search/cdx"
    WAYBACK_URL = "https://web.archive.org/web"

    def __init__(self, max_snapshots: int = 20, timeout: int = 60) -> None:
        self.max_snapshots = max_snapshots
        self.timeout = timeout

    async def cdx_search(
        self, url_pattern: str, from_date: str = "", to_date: str = "",
    ) -> List[SourceResult]:
        params: Dict[str, Any] = {
            "url": url_pattern,
            "output": "json",
            "limit": self.max_snapshots,
            "fl": "original,timestamp,endtimestamp,statuscode,digest,length",
        }
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    self.CDX_URL,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
            except Exception:
                return []

        if not data or len(data) < 2:
            return []

        headers = data[0]
        results = []
        for row in data[1:]:
            row_map = dict(zip(headers, row))
            url = row_map.get("original", "")
            timestamp = row_map.get("timestamp", "")
            snapshot_date = self._format_timestamp(timestamp)

            wayback_url = f"{self.WAYBACK_URL}/{timestamp}/{url}" if timestamp else ""

            metadata = SourceMetadata(
                url=url,
                timestamp=timestamp,
                snapshot_date=snapshot_date,
                language="unknown",
                source_type=SourceType.INTERNET_ARCHIVE,
                query_used=url_pattern,
                status_code=int(row_map.get("statuscode", 0)) if row_map.get("statuscode") else None,
                fetch_status=FetchStatus.SUCCESS,
            )
            results.append(SourceResult(
                source_metadata=metadata,
                archive_url=wayback_url,
                is_archive_snapshot=True,
                raw_response=row_map,
            ))

        return results

    async def text_search(
        self, query: str, limit: int = 20,
    ) -> List[SourceResult]:
        params: Dict[str, Any] = {
            "q": query,
            "output": "json",
            "limit": limit,
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    "https://web.archive.org/web/tex/search",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
            except Exception:
                return []

        results = []
        for item in data.get("results", data.get("response", {}).get("docs", data if isinstance(data, list) else [])):
            if isinstance(item, str):
                continue
            url = item.get("url", item.get("original_url", ""))
            metadata = SourceMetadata(
                url=url,
                timestamp=item.get("timestamp", item.get("captured_at", "")),
                snapshot_date=item.get("date", ""),
                language=item.get("language", "unknown"),
                source_type=SourceType.WAYBACK,
                query_used=query,
                title=item.get("title", ""),
                fetch_status=FetchStatus.SUCCESS,
            )
            results.append(SourceResult(
                source_metadata=metadata,
                archive_url=f"{self.WAYBACK_URL}/{item.get('timestamp', '')}/{url}",
                is_archive_snapshot=True,
                raw_response=item,
            ))

        return results

    def _format_timestamp(self, ts: str) -> str:
        try:
            return datetime.strptime(ts[:14], "%Y%m%d%H%M%S").isoformat()
        except (ValueError, IndexError):
            return ts
