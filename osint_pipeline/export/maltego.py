from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from ..models.evidence import EvidenceCollection
from ..models.graph import KnowledgeGraph


def _add_data(parent: ET.Element, key: str, value: str) -> None:
    d = ET.SubElement(parent, "data", key=key)
    d.text = value


class MaltegoExport:
    """Export OSINT findings in Maltego-compatible formats.

    No runtime dependency on Maltego SDK — pure file-based export.
    """

    @staticmethod
    def to_graphml(collection: EvidenceCollection, graph: KnowledgeGraph, path: str | Path) -> None:
        """Export entities and relations as GraphML."""
        path = Path(path)

        root = ET.Element("graphml", xmlns="http://graphml.graphdrawing.org/xmlns")
        ET.SubElement(root, "key", attrib={"id": "label", "for": "node", "attr.name": "label", "attr.type": "string"})
        ET.SubElement(root, "key", attrib={"id": "type", "for": "node", "attr.name": "type", "attr.type": "string"})
        ET.SubElement(root, "key", attrib={"id": "url", "for": "node", "attr.name": "url", "attr.type": "string"})
        ET.SubElement(root, "key", attrib={"id": "relation", "for": "edge", "attr.name": "relation", "attr.type": "string"})
        graph_el = ET.SubElement(root, "graph", attrib={"id": "G", "edgedefault": "directed"})

        for eid, ent in graph.entities.items():
            node_el = ET.SubElement(graph_el, "node", attrib={"id": eid})
            _add_data(node_el, "label", ent.name)
            _add_data(node_el, "type", ent.type)
            _add_data(node_el, "url", ent.source_urls[0] if ent.source_urls else "")

        for rel in graph.relations:
            edge_el = ET.SubElement(graph_el, "edge", attrib={"source": rel.source_entity_id, "target": rel.target_entity_id})
            _add_data(edge_el, "relation", rel.relation_type)

        tree = ET.ElementTree(root)
        tree.write(str(path), encoding="utf-8", xml_declaration=True)

    @staticmethod
    def to_csv(collection: EvidenceCollection, path: str | Path) -> None:
        """Export evidence as CSV with source, claim, confidence, conflict."""
        path = Path(path)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["source_url", "claim", "confidence", "conflict_status", "language", "category"])
            for ev in collection.items:
                for claim in ev.claims:
                    writer.writerow([
                        ev.source_url,
                        claim.claim,
                        claim.confidence,
                        claim.conflict_status.value,
                        ev.language,
                        claim.category or "",
                    ])

    @staticmethod
    def to_jsonl(collection: EvidenceCollection, path: str | Path) -> None:
        """Export evidence as JSONL (one JSON object per line)."""
        path = Path(path)
        with open(path, "w", encoding="utf-8") as f:
            for ev in collection.items:
                for claim in ev.claims:
                    line = {
                        "source_url": ev.source_url,
                        "claim": claim.claim,
                        "confidence": claim.confidence,
                        "conflict_status": claim.conflict_status.value,
                        "language": ev.language,
                        "category": claim.category,
                        "snapshot_date": ev.snapshot_date,
                        "discovered_by_query": ev.discovered_by_query,
                    }
                    f.write(json.dumps(line, ensure_ascii=False) + "\n")
