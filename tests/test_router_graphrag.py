import json
from pathlib import Path

import pytest

from osint_pipeline.router import SourceRouter, RouteResult, TARGET_CONNECTOR_MAP
from osint_pipeline.models.dork import DorkQuery, DorkTarget
from osint_pipeline.models.evidence import Evidence, EvidenceClaim, EvidenceCollection
from osint_pipeline.graphrag import EvidenceGraphBuilder, EvidenceGraphExporter, EvidenceGraph, GraphNode, GraphEdge


# ── SourceRouter ──────────────────────────────────────────────────────


class TestSourceRouter:
    @pytest.fixture
    def router(self):
        return SourceRouter()

    def test_route_searxng_target(self, router):
        dork = DorkQuery(raw="site:example.com", target=DorkTarget.SEARXNG)
        route = router.route(dork)
        assert isinstance(route, RouteResult)
        assert route.connector == "searxng"
        assert route.execution_mode == "web_search"

    def test_route_gdelt_target(self, router):
        dork = DorkQuery(raw="breaking news", target=DorkTarget.GDELT)
        route = router.route(dork)
        assert route.connector == "gdelt"
        assert route.execution_mode == "news_search"

    def test_route_archive_cdx(self, router):
        dork = DorkQuery(raw="example.com/*", target=DorkTarget.ARCHIVE_CDX)
        route = router.route(dork)
        assert route.connector == "archive_cdx"
        assert route.execution_mode == "archive_lookup"

    def test_route_openalex(self, router):
        dork = DorkQuery(raw="quantum", target=DorkTarget.OPENALEX)
        route = router.route(dork)
        assert route.connector == "openalex"
        assert route.execution_mode == "academic_search"

    def test_route_github(self, router):
        dork = DorkQuery(raw="osint", target=DorkTarget.GITHUB)
        route = router.route(dork)
        assert route.connector == "github"
        assert route.execution_mode == "code_search"

    def test_route_wikidata(self, router):
        dork = DorkQuery(raw="Einstein", target=DorkTarget.WIKIDATA)
        route = router.route(dork)
        assert route.connector == "wikidata"
        assert route.execution_mode == "entity_search"

    def test_route_reddit(self, router):
        dork = DorkQuery(raw="osint tools", target=DorkTarget.REDDIT)
        route = router.route(dork)
        assert route.connector == "reddit"
        assert route.execution_mode == "social_search"

    def test_all_targets_have_connector(self):
        for target in DorkTarget:
            assert target in TARGET_CONNECTOR_MAP, f"Missing mapping for {target}"

    def test_route_preserves_purpose_and_risk(self, router):
        dork = DorkQuery(
            raw="site:test.com",
            target=DorkTarget.GITHUB,
            purpose="Find repo",
            risk_level="low",
            language="en",
        )
        route = router.route(dork)
        assert route.purpose == "Find repo"
        assert route.risk_level == "low"

    def test_build_lineage(self, router):
        dork = DorkQuery(raw="site:example.com", target=DorkTarget.SEARXNG)
        route = router.route(dork)
        lineage = router.build_lineage(dork, route, lineage_id="l_001", original_query="test query")
        assert lineage.id == "l_001"
        assert lineage.original_query == "test query"
        assert lineage.connector == "searxng"
        assert lineage.dork_target == "searxng"


# ── EvidenceGraph (GraphRAG-light) ────────────────────────────────────


