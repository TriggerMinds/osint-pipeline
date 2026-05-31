import json as json_mod
from datetime import datetime, timezone

import pytest
import respx

from osint_pipeline.connectors import (
    SearXNGConnector,
    GDELTConnector,
    ArchiveCDXConnector,
    CommonCrawlConnector,
)
from osint_pipeline.connectors.base import BaseConnector, ConnectorResult
from osint_pipeline.models.source import SourceType, FetchStatus


# ── SearXNG ───────────────────────────────────────────────────────────


class TestSearXNGConnector:
    @pytest.fixture
    def connector(self):
        return SearXNGConnector()

    @pytest.mark.asyncio
    async def test_search_returns_results(self, connector):
        with respx.mock:
            route = respx.get("http://localhost:8888/search").respond(
                status_code=200,
                json={
                    "results": [
                        {
                            "url": "https://example.com/page1",
                            "title": "Page 1",
                            "content": "Content of page 1",
                            "language": "en",
                        },
                        {
                            "url": "https://example.com/page2",
                            "title": "Page 2",
                            "content": "Content of page 2",
                            "language": "nl",
                        },
                    ]
                },
            )

            result = await connector.search("test query")

            assert route.called
            assert len(result.sources) == 2
            assert result.sources[0].metadata.url == "https://example.com/page1"
            assert result.sources[0].metadata.title == "Page 1"
            assert result.sources[0].metadata.source_type == SourceType.SEARXNG
            assert result.sources[0].metadata.fetch_status == FetchStatus.SUCCESS
            assert result.sources[0].content == "Content of page 1"
            assert result.sources[0].metadata.language == "en"
            assert result.sources[1].metadata.language == "nl"
            assert result.sources[0].metadata.discovered_by_query == "test query"
            assert result.error is None

    @pytest.mark.asyncio
    async def test_search_non_200_returns_error_when_exhausted(self, connector):
        with respx.mock:
            route = respx.get("http://localhost:8888/search").respond(status_code=503)
            result = await connector.search("query")
            assert route.called
            assert result.error is not None

    @pytest.mark.asyncio
    async def test_search_network_error_returns_error(self, connector):
        with respx.mock:
            route = respx.get("http://localhost:8888/search").mock(
                side_effect=Exception("Connection refused")
            )
            result = await connector.search("query")
            assert route.called
            assert result.error is not None or len(result.sources) == 0

    @pytest.mark.asyncio
    async def test_health_success(self, connector):
        with respx.mock:
            respx.get("http://localhost:8888/search").respond(
                status_code=200, json={"results": []}
            )
            assert await connector.health() is True

    @pytest.mark.asyncio
    async def test_health_failure(self, connector):
        with respx.mock:
            respx.get("http://localhost:8888/search").respond(status_code=500)
            assert await connector.health() is False

    @pytest.mark.asyncio
    async def test_search_sends_typed_params(self, connector):
        with respx.mock:
            route = respx.get("http://localhost:8888/search").respond(
                status_code=200, json={"results": []}
            )
            await connector.search("query", language="nl", time_range="month")
            assert route.called
            request = route.calls[0].request
            assert request.url.params["q"] == "query"
            assert request.url.params["language"] == "nl"
            assert request.url.params["time_range"] == "month"


# ── GDELT ─────────────────────────────────────────────────────────────


class TestGDELTConnector:
    @pytest.fixture
    def connector(self):
        return GDELTConnector()

    @pytest.mark.asyncio
    async def test_search_returns_results(self, connector):
        with respx.mock:
            route = respx.get(
                "https://api.gdeltproject.org/api/v2/doc/doc"
            ).respond(
                status_code=200,
                json={
                    "articles": [
                        {
                            "url": "https://news.example.com/story1",
                            "title": "Story 1",
                            "summary": "Summary of story 1",
                            "language": "en",
                            "domain": "news.example.com",
                            "seendate": "2024-06-01",
                        },
                    ]
                },
            )

            result = await connector.search("test query")

            assert route.called
            assert len(result.sources) == 1
            s = result.sources[0]
            assert s.metadata.url == "https://news.example.com/story1"
            assert s.metadata.title == "Story 1"
            assert s.metadata.source_type == SourceType.GDELT
            assert s.metadata.fetch_status == FetchStatus.SUCCESS
            assert s.metadata.language == "en"
            assert s.metadata.domain == "news.example.com"
            assert s.metadata.discovered_by_query == "test query"
            assert s.content == "Summary of story 1"
            assert result.error is None

    @pytest.mark.asyncio
    async def test_search_sends_typed_params(self, connector):
        with respx.mock:
            route = respx.get(
                "https://api.gdeltproject.org/api/v2/doc/doc"
            ).respond(status_code=200, json={"articles": []})

            await connector.search(
                "query", language="fr", timespan="30d", max_records=100
            )
            assert route.called
            params = route.calls[0].request.url.params
            assert params["query"] == "query"
            assert params["language"] == "fr"
            assert params["timespan"] == "30d"
            assert params["maxrecords"] == "100"


