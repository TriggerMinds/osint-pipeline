from __future__ import annotations

from ..models.evidence import ConflictMarker, EvidenceCollection


class EvidenceRanker:
    def rank(self, collection: EvidenceCollection) -> EvidenceCollection:
        for ev in collection.items:
            scores = []
            for claim in ev.claims:
                score = claim.confidence

                # source diversity boost
                if len(claim.supporting_urls) > 1:
                    score += 0.1

                # archive-only / disappeared penalty
                if claim.conflict_status == ConflictMarker.ARCHIVE_ONLY:
                    score *= 0.7
                elif claim.conflict_status == ConflictMarker.DISAPPEARED:
                    score *= 0.5
                elif claim.conflict_status == ConflictMarker.CONFLICTING:
                    score *= 0.6

                scores.append(min(score, 1.0))

            if scores:
                ev.confidence_score = sum(scores) / len(scores)

        collection.items.sort(key=lambda e: e.confidence_score, reverse=True)
        return collection
