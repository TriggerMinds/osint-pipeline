from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

from .models.evidence import EvidenceCollection
from .models.lineage import QueryLineage


class GraphNode(BaseModel):
    id: str
    label: str
    node_type: str = "entity"  # entity, source, domain, claim, language
    source_urls: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    confidence: float = 1.0


class GraphEdge(BaseModel):
    source_id: str
    target_id: str
    relation: str = "related_to"
    weight: float = 1.0
    metadata: dict = Field(default_factory=dict)


class EvidenceGraph(BaseModel):
    query: str = ""
    nodes: dict[str, GraphNode] = Field(default_factory=dict)
    edges: list[GraphEdge] = Field(default_factory=list)


class EvidenceGraphBuilder:
    def build(
        self,
        collection: EvidenceCollection,
        lineage: Optional[list[QueryLineage]] = None,
    ) -> EvidenceGraph:
        graph = EvidenceGraph(query=collection.query)
        node_ids: set[str] = set()

        for ev in collection.items:
            # Source URL node
            src_id = self._node_id("src", ev.source_url)
            if src_id not in node_ids:
                domain = ev.source_url.split("/")[2] if "//" in ev.source_url else ""
                graph.nodes[src_id] = GraphNode(
                    id=src_id,
                    label=ev.source_url,
                    node_type="source",
                    source_urls=[ev.source_url],
                    metadata={
                        "language": ev.language,
                        "source_type": ev.source_type,
                        "snapshot_date": ev.snapshot_date or "",
                        "confidence_score": ev.confidence_score,
                    },
                    confidence=ev.confidence_score,
                )
                node_ids.add(src_id)

                # Domain node + edge
                if domain:
                    dom_id = self._node_id("dom", domain)
                    if dom_id not in node_ids:
                        graph.nodes[dom_id] = GraphNode(
                            id=dom_id,
                            label=domain,
                            node_type="domain",
                        )
                        node_ids.add(dom_id)
                    graph.edges.append(GraphEdge(
                        source_id=src_id,
                        target_id=dom_id,
                        relation="hosted_on",
                    ))

            # Language node + edge
            if ev.language:
                lang_id = self._node_id("lang", ev.language)
                if lang_id not in node_ids:
                    graph.nodes[lang_id] = GraphNode(
                        id=lang_id,
                        label=ev.language,
                        node_type="language",
                    )
                    node_ids.add(lang_id)
                graph.edges.append(GraphEdge(
                    source_id=src_id,
                    target_id=lang_id,
                    relation="in_language",
                ))

            # Claims
            for claim in ev.claims:
                claim_id = self._node_id("claim", claim.claim[:80])
                if claim_id not in node_ids:
                    graph.nodes[claim_id] = GraphNode(
                        id=claim_id,
                        label=claim.claim[:120],
                        node_type="claim",
                        source_urls=[ev.source_url],
                        metadata={
                            "confidence": claim.confidence,
                            "conflict_status": claim.conflict_status.value,
                            "category": claim.category or "",
                        },
                        confidence=claim.confidence,
                    )
                    node_ids.add(claim_id)
                graph.edges.append(GraphEdge(
                    source_id=src_id,
                    target_id=claim_id,
                    relation="contains_claim",
                    weight=claim.confidence,
                ))

        # Lineage links
        if lineage:
            for li in lineage:
                if li.retrieved_url:
                    lid = self._node_id("src", li.retrieved_url)
                    if lid in graph.nodes and li.connector:
                        conn_id = self._node_id("conn", li.connector)
                        if conn_id not in node_ids:
                            graph.nodes[conn_id] = GraphNode(
                                id=conn_id,
                                label=li.connector,
                                node_type="connector",
                            )
                            node_ids.add(conn_id)
                        graph.edges.append(GraphEdge(
                            source_id=lid,
                            target_id=conn_id,
                            relation="retrieved_via",
                        ))

        return graph

    @staticmethod
    def _node_id(prefix: str, value: str) -> str:
        import hashlib
        h = hashlib.sha256(value.encode()).hexdigest()[:12]
        return f"{prefix}_{h}"


def _add_data(parent, key: str, value: str) -> None:
    """Add a <data key="..."> element with escaped text content."""
    import xml.etree.ElementTree as ET
    d = ET.SubElement(parent, "data", key=key)
    d.text = value


class EvidenceGraphExporter:
    @staticmethod
    def to_json(graph: EvidenceGraph, path: str | Path) -> None:
        path = Path(path)
        path.write_text(
            json.dumps(graph.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def to_graphml(graph: EvidenceGraph, path: str | Path) -> None:
        import xml.etree.ElementTree as ET

        root = ET.Element("graphml", xmlns="http://graphml.graphdrawing.org/xmlns")
        ET.SubElement(root, "key", attrib={"id": "label", "for": "node", "attr.name": "label", "attr.type": "string"})
        ET.SubElement(root, "key", attrib={"id": "type", "for": "node", "attr.name": "node_type", "attr.type": "string"})
        ET.SubElement(root, "key", attrib={"id": "rel", "for": "edge", "attr.name": "relation", "attr.type": "string"})
        ET.SubElement(root, "key", attrib={"id": "weight", "for": "edge", "attr.name": "weight", "attr.type": "double"})
        graph_el = ET.SubElement(root, "graph", attrib={"id": "G", "edgedefault": "directed"})

        for nid, node in graph.nodes.items():
            node_el = ET.SubElement(graph_el, "node", attrib={"id": nid})
            _add_data(node_el, "label", node.label)
            _add_data(node_el, "type", node.node_type)

        for edge in graph.edges:
            edge_el = ET.SubElement(graph_el, "edge", attrib={"source": edge.source_id, "target": edge.target_id})
            _add_data(edge_el, "rel", edge.relation)
            _add_data(edge_el, "weight", str(edge.weight))

        tree = ET.ElementTree(root)
        tree.write(str(path), encoding="utf-8", xml_declaration=True)

    @staticmethod
    def to_csv_nodes(graph: EvidenceGraph, path: str | Path) -> None:
        path = Path(path)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "label", "node_type", "confidence"])
            for n in graph.nodes.values():
                w.writerow([n.id, n.label, n.node_type, n.confidence])

    @staticmethod
    def to_csv_edges(graph: EvidenceGraph, path: str | Path) -> None:
        path = Path(path)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["source_id", "target_id", "relation", "weight"])
            for e in graph.edges:
                w.writerow([e.source_id, e.target_id, e.relation, e.weight])
