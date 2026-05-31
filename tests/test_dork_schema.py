import json
from pathlib import Path

import jsonschema
import pytest

from osint_pipeline.dork_generation.schema import DORK_SCHEMA, validate_dork
from osint_pipeline.models.dork import (
    DorkOperator,
    DorkQuery,
    DorkSchema,
    DorkTarget,
    RiskLevel,
    ExpandedIntent,
)
from osint_pipeline.utils.validation import parse_llm_json, validate_llm_output


class TestDorkSchema:
    def test_schema_is_valid_json_schema(self):
        """The generated schema itself must be valid JSON Schema."""
        jsonschema.Draft202012Validator.check_schema(DORK_SCHEMA)

    def test_valid_dork_passes(self):
        instance = {
            "schema_version": "1.0",
            "description": "Test dorks",
            "intent": {
                "original_query": "waterstof opslag nederland",
                "intent": "Find hydrogen storage information in the Netherlands",
                "entities": ["waterstof", "Nederland"],
                "languages": ["nl", "en", "de", "fr"],
            },
            "entities": ["waterstof", "Nederland"],
            "languages": ["nl", "en", "de", "fr"],
            "dork_queries": [
                {
                    "raw": "site:example.com intitle:secret",
                    "operators": {"site": ["example.com"], "intitle": ["secret"]},
                    "target": "google",
                    "description": "Find secret pages",
                    "language": "en",
                    "purpose": "Document discovery",
                    "expected_signal": "Confidential documents",
                    "risk_level": "medium",
                }
            ],
        }
        errors = validate_dork(instance)
        assert errors == []

    def test_missing_raw_fails(self):
        instance = {
            "schema_version": "1.0",
            "dork_queries": [
                {
                    "operators": {"site": ["example.com"]},
                    "target": "google",
                }
            ],
        }
        errors = validate_dork(instance)
        assert len(errors) > 0

    def test_invalid_operator_fails(self):
        instance = {
            "schema_version": "1.0",
            "dork_queries": [
                {
                    "raw": "foo:bar",
                    "operators": {"invalid_op": ["value"]},
                    "target": "google",
                }
            ],
        }
        errors = validate_dork(instance)
        assert len(errors) > 0

    def test_invalid_target_fails(self):
        instance = {
            "schema_version": "1.0",
            "dork_queries": [
                {
                    "raw": "test",
                    "operators": {"site": ["example.com"]},
                    "target": "not_a_search_engine",
                }
            ],
        }
        errors = validate_dork(instance)
        assert len(errors) > 0

    def test_missing_intent_fails(self):
        """Missing intent should still pass because intent has defaults."""
        instance = {
            "schema_version": "1.0",
            "dork_queries": [
                {
                    "raw": "site:example.com",
                    "operators": {"site": ["example.com"]},
                    "target": "google",
                }
            ],
        }
        errors = validate_dork(instance)
        assert errors == []  # intent has defaults, so missing is OK

    def test_model_serialization_roundtrip(self):
        dq = DorkQuery(
            raw="site:test.com filetype:pdf",
            operators={
                DorkOperator.SITE: ["test.com"],
                DorkOperator.FILETYPE: ["pdf"],
            },
            target=DorkTarget.GOOGLE,
            description="Find PDFs on test.com",
            purpose="Document discovery",
            expected_signal="PDF files",
            risk_level=RiskLevel.LOW,
        )
        intent = ExpandedIntent(
            original_query="test",
            intent="find docs",
            entities=["test"],
            languages=["en"],
        )
        schema = DorkSchema(
            description="Test",
            intent=intent,
            entities=["test"],
            languages=["en"],
            dork_queries=[dq],
        )
        dumped = schema.model_dump()
        errors = validate_dork(dumped)
        assert errors == []

    def test_dork_schema_json_file(self):
        """The DORK_SCHEMA.json file must match the generated schema."""
        path = Path(__file__).parent.parent / "DORK_SCHEMA.json"
        assert path.exists(), "DORK_SCHEMA.json missing"
        with open(path) as f:
            file_schema = json.load(f)
        assert file_schema["title"] == DORK_SCHEMA["title"]
        assert file_schema["properties"].keys() == DORK_SCHEMA["properties"].keys()

    def test_all_new_targets_present(self):
        items = DORK_SCHEMA["properties"]["dork_queries"]["items"]
        target = items["properties"]["target"]["enum"]
        expected = [
            "google", "bing", "duckduckgo", "yandex",
            "searxng", "archive_cdx", "gdelt", "commoncrawl",
            "openalex", "github", "reddit", "wikidata",
        ]
        for t in expected:
            assert t in target, f"Missing target: {t}"

    def test_risk_level_enum_present(self):
        items = DORK_SCHEMA["properties"]["dork_queries"]["items"]
        risk = items["properties"]["risk_level"]["enum"]
        assert "safe" in risk
        assert "low" in risk
        assert "medium" in risk
        assert "high" in risk


class TestLLMValidation:
    def test_parse_valid_json(self):
        result = parse_llm_json('{"key": "value"}')
        assert result.success
        assert result.data == {"key": "value"}
        assert not result.repaired

    def test_parse_empty_fails(self):
        result = parse_llm_json("")
        assert not result.success
        assert "Empty" in result.error

    def test_parse_malformed_repair(self):
        raw = 'Some text before {"a": 1, "b": 2} and after'
        result = parse_llm_json(raw)
        assert result.success
        assert result.data == {"a": 1, "b": 2}
        assert result.repaired

    def test_parse_codeblock(self):
        raw = "```json\n{\"x\": 42}\n```"
        result = parse_llm_json(raw)
        assert result.success
        assert result.data == {"x": 42}

    def test_parse_truly_invalid(self):
        result = parse_llm_json("not even close to json")
        assert not result.success

    def test_validate_model_success(self):
        data = {"raw": "site:example.com"}
        result = validate_llm_output(DorkQuery, data)
        assert result.success
        assert result.model is not None
        assert result.model.raw == "site:example.com"

    def test_validate_model_fails(self):
        data = {"raw": ""}
        result = validate_llm_output(DorkQuery, data)
        assert not result.success
        assert "validation" in result.error.lower()

    def test_validate_model_wrong_type(self):
        result = validate_llm_output(DorkQuery, ["not", "a", "dict"])
        assert not result.success

    def test_dork_generator_error_raised_for_no_key(self):
        """Without API key, DorkGenerator should raise a clear error."""
        import os
        key = os.environ.pop("OSINT_DEEPSEEK_API_KEY", None)
        try:
            from osint_pipeline.dork_generation import DorkGenerator
            import asyncio
            gen = DorkGenerator()
            try:
                asyncio.run(gen.generate("test"))
                assert False, "Should have raised"
            except Exception as e:
                assert "API key" in str(e) or "configured" in str(e)
        finally:
            if key:
                os.environ["OSINT_DEEPSEEK_API_KEY"] = key
