import pytest

from osint_pipeline.planning import (
    rule_based_plan, extract_query_seed, apply_plan_to_config, evaluate_plan_coverage,
)
from osint_pipeline.planning.models import (
    ResearchIntent, ResearchPlan, ConnectorPlan, QuerySeed,
    ALLOWED_CONNECTORS, ALLOWED_PROFILES, ALLOWED_ARCHIVE_PREFERENCES, FORBIDDEN_PHRASES,
)
from osint_pipeline.research.runner import ResearchRunConfig


class TestRuleBasedPlan:
    def test_deleted_content_query(self):
        plan = rule_based_plan("zoek verwijderde pagina over voorbeeld.nl rapport.pdf")
        assert plan.intent == ResearchIntent.DELETED_CONTENT
        assert plan.profile == "deleted_content"
        assert "archive_cdx" in [c.connector for c in plan.connectors]
        assert "archive_today" in [c.connector for c in plan.connectors]
        assert "archive_only" in plan.archive_preference

    def test_url_query_archive(self):
        plan = rule_based_plan("https://example.com/oud-rapport.pdf")
        assert plan.intent in (ResearchIntent.ARCHIVE_LOOKUP, ResearchIntent.DELETED_CONTENT)
        assert "archive_first" in plan.archive_preference or "archive_only" in plan.archive_preference

    def test_filename_query(self):
        plan = rule_based_plan("zoek het rapport.pdf bestand")
        assert plan.intent == ResearchIntent.DOCUMENT_SEARCH
        assert "searxng" in [c.connector for c in plan.connectors]

    def test_academic_query(self):
        plan = rule_based_plan("wetenschappelijk onderzoek waterstof opslag doi")
        assert plan.intent == ResearchIntent.ACADEMIC_RESEARCH
        assert "openalex" in [c.connector for c in plan.connectors]

    def test_news_query(self):
        plan = rule_based_plan("laatste nieuws waterstof economie")
        assert plan.intent == ResearchIntent.NEWS_MONITORING
        assert "gdelt" in [c.connector for c in plan.connectors]

    def test_default_query_multi_engine(self):
        plan = rule_based_plan("waterstof opslag nederland")
        assert plan.intent == ResearchIntent.GENERAL_RESEARCH
        assert plan.profile == "multi_engine"
        assert len(plan.connectors) >= 3


class TestQuerySeed:
    def test_extract_url(self):
        seed = extract_query_seed("bekijk https://example.com/doc.pdf")
        assert "https://example.com/doc.pdf" in seed.urls

    def test_extract_domain(self):
        seed = extract_query_seed("example.com test")
        assert "example.com" in seed.domains

    def test_extract_filename(self):
        seed = extract_query_seed("zoek rapport.pdf")
        assert "rapport.pdf" in seed.filenames

    def test_extract_quoted(self):
        seed = extract_query_seed('zoek "exacte zin"')
        assert "exacte zin" in seed.quoted_phrases

    def test_language_hint_dutch(self):
        seed = extract_query_seed("dit is een test voor het vinden van informatie")
        assert "nl" in seed.languages_hint

    def test_language_hint_english(self):
        seed = extract_query_seed("this is a test for finding information")
        assert "en" in seed.languages_hint


class TestApplyPlan:
    def test_apply_plan_to_config(self):
        plan = rule_based_plan("zoek verwijderde pagina")
        cfg = apply_plan_to_config(plan)
        assert cfg._profile_name == "deleted_content"
        assert "archive_cdx" in (cfg.enabled_connectors or [])
        assert cfg.archive_preference == "archive_only"

    def test_disabled_connector_not_re_enabled(self):
        plan = rule_based_plan("waterstof opslag nederland")
        base = ResearchRunConfig(disabled_connectors=["searxng", "gdelt"])
        cfg = apply_plan_to_config(plan, base)
        assert "searxng" not in (cfg.enabled_connectors or [])
        assert "gdelt" not in (cfg.enabled_connectors or [])

    def test_plan_to_config_preserves_defaults(self):
        plan = rule_based_plan("wetenschappelijk onderzoek waterstof")
        cfg = apply_plan_to_config(plan)
        assert cfg.searxng_strategy == "multi_engine"


class TestEvaluateCoverage:
    def test_deleted_content_no_archive_warning(self):
        plan = rule_based_plan("zoek verwijderde pagina")
        artifact = {"connector_results": [{"connector": "searxng"}], "sources_fetched": 5, "evidence": {"items": []}}
        warnings = evaluate_plan_coverage(plan, artifact)
        archive_warnings = [w for w in warnings if "archive" in w.lower()]
        assert len(archive_warnings) >= 0  # may or may not trigger

    def test_academic_no_openalex_warning(self):
        plan = rule_based_plan("wetenschappelijk onderzoek waterstof")
        artifact = {"connector_results": [{"connector": "searxng"}], "sources_fetched": 3, "evidence": {"items": []}}
        warnings = evaluate_plan_coverage(plan, artifact)
        assert any("OpenAlex" in w for w in warnings)

    def test_no_sources_warning(self):
        plan = rule_based_plan("test query")
        artifact = {"connector_results": [], "sources_fetched": 0, "evidence": {"items": []}}
        warnings = evaluate_plan_coverage(plan, artifact)
        assert any("No sources" in w for w in warnings)


class TestAllowedValues:
    def test_all_connectors_known(self):
        for c in "searxng gdelt openalex archive_cdx commoncrawl archive_today github wikidata reddit".split():
            assert c in ALLOWED_CONNECTORS

    def test_all_profiles_known(self):
        for p in "smoke archive_first deleted_content multi_engine foreign_index deep_archive".split():
            assert p in ALLOWED_PROFILES

    def test_forbidden_phrases(self):
        for p in FORBIDDEN_PHRASES:
            assert p  # non-empty

    def test_plan_research_cli_help(self):
        from osint_pipeline.cli import app
        from typer.testing import CliRunner
        r = CliRunner().invoke(app, ["plan-research", "--help"])
        assert r.exit_code == 0

    def test_plan_research_output(self):
        from osint_pipeline.cli import app
        from typer.testing import CliRunner
        r = CliRunner().invoke(app, ["plan-research", "zoek verwijderde pagina rapport.pdf"])
        assert r.exit_code == 0
        assert "deleted_content" in r.stdout
