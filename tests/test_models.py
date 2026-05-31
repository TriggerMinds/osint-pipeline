import sys
sys.path.insert(0, ".")

from src.models.intent import UserIntent, QuestionType, IntentConfidence
from src.models.query import ExpandedQuery, DorkQuery, DorkOperator, MultilingualQuery, QueryBatch
from src.models.source import SourceResult, SourceMetadata, SourceType, FetchStatus
from src.models.evidence import Evidence, EvidenceClaim, ConflictMarker, EvidenceCollection
from src.models.graph import GraphEntity, GraphRelation, KnowledgeGraph


def test_user_intent_defaults():
    intent = UserIntent(original_query="test query")
    assert intent.original_query == "test query"
    assert intent.question_type == QuestionType.UNKNOWN
    assert intent.primary_entities == []
    assert intent.preferred_languages == {"en"}
    assert intent.confidence.overall == 0.5


def test_user_intent_full():
    intent = UserIntent(
        original_query="Find information about John Doe in Moscow between 2020-2023",
        question_type=QuestionType.INVESTIGATIVE,
        primary_entities=["John Doe"],
        locations=["Moscow"],
        timeframe_start="2020-01-01",
        timeframe_end="2023-12-31",
        preferred_languages={"en", "ru"},
        requires_multilingual=True,
        requires_archival=True,
        dork_friendly=True,
    )
    assert intent.question_type == QuestionType.INVESTIGATIVE
    assert "John Doe" in intent.primary_entities
    assert "Moscow" in intent.locations
    assert intent.requires_multilingual
    assert intent.requires_archival


def test_expanded_query():
    eq = ExpandedQuery(
        original_intent="test",
        queries=["query1", "query2"],
        expansion_rationale="test expansion",
    )
    assert len(eq.queries) == 2
    assert eq.expansion_rationale == "test expansion"


def test_dork_query():
    dq = DorkQuery(
        raw_query='site:example.com intitle:secret',
        operators={DorkOperator.SITE: ["example.com"], DorkOperator.INTITLE: ["secret"]},
        target_source="google",
    )
    assert DorkOperator.SITE in dq.operators
    assert dq.operators[DorkOperator.SITE] == ["example.com"]


def test_multilingual_query():
    mq = MultilingualQuery(
        original_query="test query",
        language="ru",
        translated_query="тестовый запрос",
        transliteration="testoviy zapros",
    )
    assert mq.language == "ru"
    assert mq.translated_query == "тестовый запрос"


def test_source_metadata():
    sm = SourceMetadata(
        url="https://example.com/doc",
        timestamp="2024-01-15T10:00:00Z",
        snapshot_date="2024-01-15",
        language="en",
        source_type=SourceType.SEARXNG,
        query_used="test query",
    )
    assert sm.url == "https://example.com/doc"
    assert sm.source_type == SourceType.SEARXNG
    assert sm.fetch_status == FetchStatus.PENDING


def test_source_result():
    sm = SourceMetadata(
        url="https://example.com",
        timestamp="2024-01-01",
        source_type=SourceType.GDELT,
        query_used="test",
    )
    sr = SourceResult(
        source_metadata=sm,
        content_text="Test content here",
        is_archive_snapshot=False,
    )
    assert sr.content_text == "Test content here"
    assert not sr.is_archive_snapshot


def test_evidence_claim():
    ec = EvidenceClaim(
        claim_text="The event occurred on January 15",
        supporting_sources=["https://source1.com"],
        confidence=0.85,
        conflict_status=ConflictMarker.CONSISTENT,
    )
    assert ec.claim_text == "The event occurred on January 15"
    assert ec.confidence == 0.85
    assert ec.conflict_status == ConflictMarker.CONSISTENT


def test_evidence():
    ev = Evidence(
        source_url="https://example.com",
        language="en",
        source_type="searxng",
        query_used="test query",
        is_archive_only=False,
        is_disappeared=False,
    )
    assert len(ev.extracted_claims) == 0
    assert not ev.is_archive_only


