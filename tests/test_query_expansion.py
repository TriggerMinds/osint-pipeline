from osint_pipeline.models.query import ExpandedQuery, MultilingualQuery


class TestQueryExpansion:
    def test_expanded_query_defaults(self):
        eq = ExpandedQuery(original="test query")
        assert eq.original == "test query"
        assert eq.variants == []
        assert eq.language == "en"

    def test_expanded_query_with_variants(self):
        eq = ExpandedQuery(
            original="waterstof opslag nederland",
            variants=[
                "waterstofopslag Nederland",
                "hydrogen storage Netherlands",
                "Wasserstoffspeicher Niederlande",
            ],
            language="nl",
            rationale="Dutch query with English and German variants",
        )
        assert len(eq.variants) == 3
        assert eq.language == "nl"

    def test_multilingual_query(self):
        mq = MultilingualQuery(
            original="hydrogen storage Netherlands",
            target_language="nl",
            translated="waterstofopslag Nederland",
        )
        assert mq.target_language == "nl"
        assert mq.translated == "waterstofopslag Nederland"
        assert mq.transliteration is None

    def test_multilingual_query_with_transliteration(self):
        mq = MultilingualQuery(
            original="hydrogen storage",
            target_language="zh",
            translated="氢储存",
            transliteration="qing chu cun",
        )
        assert mq.transliteration == "qing chu cun"
