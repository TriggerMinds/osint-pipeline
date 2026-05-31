from __future__ import annotations
import json
from typing import Dict, List, Optional
from ..models.source import SourceResult, SourceType
from ..models.evidence import Evidence, EvidenceClaim, ConflictMarker, EvidenceCollection
from ..providers import LLMProvider, get_provider

EXTRACT_PROMPT = """You are an evidence extraction specialist. Extract factual claims from the provided source content.

Output valid JSON with:
{
  "claims": [
    {
      "claim_text": "The factual statement extracted",
      "confidence": 0.0-1.0,
      "category": "category label"
    }
  ]
}

Rules:
1. Only extract claims explicitly supported by the text
2. Do NOT infer or add information not present
3. Mark confidence low (0.3-0.5) if the claim is vague or uncertain
4. Mark confidence medium (0.5-0.8) for clear statements
5. Mark confidence high (0.8-1.0) for explicit, verifiable statements with specifics
6. If the text is empty or meaningless, return empty claims list"""


class EvidenceExtractor:
    def __init__(self, provider_name: str = "deepseek") -> None:
        self.provider: LLMProvider = get_provider(provider_name)

    async def extract_all(
        self,
        sources_by_type: Dict[SourceType, List[SourceResult]],
    ) -> EvidenceCollection:
        all_evidence: List[Evidence] = []
        all_claims: List[EvidenceClaim] = []

        for source_type, sources in sources_by_type.items():
            for source in sources:
                text = source.content_text or source.content_markdown or ""
                if not text:
                    continue

                evidence = await self._extract_single(source, text)
                all_evidence.append(evidence)
                all_claims.extend(evidence.extracted_claims)

        collection = EvidenceCollection(
            evidence_list=all_evidence,
        )

        self._detect_conflicts(collection)
        self._mark_archive_only(collection, sources_by_type)

        return collection

    async def _extract_single(self, source: SourceResult, text: str) -> Evidence:
        truncated = text[:8000]  # Token budget
        messages = [
            {"role": "system", "content": EXTRACT_PROMPT},
            {"role": "user", "content": (
                f"URL: {source.source_metadata.url}\n"
                f"Language: {source.source_metadata.language}\n"
                f"Content:\n{truncated}"
            )},
        ]

        raw = await self.provider.chat(
            messages,
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}

        claims = []
        for c in data.get("claims", []):
            claims.append(EvidenceClaim(
                claim_text=c.get("claim_text", ""),
                supporting_sources=[source.source_metadata.url],
                confidence=c.get("confidence", 0.5),
                category=c.get("category"),
            ))

        return Evidence(
            source_url=source.source_metadata.url,
            snapshot_date=source.source_metadata.snapshot_date,
            language=source.source_metadata.language,
            source_type=source.source_metadata.source_type.value,
            query_used=source.source_metadata.query_used,
            extracted_claims=claims,
            raw_text_snippet=truncated[:500],
            is_archive_only=source.is_archive_only,
            is_disappeared=source.is_disappeared,
            archive_url=source.archive_url,
        )

    def _detect_conflicts(self, collection: EvidenceCollection) -> None:
        claim_groups: Dict[str, List[EvidenceClaim]] = {}
        for evidence in collection.evidence_list:
            for claim in evidence.extracted_claims:
                key = claim.claim_text.lower().strip()[:100]
                if key not in claim_groups:
                    claim_groups[key] = []
                claim_groups[key].append(claim)

        for key, claims in claim_groups.items():
            if len(claims) < 2:
                continue

            confidences = [c.confidence for c in claims]
            avg_conf = sum(confidences) / len(confidences)
            max_diff = max(confidences) - min(confidences)

            if max_diff > 0.4:
                # Likely conflicting
                for c in claims:
                    c.conflict_status = ConflictMarker.CONFLICTING
                collection.conflicting_claims.extend(claims)
            elif max_diff > 0.2:
                for c in claims:
                    if c.conflict_status == ConflictMarker.UNCERTAIN:
                        c.conflict_status = ConflictMarker.UNCERTAIN
            else:
                for c in claims:
                    if c.conflict_status == ConflictMarker.UNCERTAIN:
                        c.conflict_status = ConflictMarker.CONSISTENT

    def _mark_archive_only(self, collection: EvidenceCollection, sources_by_type: Dict[SourceType, List[SourceResult]]) -> None:
        for source_type, sources in sources_by_type.items():
            for source in sources:
                if source.is_archive_only:
                    collection.archive_only_sources.append(source.source_metadata.url)
                    for evidence in collection.evidence_list:
                        if evidence.source_url == source.source_metadata.url:
                            for claim in evidence.extracted_claims:
                                if claim.conflict_status == ConflictMarker.UNCERTAIN:
                                    claim.conflict_status = ConflictMarker.ARCHIVE_ONLY
                if source.is_disappeared:
                    collection.disappeared_sources.append(source.source_metadata.url)