def test_evidence_collection():
    ec = EvidenceCollection(query="test")
    assert len(ec.evidence_list) == 0
    assert len(ec.conflicting_claims) == 0


def test_conflict_detection():
    ec = EvidenceCollection(query="test")
    ev1 = Evidence(
        source_url="https://source1.com",
        language="en",
        source_type="searxng",
        query_used="test",
    )
    ev1.extracted_claims.append(EvidenceClaim(
        claim_text="The sky is blue",
        confidence=0.9,
        conflict_status=ConflictMarker.UNCERTAIN,
    ))
    ev2 = Evidence(
        source_url="https://source2.com",
        language="en",
        source_type="gdelt",
        query_used="test",
    )
    ev2.extracted_claims.append(EvidenceClaim(
        claim_text="The sky is blue",
        confidence=0.3,
        conflict_status=ConflictMarker.UNCERTAIN,
    ))
    ec.evidence_list.extend([ev1, ev2])

    # Simulate conflict detection (like EvidenceExtractor does)
    from src.pipeline.evidence_extractor import EvidenceExtractor
    extractor = EvidenceExtractor.__new__(EvidenceExtractor)
    extractor._detect_conflicts(ec)

    assert ec.conflicting_claims  # Should have conflicts due to high confidence diff
    assert ec.conflicting_claims[0].conflict_status == ConflictMarker.CONFLICTING


def test_graph_entity():
    ge = GraphEntity(
        id="ent_1",
        name="John Doe",
        type="person",
        aliases=["J. Doe"],
    )
    assert ge.name == "John Doe"
    assert "J. Doe" in ge.aliases


def test_graph_relation():
    gr = GraphRelation(
        source_entity_id="ent_1",
        target_entity_id="ent_2",
        relation_type="employed_by",
        temporal_context="2020-2023",
    )
    assert gr.source_entity_id == "ent_1"
    assert gr.target_entity_id == "ent_2"
    assert gr.relation_type == "employed_by"


def test_knowledge_graph():
    kg = KnowledgeGraph(query="test")
    kg.entities["ent_1"] = GraphEntity(id="ent_1", name="Entity 1")
    kg.entities["ent_2"] = GraphEntity(id="ent_2", name="Entity 2")
    kg.relations.append(GraphRelation(
        source_entity_id="ent_1",
        target_entity_id="ent_2",
        relation_type="related_to",
    ))
    assert len(kg.entities) == 2
    assert len(kg.relations) == 1


def test_source_router():
    from src.pipeline.source_router import SourceRouter
    router = SourceRouter()
    intent = UserIntent(
        original_query="test",
        requires_multilingual=True,
        requires_archival=True,
        question_type=QuestionType.INVESTIGATIVE,
        preferred_languages={"en", "ru"},
    )
    qb = QueryBatch(
        intent_id="1",
        expanded_queries=[ExpandedQuery(original_intent="test", queries=["q1", "q2"])],
    )
    plan = router.route(intent, qb)
    assert plan  # Should route to at least SearXNG for multilingual


def test_evidence_ranking():
    from src.pipeline.ranking import EvidenceRanking
    ranker = EvidenceRanking()
    ec = EvidenceCollection(query="test")
    ev = Evidence(
        source_url="https://example.com",
        language="en",
        source_type="searxng",
        query_used="test",
        confidence_score=0.5,
    )
    ev.extracted_claims.append(EvidenceClaim(
        claim_text="test claim",
        confidence=0.8,
        conflict_status=ConflictMarker.CONSISTENT,
    ))
    ec.evidence_list.append(ev)
    ranked = ranker.rank(ec)
    assert ranked.evidence_list[0].confidence_score >= 0


if __name__ == "__main__":
    test_user_intent_defaults()
    test_user_intent_full()
    test_expanded_query()
    test_dork_query()
    test_multilingual_query()
    test_source_metadata()
    test_source_result()
    test_evidence_claim()
    test_evidence()
    test_evidence_collection()
    test_conflict_detection()
    test_graph_entity()
    test_graph_relation()
    test_knowledge_graph()
    test_source_router()
    test_evidence_ranking()
    print("All tests passed!")
