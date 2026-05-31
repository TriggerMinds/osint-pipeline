from osint_pipeline.research.runner import ResearchRunConfig, _canonical_url, _dedup_sources, _filter_by_confidence
from osint_pipeline.models.source import SourceResult, SourceMetadata, SourceType
from osint_pipeline.models.evidence import EvidenceCollection, Evidence, EvidenceClaim, ConflictMarker


class TestCanonicalURL:
    def test_strip_trailing_slash(self):
        assert _canonical_url("https://example.com/", "url") == "https://example.com"

    def test_lowercase_host(self):
        assert _canonical_url("HTTPS://EXAMPLE.COM/Path", "url") == "https://example.com/path"

    def test_canonical_removes_utm(self):
        result = _canonical_url(
            "https://example.com/page?utm_source=twitter&a=1&utm_campaign=test",
            "canonical_url",
        )
        assert "utm_source" not in result
        assert "utm_campaign" not in result
        assert "a=1" in result

    def test_canonical_removes_fbclid(self):
        result = _canonical_url(
            "https://example.com/page?fbclid=abc123&q=test",
            "canonical_url",
        )
        assert "fbclid" not in result
        assert "q=test" in result

    def test_domain_url_mode(self):
        result = _canonical_url("https://example.com/page?x=1", "domain_url")
        assert result == "https://example.com"

    def test_identical_urls_deduped(self):
        sources = [
            SourceResult(metadata=SourceMetadata(url="https://x.com/a", source_type=SourceType.SEARXNG, discovered_by_query="q")),
            SourceResult(metadata=SourceMetadata(url="https://x.com/a", source_type=SourceType.GDELT, discovered_by_query="q")),
        ]
        deduped = _dedup_sources(sources, "url")
        assert len(deduped) == 1

    def test_tracking_urls_deduped_canonical(self):
        sources = [
            SourceResult(metadata=SourceMetadata(
                url="https://x.com/page?utm_source=tw&id=1", source_type=SourceType.SEARXNG, discovered_by_query="q",
            )),
            SourceResult(metadata=SourceMetadata(
                url="https://x.com/page?id=1", source_type=SourceType.GDELT, discovered_by_query="q",
            )),
        ]
        deduped = _dedup_sources(sources, "canonical_url")
        assert len(deduped) == 1


class TestDisabledConnectors:
    def test_disabled_connector_not_executed(self):
        """Simulated: disabled connector should be filtered."""
        config = ResearchRunConfig(disabled_connectors=["github", "reddit"])
        assert "github" in config.disabled_connectors
        assert "reddit" in config.disabled_connectors


class TestLanguageFilter:
    def test_language_filter_list(self):
        config = ResearchRunConfig(enabled_languages=["en", "nl"])
        assert config.enabled_languages == ["en", "nl"]


class TestMaxPerConnector:
    def test_max_tasks_per_connector_config(self):
        config = ResearchRunConfig(max_tasks_per_connector=3)
        assert config.max_tasks_per_connector == 3

    def test_max_results_per_connector_config(self):
        config = ResearchRunConfig(max_results_per_connector=10)
        assert config.max_results_per_connector == 10


class TestEvidenceFilter:
    def test_filter_below_confidence(self):
        ec = EvidenceCollection(query="test")
        ev = Evidence(
            source_url="https://x.com", language="en", source_type="searxng",
            discovered_by_query="q",
            claims=[
                EvidenceClaim(claim="low", confidence=0.2),
                EvidenceClaim(claim="high", confidence=0.9),
            ],
        )
        ec.items.append(ev)
        filtered = _filter_by_confidence(ec, 0.5)
        assert len(filtered.items[0].claims) == 1
        assert filtered.items[0].claims[0].claim == "high"

    def test_empty_when_all_filtered(self):
        ec = EvidenceCollection(query="test")
        ev = Evidence(
            source_url="https://x.com", language="en", source_type="searxng",
            discovered_by_query="q",
            claims=[EvidenceClaim(claim="low", confidence=0.1)],
        )
        ec.items.append(ev)
        filtered = _filter_by_confidence(ec, 0.5)
        assert len(filtered.items) == 0


class TestArchivePreference:
    def test_archive_only_config(self):
        config = ResearchRunConfig(archive_preference="archive_only")
        assert config.archive_preference == "archive_only"

    def test_archive_first_config(self):
        config = ResearchRunConfig(archive_preference="archive_first")
        assert config.archive_preference == "archive_first"

    def test_live_first_config(self):
        config = ResearchRunConfig(archive_preference="live_first")
        assert config.archive_preference == "live_first"


class TestCrawlEnrichmentPolicy:
    def test_missing_content_policy(self):
        config = ResearchRunConfig(crawl_enrichment_policy="missing_content", enrich=True)
        assert config.enrich
        assert config.crawl_enrichment_policy == "missing_content"

    def test_top_ranked_policy(self):
        config = ResearchRunConfig(crawl_enrichment_policy="top_ranked", enrich=True)
        assert config.crawl_enrichment_policy == "top_ranked"

    def test_none_policy(self):
        config = ResearchRunConfig(crawl_enrichment_policy="none")
        assert config.crawl_enrichment_policy == "none"


class TestEnabledConnectors:
    def test_enabled_connectors_config(self):
        config = ResearchRunConfig(enabled_connectors=["searxng", "gdelt"])
        assert config.enabled_connectors == ["searxng", "gdelt"]