class TestEvidenceGraphBuilder:
    @pytest.fixture
    def builder(self):
        return EvidenceGraphBuilder()

    def _make_collection(self) -> EvidenceCollection:
        ec = EvidenceCollection(query="test graph")
        ev1 = Evidence(
            source_url="https://example.com/doc1",
            language="en",
            source_type="searxng",
            discovered_by_query="test",
            confidence_score=0.9,
            claims=[
                EvidenceClaim(claim="First claim", confidence=0.9, category="event"),
            ],
        )
        ev2 = Evidence(
            source_url="https://other.org/page",
            language="nl",
            source_type="gdelt",
            discovered_by_query="test",
            confidence_score=0.7,
            claims=[
                EvidenceClaim(claim="Second claim", confidence=0.7),
            ],
        )
        ec.items.extend([ev1, ev2])
        return ec

    def test_build_creates_nodes(self, builder):
        ec = self._make_collection()
        graph = builder.build(ec)
        assert len(graph.nodes) > 0
        # Should have source nodes, domain nodes, language nodes, claim nodes
        node_types = {n.node_type for n in graph.nodes.values()}
        assert "source" in node_types
        assert "domain" in node_types
        assert "claim" in node_types
        assert "language" in node_types

    def test_build_creates_edges(self, builder):
        ec = self._make_collection()
        graph = builder.build(ec)
        assert len(graph.edges) > 0
        relations = {e.relation for e in graph.edges}
        assert "contains_claim" in relations
        assert "hosted_on" in relations
        assert "in_language" in relations

    def test_build_with_lineage(self, builder):
        from osint_pipeline.models.lineage import QueryLineage
        ec = self._make_collection()
        lineage = [
            QueryLineage(
                id="l1", original_query="test", connector="gdelt",
                retrieved_url="https://other.org/page",
            ),
        ]
        graph = builder.build(ec, lineage=lineage)
        # Should have a connector node
        conn_nodes = [n for n in graph.nodes.values() if n.node_type == "connector"]
        assert len(conn_nodes) > 0


class TestEvidenceGraphExporter:
    def _make_graph(self) -> EvidenceGraph:
        g = EvidenceGraph(query="test")
        g.nodes["n1"] = GraphNode(id="n1", label="Node 1", node_type="entity")
        g.nodes["n2"] = GraphNode(id="n2", label="Node 2", node_type="source")
        g.edges.append(GraphEdge(source_id="n1", target_id="n2", relation="references"))
        return g

    def test_export_json(self, tmp_path: Path):
        g = self._make_graph()
        out = tmp_path / "graph.json"
        EvidenceGraphExporter.to_json(g, out)
        assert out.exists()
        data = json.loads(out.read_text())
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1

    def test_export_graphml(self, tmp_path: Path):
        g = self._make_graph()
        out = tmp_path / "graph.graphml"
        EvidenceGraphExporter.to_graphml(g, out)
        assert out.exists()
        content = out.read_text()
        assert "<graphml" in content
        assert "Node 1" in content
        assert "references" in content

    def test_graphml_valid_xml(self, tmp_path: Path):
        """Exported GraphML can be parsed with ElementTree."""
        import xml.etree.ElementTree as ET
        g = self._make_graph()
        out = tmp_path / "valid.graphml"
        EvidenceGraphExporter.to_graphml(g, out)
        tree = ET.parse(str(out))
        root = tree.getroot()
        assert root.tag.endswith("graphml")

    def test_graphml_claim_with_ampersand(self, tmp_path: Path):
        """Claims containing & must produce valid XML."""
        g = EvidenceGraph(query="test")
        g.nodes["n1"] = GraphNode(id="n1", label="A & B", node_type="claim")
        out = tmp_path / "amp.graphml"
        EvidenceGraphExporter.to_graphml(g, out)
        import xml.etree.ElementTree as ET
        tree = ET.parse(str(out))  # raises if invalid XML
        root = tree.getroot()
        assert "A &amp; B" in out.read_text()

    def test_graphml_url_with_query_string(self, tmp_path: Path):
        """URLs with ?a=1&b=2 must produce valid XML."""
        g = EvidenceGraph(query="test")
        g.nodes["n1"] = GraphNode(
            id="n1",
            label="https://example.com/page?a=1&b=2",
            node_type="source",
        )
        out = tmp_path / "url.graphml"
        EvidenceGraphExporter.to_graphml(g, out)
        import xml.etree.ElementTree as ET
        tree = ET.parse(str(out))
        root = tree.getroot()
        assert "a=1&amp;b=2" in out.read_text()

    def test_graphml_claim_with_html_tags(self, tmp_path: Path):
        """Claims containing <script> must produce valid XML."""
        g = EvidenceGraph(query="test")
        g.nodes["n1"] = GraphNode(
            id="n1",
            label='<script>alert("xss")</script>',
            node_type="claim",
        )
        out = tmp_path / "script.graphml"
        EvidenceGraphExporter.to_graphml(g, out)
        import xml.etree.ElementTree as ET
        tree = ET.parse(str(out))
        content = out.read_text()
        assert "&lt;script&gt;" in content

    def test_graphml_unicode_label(self, tmp_path: Path):
        """Unicode labels must survive roundtrip via XML."""
        g = EvidenceGraph(query="test")
        g.nodes["n1"] = GraphNode(id="n1", label="水素貯蔵", node_type="entity")
        out = tmp_path / "unicode.graphml"
        EvidenceGraphExporter.to_graphml(g, out)
        import xml.etree.ElementTree as ET
        tree = ET.parse(str(out))
        ns = "{http://graphml.graphdrawing.org/xmlns}"
        for data in tree.iter(f"{ns}data"):
            if data.attrib.get("key") == "label":
                assert data.text == "水素貯蔵"
                return
        assert False, "label data element not found"

    def test_export_csv_nodes(self, tmp_path: Path):
        g = self._make_graph()
        out = tmp_path / "nodes.csv"
        EvidenceGraphExporter.to_csv_nodes(g, out)
        assert out.exists()
        content = out.read_text()
        assert "id,label,node_type,confidence" in content
        assert "Node 1" in content

    def test_export_csv_edges(self, tmp_path: Path):
        g = self._make_graph()
        out = tmp_path / "edges.csv"
        EvidenceGraphExporter.to_csv_edges(g, out)
        assert out.exists()
        content = out.read_text()
        assert "source_id,target_id,relation,weight" in content
        assert "references" in content


