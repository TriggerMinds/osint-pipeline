from osint_pipeline.research.strategies import (
    build_discovery_strategy, build_deleted_content_queries,
    SEARXNG_STRATEGIES, PROFILE_SEARXNG,
)
from osint_pipeline.models.dork import DorkTarget
from osint_pipeline.router import SourceRouter, TARGET_CONNECTOR_MAP
from osint_pipeline.research.executor import ConnectorTask


class TestSearXNGEnginesInProfiles:
    def test_multi_engine_has_engines(self):
        cfg = PROFILE_SEARXNG.get("multi_engine", {})
        assert cfg["strategy"] == "multi_engine"
        assert len(cfg["engines"]) > 0

    def test_foreign_index_has_engines(self):
        cfg = PROFILE_SEARXNG.get("foreign_index", {})
        assert len(cfg["engines"]) > 0

    def test_deleted_content_has_engines(self):
        cfg = PROFILE_SEARXNG.get("deleted_content", {})
        assert len(cfg["engines"]) > 0

    def test_smoke_engines_empty(self):
        cfg = PROFILE_SEARXNG.get("smoke", {})
        assert cfg["engines"] == ()

    def test_searxng_strategies_defined(self):
        for name in ("default", "file_discovery", "multi_engine", "regional_diverse"):
            assert name in SEARXNG_STRATEGIES


class TestConnectorTaskEngines:
    def test_task_has_engines_field(self):
        task = ConnectorTask(connector="searxng", query="q", lineage_id="l1", engines=("brave", "mojeek"))
        assert task.engines == ("brave", "mojeek")

    def test_task_engines_default_empty(self):
        task = ConnectorTask(connector="gdelt", query="q", lineage_id="l1")
        assert task.engines == ()


class TestDiscoveryStrategy:
    def test_multi_engine_strategy_has_engines_requested(self):
        s = build_discovery_strategy(
            "multi_engine", searxng_strategy="multi_engine",
            searxng_engines=("brave", "mojeek", "yandex", "bing", "duckduckgo"),
            connectors_used=["searxng", "gdelt"],
        )
        assert len(s["engines_requested"]) > 0
        assert s["searxng_strategy"] == "multi_engine"

    def test_connectors_used_separate_from_engines(self):
        s = build_discovery_strategy(
            "multi_engine", searxng_strategy="multi_engine",
            searxng_engines=("brave", "mojeek"),
            connectors_used=["searxng", "gdelt", "openalex"],
        )
        assert "searxng" in s["connectors_used"]
        assert "gdelt" in s["connectors_used"]
        assert s["engines_used"] == []  # not populated from connectors
        assert s["engines_requested"] == ["brave", "mojeek"]

    def test_engines_used_empty_by_default(self):
        s = build_discovery_strategy("archive_first", searxng_strategy="file_discovery")
        assert s["engines_used"] == []

    def test_deleted_content_has_archive_sources(self):
        s = build_discovery_strategy("deleted_content")
        assert s["deleted_content_query"] is True
        assert len(s["archive_sources"]) > 0

    def test_archive_first_has_archive_sources(self):
        s = build_discovery_strategy("archive_first")
        assert len(s["archive_sources"]) > 0


class TestDeletedContentQueries:
    def test_injects_archive_suffixes(self):
        queries = build_deleted_content_queries("test query")
        assert len(queries) > 0
        assert any("site:archive.org" in q for q in queries)
        assert any("site:archive.ph" in q for q in queries)
        assert any("cache:" in q for q in queries)

    def test_respects_query(self):
        queries = build_deleted_content_queries("hydrogen storage")
        assert all("hydrogen" in q for q in queries)


class TestDorkTargetArchiveToday:
    def test_enum_exists(self):
        assert hasattr(DorkTarget, "ARCHIVE_TODAY")
        assert DorkTarget.ARCHIVE_TODAY.value == "archive_today"

    def test_router_maps_archive_today(self):
        assert DorkTarget.ARCHIVE_TODAY in TARGET_CONNECTOR_MAP
        assert TARGET_CONNECTOR_MAP[DorkTarget.ARCHIVE_TODAY] == "archive_today"

    def test_router_roundtrip(self):
        from osint_pipeline.models.dork import DorkQuery
        router = SourceRouter()
        dork = DorkQuery(raw="https://example.com", target=DorkTarget.ARCHIVE_TODAY)
        route = router.route(dork)
        assert route.connector == "archive_today"
        assert route.execution_mode == "archive_lookup"


class TestSourceMetadataArchiveProvider:
    def test_archive_provider_field_exists(self):
        from osint_pipeline.models.source import SourceMetadata, SourceType
        sm = SourceMetadata(
            url="https://example.com",
            source_type=SourceType.ARCHIVE_TODAY,
            discovered_by_query="q",
            archive_url="https://archive.ph/abc123",
            archive_provider="archive_today",
        )
        assert sm.archive_provider == "archive_today"

    def test_archive_provider_optional(self):
        from osint_pipeline.models.source import SourceMetadata, SourceType
        sm = SourceMetadata(
            url="https://example.com",
            source_type=SourceType.SEARXNG,
            discovered_by_query="q",
        )
        assert sm.archive_provider is None


class TestNoForbiddenPhrases:
    FORBIDDEN = ["zero-attribution", "100% anonymous", "no DNS leaks guaranteed", "uncensored"]

    def test_no_forbidden_in_strategies(self):
        import osint_pipeline.research.strategies as s
        import inspect
        src = inspect.getsource(s)
        for phrase in self.FORBIDDEN:
            assert phrase not in src.lower()

    def test_no_forbidden_in_cli(self):
        import osint_pipeline.cli as cli
        import inspect
        src = inspect.getsource(cli)
        for phrase in self.FORBIDDEN:
            assert phrase not in src.lower()

    def test_no_forbidden_in_router(self):
        import osint_pipeline.router as r
        import inspect
        src = inspect.getsource(r)
        for phrase in self.FORBIDDEN:
            assert phrase not in src.lower()

    def test_no_forbidden_in_executor(self):
        import osint_pipeline.research.executor as e
        import inspect
        src = inspect.getsource(e)
        for phrase in self.FORBIDDEN:
            assert phrase not in src.lower()

    def test_no_forbidden_in_runner(self):
        import osint_pipeline.research.runner as r
        import inspect
        src = inspect.getsource(r)
        for phrase in self.FORBIDDEN:
            assert phrase not in src.lower()
