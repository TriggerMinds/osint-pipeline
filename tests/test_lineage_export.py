from pathlib import Path

from osint_pipeline.models.lineage import QueryLineage, ResearchRun
from osint_pipeline.models.source import SourceMetadata, SourceType
from osint_pipeline.models.evidence import Evidence, EvidenceClaim, EvidenceCollection
from osint_pipeline.models.graph import GraphEntity, GraphRelation, KnowledgeGraph
from osint_pipeline.export.maltego import MaltegoExport


# ── QueryLineage models ───────────────────────────────────────────────


class TestQueryLineage:
    def test_query_lineage_defaults(self):
        ql = QueryLineage()
        assert ql.id == ""
        assert ql.original_query == ""
        assert ql.language == "en"

    def test_query_lineage_full(self):
        ql = QueryLineage(
            id="lineage_001",
            original_query="hydrogen storage",
            expanded_query='site:nl "waterstof" filetype:pdf',
            language="nl",
            dork_raw='site:nl "waterstof" filetype:pdf',
            dork_target="google",
            connector="searxng",
            retrieved_url="https://example.com/doc.pdf",
            archive_snapshot_date="2024-06-01T00:00:00",
        )
        assert ql.id == "lineage_001"
        assert ql.connector == "searxng"

    def test_research_run_defaults(self):
        run = ResearchRun(original_query="test")
        assert run.original_query == "test"
        assert run.status == "in_progress"
        assert run.query_lineages == []

    def test_research_run_with_lineages(self):
        run = ResearchRun(
            id="run_001",
            original_query="test query",
            query_lineages=[
                QueryLineage(id="l1", expanded_query="q1", connector="gdelt"),
                QueryLineage(id="l2", expanded_query="q2", connector="searxng"),
            ],
        )
        assert len(run.query_lineages) == 2
        assert run.total_sources == 0


# ── SourceMetadata with run_id and query_lineage_id ───────────────────


class TestSourceMetadataLineage:
    def test_source_metadata_has_lineage_fields(self):
        sm = SourceMetadata(
            url="https://example.com",
            source_type=SourceType.SEARXNG,
            discovered_by_query="test",
        )
        assert hasattr(sm, "run_id")
        assert hasattr(sm, "query_lineage_id")
        assert sm.run_id == ""
        assert sm.query_lineage_id == ""

    def test_source_metadata_lineage_assigned(self):
        sm = SourceMetadata(
            url="https://example.com",
            source_type=SourceType.GDELT,
            discovered_by_query="test",
            run_id="run_001",
            query_lineage_id="l_001",
        )
        assert sm.run_id == "run_001"
        assert sm.query_lineage_id == "l_001"


# ── Maltego export ────────────────────────────────────────────────────


class TestMaltegoExport:
    def _make_evidence(self) -> EvidenceCollection:
        ec = EvidenceCollection(query="test")
        ev = Evidence(
            source_url="https://example.com",
            language="en",
            source_type="searxng",
            discovered_by_query="test",
            claims=[
                EvidenceClaim(claim="test claim", confidence=0.9),
            ],
        )
        ec.items.append(ev)
        return ec

    def _make_graph(self) -> KnowledgeGraph:
        kg = KnowledgeGraph(query="test")
        kg.entities["e1"] = GraphEntity(id="e1", name="Entity 1", type="person")
        kg.entities["e2"] = GraphEntity(id="e2", name="Entity 2", type="org")
        kg.relations.append(
            GraphRelation(
                source_entity_id="e1",
                target_entity_id="e2",
                relation_type="works_for",
            )
        )
        return kg

    def test_to_csv(self, tmp_path: Path):
        ec = self._make_evidence()
        out = tmp_path / "test.csv"
        MaltegoExport.to_csv(ec, out)
        assert out.exists()
        content = out.read_text()
        assert "source_url" in content
        assert "test claim" in content

    def test_to_jsonl(self, tmp_path: Path):
        ec = self._make_evidence()
        out = tmp_path / "test.jsonl"
        MaltegoExport.to_jsonl(ec, out)
        assert out.exists()
        lines = out.read_text().strip().split("\n")
        assert len(lines) == 1
        assert "test claim" in lines[0]

    def test_to_graphml(self, tmp_path: Path):
        ec = self._make_evidence()
        kg = self._make_graph()
        out = tmp_path / "test.graphml"
        MaltegoExport.to_graphml(ec, kg, out)
        assert out.exists()
        content = out.read_text()
        assert "<graphml" in content
        assert "Entity 1" in content
        assert "works_for" in content

    def test_maltego_graphml_valid_xml(self, tmp_path: Path):
        """Maltego GraphML can be parsed with ElementTree."""
        import xml.etree.ElementTree as ET
        ec = self._make_evidence()
        kg = self._make_graph()
        out = tmp_path / "valid.graphml"
        MaltegoExport.to_graphml(ec, kg, out)
        tree = ET.parse(str(out))
        assert tree.getroot().tag.endswith("graphml")

    def test_maltego_graphml_special_chars(self, tmp_path: Path):
        """Entity names with &, <, > produce valid XML."""
        import xml.etree.ElementTree as ET
        ec = self._make_evidence()
        kg = KnowledgeGraph(query="test")
        kg.entities["e1"] = GraphEntity(id="e1", name="AT&T Company", type="org")
        kg.entities["e2"] = GraphEntity(id="e2", name="<script>bad</script>", type="entity")
        kg.relations.append(
            GraphRelation(source_entity_id="e1", target_entity_id="e2", relation_type="owns")
        )
        out = tmp_path / "special.graphml"
        MaltegoExport.to_graphml(ec, kg, out)
        tree = ET.parse(str(out))
        content = out.read_text()
        assert "AT&amp;T" in content
        assert "&lt;script&gt;" in content


# ── Adapter stubs ─────────────────────────────────────────────────────


class TestAdapters:
    def test_waymore_adapter_has_install_hint(self):
        from osint_pipeline.adapters import WaymoreAdapter
        wa = WaymoreAdapter()
        assert "waymore" in wa.install_hint.lower()

    def test_photon_adapter_is_stub(self):
        from osint_pipeline.adapters import PhotonAdapter
        pa = PhotonAdapter()
        assert pa.available is False
        assert "stub" in pa.install_hint.lower()

    def test_spiderfoot_adapter_is_stub(self):
        from osint_pipeline.adapters import SpiderFootAdapter
        sa = SpiderFootAdapter()
        assert sa.available is False
        assert "stub" in sa.install_hint.lower()