# ── Archive CDX ───────────────────────────────────────────────────────


class TestArchiveCDXConnector:
    @pytest.fixture
    def connector(self):
        return ArchiveCDXConnector()

    @pytest.mark.asyncio
    async def test_search_returns_snapshots(self, connector):
        mock_cdx = [
            ["original", "timestamp", "statuscode", "digest"],
            ["https://example.com/doc", "20240101120000", "200", "abc123"],
            ["https://example.com/doc", "20230101120000", "301", "def456"],
        ]

        with respx.mock:
            route = respx.get(
                "https://web.archive.org/cdx/search/cdx"
            ).respond(status_code=200, json=mock_cdx)

            result = await connector.search("https://example.com/doc")

            assert route.called
            assert len(result.sources) == 2
            s0 = result.sources[0]
            assert s0.metadata.url == "https://example.com/doc"
            assert s0.metadata.source_type == SourceType.INTERNET_ARCHIVE
            assert s0.metadata.status_code == 200
            assert s0.metadata.fetch_status == FetchStatus.SUCCESS
            assert s0.metadata.snapshot_date is not None
            assert "web.archive.org" in (s0.metadata.archive_url or "")

    @pytest.mark.asyncio
    async def test_search_with_from_to(self, connector):
        with respx.mock:
            route = respx.get(
                "https://web.archive.org/cdx/search/cdx"
            ).respond(status_code=200, json=[["original"], []])

            await connector.search("https://example.com", from_date="2024", to_date="2025")
            assert route.called
            params = route.calls[0].request.url.params
            assert params["from"] == "2024"
            assert params["to"] == "2025"

    @pytest.mark.asyncio
    async def test_search_sends_filter_and_collapse(self, connector):
        with respx.mock:
            route = respx.get(
                "https://web.archive.org/cdx/search/cdx"
            ).respond(status_code=200, json=[["original"], []])

            await connector.search("https://example.com")
            assert route.called
            params = route.calls[0].request.url.params
            assert params["filter"] is not None
            assert "statuscode:200" in params["filter"]
            assert params["collapse"] == "urlkey"


# ── Common Crawl ──────────────────────────────────────────────────────


class TestCommonCrawlConnector:
    @pytest.fixture
    def connector(self):
        return CommonCrawlConnector()

    @pytest.mark.asyncio
    async def test_fetch_indexes(self, connector):
        mock_indexes = [
            {"id": "CC-MAIN-2024-10", "name": "2024 Weekly 10", "created": "2024-03-15"},
            {"id": "CC-MAIN-2024-05", "name": "2024 Weekly 5", "created": "2024-02-01"},
        ]

        with respx.mock:
            respx.get(
                f"{connector.settings.commoncrawl_base_url}/collinfo.json"
            ).respond(status_code=200, json=mock_indexes)

            indexes = await connector._fetch_indexes()
            assert len(indexes) == 2
            assert indexes[0].id == "CC-MAIN-2024-10"
            assert indexes[1].name == "2024 Weekly 5"

    @pytest.mark.asyncio
    async def test_search_returns_results(self, connector):
        mock_indexes = [
            {"id": "CC-MAIN-2024-10", "name": "Index 1", "created": "2024-01-01"},
        ]
        mock_pages = "\n".join([
            json_mod.dumps({"url": "https://example.com/p1", "timestamp": "20240101120000", "status": "200"}),
            json_mod.dumps({"url": "https://example.com/p2", "timestamp": "20240102120000", "status": "301"}),
        ])

        with respx.mock:
            respx.get(
                f"{connector.settings.commoncrawl_base_url}/collinfo.json"
            ).respond(status_code=200, json=mock_indexes)

            route = respx.get(
                f"{connector.settings.commoncrawl_base_url}/CC-MAIN-2024-10-cdx"
            ).respond(status_code=200, text=mock_pages)

            result = await connector.search("https://example.com/*")

            assert route.called
            assert len(result.sources) == 2
            s0 = result.sources[0]
            assert s0.metadata.url == "https://example.com/p1"
            assert s0.metadata.source_type == SourceType.COMMON_CRAWL
            assert s0.metadata.status_code == 200
            assert s0.metadata.fetch_status == FetchStatus.SUCCESS
            assert s0.metadata.snapshot_date is not None

    @pytest.mark.asyncio
    async def test_no_indexes_returns_error(self, connector):
        with respx.mock:
            respx.get(
                f"{connector.settings.commoncrawl_base_url}/collinfo.json"
            ).respond(status_code=404)

            result = await connector.search("https://example.com")
            assert result.error is not None
            assert "No Common Crawl indexes" in result.error

    @pytest.mark.asyncio
    async def test_health_ok(self, connector):
        with respx.mock:
            respx.get(
                f"{connector.settings.commoncrawl_base_url}/collinfo.json"
            ).respond(
                status_code=200,
                json=[{"id": "CC-MAIN-2024-10", "name": "idx", "created": "2024-01-01"}],
            )
            assert await connector.health() is True

    @pytest.mark.asyncio
    async def test_health_no_indexes(self, connector):
        with respx.mock:
            respx.get(
                f"{connector.settings.commoncrawl_base_url}/collinfo.json"
            ).respond(status_code=200, json=[])
            assert await connector.health() is False


