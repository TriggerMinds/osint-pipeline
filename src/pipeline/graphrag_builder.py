from __future__ import annotations
import json
from typing import Dict, List, Optional
from ..models.evidence import EvidenceCollection, EvidenceClaim
from ..models.graph import GraphEntity, GraphRelation, KnowledgeGraph
from ..providers import LLMProvider, get_provider

ENTITY_PROMPT = """Extract entities and their relationships from the provided evidence claims.

Output valid JSON:
{
  "entities": [
    {
      "id": "unique_id",
      "name": "entity name",
      "type": "person|organization|location|event|concept|document|technology|other",
      "aliases": ["alt_name1"],
      "attributes": {"key": "value"}
    }
  ],
  "relations": [
    {
      "source_entity_id": "id1",
      "target_entity_id": "id2",
      "relation_type": "type of relationship",
      "temporal_context": "YYYY-MM-DD or timeframe if available"
    }
  ]
}

Extract only entities and relations explicitly supported by the evidence."""


class GraphRAGBuilder:
    def __init__(
        self,
        entity_provider: str = "deepseek",
        relation_provider: str = "deepseek",
    ) -> None:
        self.entity_extractor: LLMProvider = get_provider(entity_provider)
        self.relation_extractor: LLMProvider = get_provider(relation_provider)

    async def build(self, evidence: EvidenceCollection) -> KnowledgeGraph:
        all_claims = []
        for ev in evidence.evidence_list:
            all_claims.extend(ev.extracted_claims)

        if not all_claims:
            return KnowledgeGraph()

        # Batch extraction per source for context
        claims_text = json.dumps(
            [c.model_dump() for c in all_claims],
            indent=2,
        )[:12000]

        messages = [
            {"role": "system", "content": ENTITY_PROMPT},
            {"role": "user", "content": f"Extract entities and relations from:\n\n{claims_text}"},
        ]

        raw = await self.entity_extractor.chat(
            messages,
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}

        entities: Dict[str, GraphEntity] = {}
        for e in data.get("entities", []):
            entity = GraphEntity(
                id=e.get("id", f"ent_{len(entities)}"),
                name=e.get("name", "unknown"),
                type=e.get("type", "unknown"),
                aliases=e.get("aliases", []),
                attributes=e.get("attributes", {}),
                source_urls=list(set(
                    c.supporting_sources[0]
                    for c in all_claims
                    if e.get("name", "").lower() in c.claim_text.lower()
                )),
                confidence=e.get("confidence", 0.5),
            )
            entities[entity.id] = entity

        relations = []
        for r in data.get("relations", []):
            if r.get("source_entity_id") not in entities or r.get("target_entity_id") not in entities:
                continue

            relation = GraphRelation(
                source_entity_id=r["source_entity_id"],
                target_entity_id=r["target_entity_id"],
                relation_type=r.get("relation_type", "related_to"),
                attributes=r.get("attributes", {}),
                temporal_context=r.get("temporal_context"),
                confidence=r.get("confidence", 0.5),
            )
            relations.append(relation)

        return KnowledgeGraph(
            entities=entities,
            relations=relations,
            metadata={
                "total_claims": len(all_claims),
                "total_sources": len(evidence.evidence_list),
                "conflicting_claims": len(evidence.conflicting_claims),
            },
        )
