from datetime import datetime, timezone

from osint_pipeline.models.source import (
    SourceMetadata,
    SourceResult,
    SourceType,
    FetchStatus,
)


class TestSourceMetadata:
    def test_source_metadata_minimal(self):
        sm = SourceMetadata(
            url="https://example.com/page",
            source_type=SourceType.SEARXNG,
            discovered_by_query="test query",
        )
        assert sm.url == "https://example.com/page"
        assert sm.source_type == SourceType.SEARXNG
        assert sm.language == "unknown"
        assert sm.discovered_by_query == "test query"
        assert sm.fetch_status == FetchStatus.PENDING

    def test_source_metadata_full(self):
        now = datetime.now(timezone.utc).isoformat()
        sm = SourceMetadata(
            url="https://example.com/doc.pdf",
            source_type=SourceType.GDELT,
            language="en",
            discovered_by_query="test query",
            discovered_at=now,
            snapshot_date="2024-06-01T00:00:00",
            title="Test Document",
            domain="example.com",
            status_code=200,
            fetch_status=FetchStatus.SUCCESS,
            archive_url="https://web.archive.org/web/20240601/https://example.com/doc.pdf",
        )
        assert sm.title == "Test Document"
        assert sm.status_code == 200
        assert sm.archive_url is not None

    def test_source_result_with_content(self):
        sm = SourceMetadata(
            url="https://example.com",
            source_type=SourceType.SEARXNG,
            discovered_by_query="test",
        )
        sr = SourceResult(
            metadata=sm,
            content="Sample page content for testing",
        )
        assert sr.content == "Sample page content for testing"
        assert sr.error is None

    def test_source_result_with_error(self):
        sm = SourceMetadata(
            url="https://example.com",
            source_type=SourceType.GDELT,
            discovered_by_query="test",
        )
        sr = SourceResult(metadata=sm, error="HTTP 500")
        assert sr.error == "HTTP 500"

    def test_all_source_types_have_values(self):
        assert SourceType.SEARXNG.value == "searxng"
        assert SourceType.GDELT.value == "gdelt"
        assert SourceType.COMMON_CRAWL.value == "common_crawl"
        assert SourceType.INTERNET_ARCHIVE.value == "internet_archive"
        assert SourceType.WAYBACK.value == "wayback"
        assert SourceType.CRAWL4AI.value == "crawl4ai"
        assert SourceType.OPENALEX.value == "openalex"
        assert SourceType.GITHUB.value == "github"
        assert SourceType.WIKIDATA.value == "wikidata"
        assert SourceType.REDDIT.value == "reddit"
        assert SourceType.WAYMORE.value == "waymore"

    def test_all_fetch_statuses(self):
        assert FetchStatus.PENDING.value == "pending"
        assert FetchStatus.SUCCESS.value == "success"
        assert FetchStatus.NOT_FOUND.value == "not_found"
        assert FetchStatus.ERROR.value == "error"
        assert FetchStatus.ARCHIVE_ONLY.value == "archive_only"

    def test_source_metadata_serialization(self):
        sm = SourceMetadata(
            url="https://example.com",
            source_type=SourceType.SEARXNG,
            discovered_by_query="q",
        )
        d = sm.model_dump()
        assert d["url"] == "https://example.com"
        assert d["source_type"] == "searxng"
        assert d["fetch_status"] == "pending"

    def test_source_metadata_has_lineage_fields(self):
        sm = SourceMetadata(
            url="https://x.com",
            source_type=SourceType.SEARXNG,
            discovered_by_query="q",
            run_id="r1",
            query_lineage_id="l1",
        )
        assert sm.run_id == "r1"
        assert sm.query_lineage_id == "l1"