# ── CLI command verification ──────────────────────────────────────────


class TestCLINewCommands:
    def test_route_dork_help(self):
        from osint_pipeline.cli import app
        from typer.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(app, ["route-dork", "--help"])
        assert result.exit_code == 0

    def test_run_research_help(self):
        from osint_pipeline.cli import app
        from typer.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(app, ["run-research", "--help"])
        assert result.exit_code == 0

    def test_export_graph_help(self):
        from osint_pipeline.cli import app
        from typer.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(app, ["export-graph", "--help"])
        assert result.exit_code == 0

    def test_route_dork_with_file(self, tmp_path: Path):
        """route-dork with a valid DorkSchema JSON file works."""
        from osint_pipeline.cli import app
        from typer.testing import CliRunner
        dork_file = tmp_path / "dorks.json"
        dork_file.write_text(json.dumps({
            "schema_version": "1.0",
            "dork_queries": [
                {
                    "raw": "site:example.com",
                    "operators": {"site": ["example.com"]},
                    "target": "google",
                }
            ],
        }))
        runner = CliRunner()
        result = runner.invoke(app, ["route-dork", str(dork_file)])
        assert result.exit_code == 0
        assert "SearXNG" in result.stdout or "searxng" in result.stdout


# ── .env.example no secrets ───────────────────────────────────────────


class TestEnvExample:
    def test_no_secrets_in_env_example(self):
        """.env.example contains no real tokens, IPs, or credentials."""
        path = Path(__file__).parent.parent / ".env.example"
        assert path.exists()
        content = path.read_text()
        # Should not contain real secrets
        assert "ghp_" not in content or "ghp_your" in content  # placeholder only
        # All placeholder values should be empty or documented as placeholders
        assert "OSINT_GITHUB_TOKEN=" in content
        assert "OSINT_OPENALEX_EMAIL=" in content
