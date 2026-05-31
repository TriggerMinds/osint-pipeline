from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from ..models.evidence import EvidenceCollection
from ..models.graph import KnowledgeGraph


class MaltegoExport:
    """Export OSINT findings in Maltego-compatible formats.

    No runtime dependency on Maltego SDK — pure file-based export.
    """

    @staticmethod
    def to_graphml(collection: EvidenceCollection, graph: KnowledgeGraph, path: str | Path) -> None:
        """Export entities and relations as GraphML."""
        path = Path(path)
        lines: list[str] = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<graphml xmlns="http://graphml.graphdrawing.org/xmlns"',
            '  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">',
            '  <key id="label" for="node" attr.name="label" attr.type="string"/>',
            '  <key id="type" for="node" attr.name="type" attr.type="string"/>',
            '  <key id="url" for="node" attr.name="url" attr.type="string"/>',
            '  <key id="relation" for="edge" attr.name="relation" attr.type="string"/>',
            '  <graph id="G" edgedefault="directed">',
        ]

        for eid, ent in graph.entities.items():
            lines.append(
                f'    <node id="{eid}">'
                f'<data key="label">{ent.name}</data>'
                f'<data key="type">{ent.type}</data>'
                f'<data key="url">{ent.source_urls[0] if ent.source_urls else ""}</data>'
                f'</node>'
            )

        for rel in graph.relations:
            lines.append(
                f'    <edge source="{rel.source_entity_id}" target="{rel.target_entity_id}">'
                f'<data key="relation">{rel.relation_type}</data>'
                f'</edge>'
            )

        lines.append('  </graph>')
        lines.append('</graphml>')
        path.write_text("\n".join(lines), encoding="utf-8")

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
