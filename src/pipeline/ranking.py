from __future__ import annotations
from typing import Dict, List, Optional
from ..models.evidence import Evidence, EvidenceClaim, ConflictMarker, EvidenceCollection
from ..models.graph import KnowledgeGraph


class EvidenceRanking:
    def __init__(self, max_citations: int = 5) -> None:
        self.max_citations = max_citations

    def rank(self, collection: EvidenceCollection, graph: Optional[KnowledgeGraph] = None) -> EvidenceCollection:
        for evidence in collection.evidence_list:
            scores = []
            for claim in evidence.extracted_claims:
                score = claim.confidence

                # Boost by source diversity
                if len(claim.supporting_sources) > 1:
                    score += 0.1 * min(len(claim.supporting_sources), self.max_citations)

                # Penalize archive-only sources
                if evidence.is_archive_only:
                    score *= 0.8

                # Penalize disappeared sources
                if evidence.is_disappeared:
                    score *= 0.5

                # Boost primary-language sources
                if evidence.language == "en":
                    score += 0.05

                # Boost sources with recent snapshots
                if evidence.snapshot_date:
                    score += 0.05

                # Penalize conflicting
                if claim.conflict_status == ConflictMarker.CONFLICTING:
                    score *= 0.6
                elif claim.conflict_status == ConflictMarker.ARCHIVE_ONLY:
                    score *= 0.7

                scores.append(min(score, 1.0))

            if scores:
                evidence.confidence_score = sum(scores) / len(scores)

        # Sort evidence by score descending
        collection.evidence_list.sort(key=lambda e: e.confidence_score, reverse=True)

        return collection

    def prioritize_claims(self, collection: EvidenceCollection) -> List[EvidenceClaim]:
        all_claims = []
        for evidence in collection.evidence_list:
            for claim in evidence.extracted_claims:
                all_claims.append(claim)

        all_claims.sort(key=lambda c: c.confidence, reverse=True)
        return all_claims

    def get_citations(self, claim: EvidenceClaim, collection: EvidenceCollection) -> List[Dict]:
        citations = []
        seen_urls = set()

        for evidence in collection.evidence_list:
            if evidence.source_url in claim.supporting_sources:
                if evidence.source_url in seen_urls:
                    continue
                seen_urls.add(evidence.source_url)

                citation = {
                    "url": evidence.source_url,
                    "snapshot_date": evidence.snapshot_date,
                    "language": evidence.language,
                    "source_type": evidence.source_type,
                    "query_used": evidence.query_used,
                    "archive_url": evidence.archive_url,
                    "is_archive_only": evidence.is_archive_only,
                    "is_disappeared": evidence.is_disappeared,
                }
                citations.append(citation)

                if len(citations) >= self.max_citations:
                    break

        return citations
