import json
from pathlib import Path

import jsonschema
import pytest

from osint_pipeline.dork_generation.schema import DORK_SCHEMA, validate_dork
from osint_pipeline.models.dork import DorkOperator, DorkQuery, DorkSchema


class TestDorkSchema:
    def test_schema_is_valid_json_schema(self):
        """The schema itself must be valid JSON Schema."""
        jsonschema.Draft202012Validator.check_schema(DORK_SCHEMA)

    def test_valid_dork_passes(self):
        instance = {
            "schema_version": "1.0",
            "description": "Test dorks",
            "dork_queries": [
                {
                    "raw": "site:example.com intitle:secret",
                    "operators": {"site": ["example.com"], "intitle": ["secret"]},
                    "target": "google",
                    "description": "Find secret pages",
                    "language": "en",
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

    def test_model_serialization_roundtrip(self):
        dq = DorkQuery(
            raw="site:test.com filetype:pdf",
            operators={
                DorkOperator.SITE: ["test.com"],
                DorkOperator.FILETYPE: ["pdf"],
            },
            target="google",
            description="Find PDFs on test.com",
        )
        schema = DorkSchema(dork_queries=[dq])
        dumped = schema.model_dump()
        errors = validate_dork(dumped)
        assert errors == []

    def test_dork_schema_json_file(self):
        """The DORK_SCHEMA.json file must match the in-code schema."""
        path = Path(__file__).parent.parent / "DORK_SCHEMA.json"
        assert path.exists(), "DORK_SCHEMA.json missing"
        with open(path) as f:
            file_schema = json.load(f)
        assert file_schema["title"] == DORK_SCHEMA["title"]
        assert file_schema["properties"].keys() == DORK_SCHEMA["properties"].keys()
