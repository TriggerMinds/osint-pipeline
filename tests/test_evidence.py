from osint_pipeline.models.evidence import (
    Evidence,
    EvidenceClaim,
    EvidenceCollection,
    ConflictMarker,
)


class TestEvidence:
    def test_evidence_claim_defaults(self):
        c = EvidenceClaim(claim="test claim", confidence=0.8)
        assert c.claim == "test claim"
        assert c.confidence == 0.8
        assert c.conflict_status == ConflictMarker.UNCERTAIN
        assert c.supporting_urls == []

    def test_evidence_creation(self):
        e = Evidence(
            source_url="https://example.com",
            language="en",
            source_type="searxng",
            discovered_by_query="test",
        )
        assert e.claims == []
        assert e.confidence_score == 0.5
        assert e.archive_url is None

    def test_evidence_collection(self):
        c = EvidenceCollection(query="test query")
        assert c.query == "test query"
        assert c.items == []

    def test_conflict_status_values(self):
        assert ConflictMarker.CONSISTENT.value == "consistent"
        assert ConflictMarker.CONFLICTING.value == "conflicting"
        assert ConflictMarker.ARCHIVE_ONLY.value == "archive_only"
        assert ConflictMarker.DISAPPEARED.value == "disappeared"

    def test_evidence_with_claims(self):
        e = Evidence(
            source_url="https://source.com",
            language="en",
            source_type="gdelt",
            discovered_by_query="news",
            claims=[
                EvidenceClaim(claim="claim 1", confidence=0.9),
                EvidenceClaim(claim="claim 2", confidence=0.7),
            ],
        )
        assert len(e.claims) == 2
        assert e.claims[0].confidence == 0.9

    def test_evidence_confidence_score_bound(self):
        e = Evidence(
            source_url="https://x.com",
            language="en",
            source_type="searxng",
            discovered_by_query="q",
            confidence_score=1.0,
        )
        assert e.confidence_score == 1.0