# ── SourceMetadata completeness check ─────────────────────────────────


class TestSourceMetadataFilling:
    """Verify all SourceMetadata fields are populated by every connector."""

    @pytest.mark.asyncio
    async def test_searxng_metadata_fields(self):
        with respx.mock:
            respx.get("http://localhost:8888/search").respond(
                status_code=200,
                json={
                    "results": [
                        {
                            "url": "https://example.com/page",
                            "title": "A Page",
                            "content": "content",
                            "language": "en",
                        }
                    ]
                },
            )
            c = SearXNGConnector()
            result = await c.search("q")
            m = result.sources[0].metadata
            assert m.url == "https://example.com/page"
            assert m.source_type == SourceType.SEARXNG
            assert m.language == "en"
            assert m.discovered_by_query == "q"
            assert m.discovered_at != ""
            assert m.title == "A Page"
            assert m.fetch_status == FetchStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_gdelt_metadata_fields(self):
        with respx.mock:
            respx.get(
                "https://api.gdeltproject.org/api/v2/doc/doc"
            ).respond(
                status_code=200,
                json={
                    "articles": [
                        {
                            "url": "https://news.com/a",
                            "title": "Article",
                            "summary": "text",
                            "language": "fr",
                            "domain": "news.com",
                        }
                    ]
                },
            )
            c = GDELTConnector()
            result = await c.search("q")
            m = result.sources[0].metadata
            assert m.url == "https://news.com/a"
            assert m.source_type == SourceType.GDELT
            assert m.language == "fr"
            assert m.title == "Article"
            assert m.domain == "news.com"
            assert m.fetch_status == FetchStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_archive_cdx_metadata_fields(self):
        mock = [
            ["original", "timestamp", "statuscode", "digest"],
            ["https://archive.org/doc", "20240101120000", "200", "abc"],
        ]
        with respx.mock:
            respx.get("https://web.archive.org/cdx/search/cdx").respond(
                status_code=200, json=mock
            )
            c = ArchiveCDXConnector()
            result = await c.search("https://archive.org/doc")
            m = result.sources[0].metadata
            assert m.url == "https://archive.org/doc"
            assert m.source_type == SourceType.INTERNET_ARCHIVE
            assert m.status_code == 200
            assert m.snapshot_date is not None
            assert m.archive_url is not None
            assert m.fetch_status == FetchStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_commoncrawl_metadata_fields(self):
        with respx.mock:
            respx.get(
                "https://index.commoncrawl.org/collinfo.json"
            ).respond(
                status_code=200,
                json=[{"id": "CC-MAIN-2024-10", "name": "idx", "created": "2024-01-01"}],
            )
            respx.get(
                "https://index.commoncrawl.org/CC-MAIN-2024-10-cdx"
            ).respond(
                status_code=200,
                text=json_mod.dumps({
                    "url": "https://cc.example.com/p",
                    "timestamp": "20240101120000",
                    "status": "200",
                }),
            )
            c = CommonCrawlConnector()
            result = await c.search("https://cc.example.com/*")
            m = result.sources[0].metadata
            assert m.url == "https://cc.example.com/p"
            assert m.source_type == SourceType.COMMON_CRAWL
            assert m.status_code == 200
            assert m.snapshot_date is not None
            assert m.fetch_status == FetchStatus.SUCCESS


