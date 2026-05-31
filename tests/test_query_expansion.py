import pytest

from osint_pipeline.models.query import ExpandedQuery, MultilingualQuery
from osint_pipeline.utils.validation import parse_llm_json, validate_llm_output


class TestQueryExpansion:
    def test_expanded_query_requires_language_and_variants(self):
        eq = ExpandedQuery(original="test query", language="en", variants=["v1"])
        assert eq.original == "test query"
        assert eq.variants == ["v1"]
        assert eq.language == "en"

    def test_expanded_query_empty_variants_fails(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ExpandedQuery(original="test", language="en", variants=[])

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

    def test_expanded_query_validation(self):
        data = {
            "original": "test",
            "variants": ["variant 1", "variant 2"],
            "language": "en",
            "rationale": "testing validation",
        }
        result = validate_llm_output(ExpandedQuery, data)
        assert result.success
        assert result.model.variants == ["variant 1", "variant 2"]

    def test_expanded_query_minimal_nl_en_de_fr(self):
        """This test verifies the model supports all required language fields."""
        langs = {"nl", "en", "de", "fr"}
        results = []
        for lang in langs:
            eq = ExpandedQuery(original="test", language=lang, variants=[f"test in {lang}"])
            results.append(eq)
        assert len(results) == 4
        assert {r.language for r in results} == langs

    def test_multilingual_query(self):
        mq = MultilingualQuery(
            original="hydrogen storage Netherlands",
            target_language="nl",
            translated="waterstofopslag Nederland",
        )
        assert mq.target_language == "nl"
        assert mq.translated == "waterstofopslag Nederland"

    def test_multilingual_query_with_transliteration(self):
        mq = MultilingualQuery(
            original="hydrogen storage",
            target_language="zh",
            translated="氢储存",
            transliteration="qing chu cun",
        )
        assert mq.transliteration == "qing chu cun"


class TestLLMJSONParsing:
    def test_parse_expansion_response(self):
        raw = """{
            "expansions": [
                {"language": "nl", "variants": ["v1"], "rationale": "r1"},
                {"language": "en", "variants": ["v2"], "rationale": "r2"},
                {"language": "de", "variants": ["v3"], "rationale": "r3"},
                {"language": "fr", "variants": ["v4"], "rationale": "r4"}
            ]
        }"""
        result = parse_llm_json(raw)
        assert result.success
        assert len(result.data["expansions"]) == 4

    def test_malformed_json_with_codeblock(self):
        raw = "```json\n{\"expansions\": [{\"language\": \"nl\", \"variants\": [\"test\"]}]}\n```"
        result = parse_llm_json(raw)
        assert result.success
        assert result.data["expansions"][0]["language"] == "nl"

    def test_truly_invalid_llm_output(self):
        result = parse_llm_json("This is not JSON at all and cannot be repaired")
        assert not result.success
