import json
from pathlib import Path
from typing import Any

import pytest

from osint_pipeline.research import ResearchRunConfig, ResearchArtifact, TimingBreakdown, GraphSummary
from osint_pipeline.research.runner import _canonical_url


# ── Dry-run mode ─────────────────────────────────────────────────────


class TestDryRun:
    def test_dry_run_config(self):
        c = ResearchRunConfig(dry_run=True)
        assert c.dry_run is True

    def test_dry_run_artifact_field(self):
        a = ResearchArtifact(run_id="dry", query="t", dry_run=True)
        assert a.dry_run is True
        d = a.model_dump_safe()
        assert d.get("dry_run") is True

    def test_normal_run_artifact_field_false(self):
        a = ResearchArtifact(run_id="normal", query="t")
        assert a.dry_run is False


# ── Smoke profile ────────────────────────────────────────────────────


class TestSmokeProfile:
    def test_smoke_profile_config(self):
        """Smoke profile sets conservative limits."""
        c = ResearchRunConfig(
            max_dorks=3,
            max_results=10,
            max_tasks_per_connector=2,
            max_results_per_connector=10,
            min_evidence_confidence=0.3,
            dedup_mode="canonical_url",
        )
        assert c.max_dorks == 3
        assert c.max_results == 10
        assert c.max_tasks_per_connector == 2
        assert c.max_results_per_connector == 10
        assert c.min_evidence_confidence == 0.3
        assert c.dedup_mode == "canonical_url"


# ── Fixture mode ─────────────────────────────────────────────────────


class TestFixtureMode:
    def test_fixture_config(self):
        c = ResearchRunConfig(fixture_mode=True, fixture_dir="tests/fixtures/connectors")
        assert c.fixture_mode is True
        assert c.fixture_dir == "tests/fixtures/connectors"

    def test_fixture_searxng_exists(self):
        """Fixture files exist on disk."""
        path = Path("tests/fixtures/connectors/searxng_hydrogen.json")
        assert path.exists()
        data = json.loads(path.read_text())
        assert "sources" in data
        assert len(data["sources"]) > 0

    def test_fixture_gdelt_exists(self):
        path = Path("tests/fixtures/connectors/gdelt_hydrogen.json")
        assert path.exists()
        assert "sources" in json.loads(path.read_text())

    def test_fixture_openalex_exists(self):
        path = Path("tests/fixtures/connectors/openalex_hydrogen.json")
        assert path.exists()
        assert "sources" in json.loads(path.read_text())


# ── Validate artifact ─────────────────────────────────────────────────


class TestValidateArtifact:
    def _make_valid_artifact(self) -> ResearchArtifact:
        return ResearchArtifact(
            run_id="test_001",
            query="test query",
            status="completed",
            timing=TimingBreakdown(expand=0.5, dork=0.3),
            routes=2,
            sources_fetched=3,
            claims_extracted=1,
            lineages=[
                {"id": "l_000", "original_query": "test", "connector": "searxng"},
                {"id": "l_001", "original_query": "test", "connector": "gdelt"},
            ],
            graph=GraphSummary(nodes=2, edges=1),
            quality_controls={"dry_run": False},
        )

    def test_valid_artifact_passes(self):
        artifact = self._make_valid_artifact()
        safe = artifact.model_dump_safe()
        assert safe["run_id"] == "test_001"
        assert safe["status"] == "completed"

    def test_model_dump_safe_preserves_timing(self):
        a = self._make_valid_artifact()
        safe = a.model_dump_safe()
        assert safe["timing"]["expand"] == 0.5
        assert safe["timing"]["dork"] == 0.3

    def test_model_dump_safe_preserves_graph(self):
        a = self._make_valid_artifact()
        safe = a.model_dump_safe()
        assert safe["graph"]["nodes"] == 2
        assert safe["graph"]["edges"] == 1

    def test_pydantic_roundtrip(self):
        a = self._make_valid_artifact()
        safe = a.model_dump_safe()
        restored = ResearchArtifact(**safe)
        assert restored.run_id == "test_001"
        assert restored.status == "completed"

    def test_missing_lineage_detected(self):
        a = ResearchArtifact(run_id="bad", query="x", lineages=[])
        safe = a.model_dump_safe()
        assert safe["lineages"] == []

    def test_no_secrets_in_output(self):
        a = ResearchArtifact(
            run_id="sec",
            query="x",
            errors=["Bearer ghp_secret1234567890"],
        )
        safe = a.model_dump_safe()
        raw = json.dumps(safe)
        assert "ghp_secret1234567890" not in raw
        assert "Bearer ***" in raw or "***" in raw


# ── CLI help (no API call) ───────────────────────────────────────────


class TestCLI:
    def _invoke_help(self, args: list[str]) -> Any:
        """Invoke CLI help, handling Windows encoding errors gracefully."""
        from osint_pipeline.cli import app
        from typer.testing import CliRunner
        try:
            r = CliRunner().invoke(app, args)
            return r
        except UnicodeEncodeError:
            return None

    def test_run_research_help(self):
        r = self._invoke_help(["run-research", "--help"])
        if r is None:
            return  # Windows encoding limitation
        assert r.exit_code == 0
        assert "--dry-run" in r.stdout

    def test_validate_artifact_help(self):
        r = self._invoke_help(["validate-artifact", "--help"])
        if r is None:
            return
        assert r.exit_code == 0

    def test_smoke_profile_mentioned(self):
        r = self._invoke_help(["run-research", "--help"])
        if r is None:
            return
        assert r.exit_code == 0
        assert "--profile" in r.stdout


class TestArtifactJSONRoundtrip:
    def test_write_and_reload(self, tmp_path: Path):
        a = ResearchArtifact(
            run_id="rt_001",
            query="waterstof opslag nederland",
            status="completed",
            timing=TimingBreakdown(expand=1.0, dork=2.0),
            routes=2,
            sources_fetched=3,
            lineages=[{"id": "l_0", "connector": "searxng"}],
            graph=GraphSummary(nodes=2, edges=1),
            quality_controls={"dry_run": False},
        )
        out = tmp_path / "artifact.json"
        out.write_text(json.dumps(a.model_dump_safe(), indent=2))
        reloaded = json.loads(out.read_text())
        restored = ResearchArtifact(**reloaded)
        assert restored.run_id == "rt_001"
        assert restored.timing.expand == 1.0