# ── Retry logic tests ─────────────────────────────────────────────────


class _RetryTestConnector(BaseConnector):
    """Minimal connector subclass to test _request_with_retry in isolation."""

    async def search(self, query: str, **kwargs) -> ConnectorResult:
        import httpx as _httpx
        from osint_pipeline.connectors.base import _compact_error
        from osint_pipeline.connectors.errors import ConnectorError
        async with _httpx.AsyncClient(timeout=5) as client:
            try:
                await self._request_with_retry(
                    client, "GET", "http://test.local/endpoint",
                )
                return ConnectorResult(sources=[])
            except ConnectorError as exc:
                return ConnectorResult(
                    sources=[], error=_compact_error(exc)
                )

    async def health(self) -> bool:
        return True


class TestRetryLogic:
    @pytest.mark.asyncio
    async def test_429_then_200_succeeds(self):
        with respx.mock:
            route_429 = respx.get("http://test.local/endpoint").respond(status_code=429)
            route_200 = respx.get("http://test.local/endpoint").respond(status_code=200, json={})
            conn = _RetryTestConnector()
            result = await conn.search("q")
            # Should eventually succeed
            assert result.error is None

    @pytest.mark.asyncio
    async def test_503_then_200_succeeds(self):
        with respx.mock:
            respx.get("http://test.local/endpoint").respond(status_code=503)
            respx.get("http://test.local/endpoint").respond(status_code=200, json={})
            conn = _RetryTestConnector()
            result = await conn.search("q")
            assert result.error is None

    @pytest.mark.asyncio
    async def test_404_does_not_retry(self):
        with respx.mock:
            route = respx.get("http://test.local/endpoint").respond(status_code=404)
            conn = _RetryTestConnector()
            try:
                await conn.search("q")
            except Exception:
                pass
            # Should only have been called once
            assert route.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_after_header_is_used(self):
        with respx.mock:
            route = respx.get("http://test.local/endpoint").respond(status_code=429, headers={"Retry-After": "2"})
            respx.get("http://test.local/endpoint").respond(status_code=200, json={})
            conn = _RetryTestConnector()
            result = await conn.search("q")
            assert result.error is None

    @pytest.mark.asyncio
    async def test_exhausted_retries_returns_controlled_error(self):
        with respx.mock:
            route = respx.get("http://test.local/endpoint").respond(status_code=503)
            conn = _RetryTestConnector()
            result = await conn.search("q")
            assert result.error is not None
            assert "ConnectorRetriesExhaustedError" in result.error

    @pytest.mark.asyncio
    async def test_400_does_not_retry(self):
        with respx.mock:
            route = respx.get("http://test.local/endpoint").respond(status_code=400)
            conn = _RetryTestConnector()
            await conn.search("q")
            assert route.call_count == 1

    @pytest.mark.asyncio
    async def test_403_does_not_retry(self):
        with respx.mock:
            route = respx.get("http://test.local/endpoint").respond(status_code=403)
            conn = _RetryTestConnector()
            await conn.search("q")
            assert route.call_count == 1

    @pytest.mark.asyncio
    async def test_410_does_not_retry(self):
        with respx.mock:
            route = respx.get("http://test.local/endpoint").respond(status_code=410)
            conn = _RetryTestConnector()
            await conn.search("q")
            assert route.call_count == 1

    @pytest.mark.asyncio
    async def test_compact_error_format_typed(self):
        from osint_pipeline.connectors.errors import ConnectorRetriesExhaustedError, ConnectorTimeoutError, ConnectorHTTPStatusError
        from osint_pipeline.connectors.base import _compact_error
        e1 = ConnectorRetriesExhaustedError(503, "http://x", 3)
        assert _compact_error(e1) == "ConnectorRetriesExhaustedError: HTTP 503 after 4 attempt(s)"
        e2 = ConnectorTimeoutError()
        assert _compact_error(e2) == "ConnectorTimeoutError: request timed out"
        e3 = ConnectorHTTPStatusError(404, "http://x")
        assert _compact_error(e3) == "ConnectorHTTPStatusError: HTTP 404"
