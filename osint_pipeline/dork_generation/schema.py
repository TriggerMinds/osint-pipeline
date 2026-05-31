from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models.dork import DorkOperator, DorkSchema

DORK_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "OSINT Dork Query Schema",
    "description": "Schema-constrained dork queries for OSINT search engine enumeration",
    "type": "object",
    "required": ["schema_version", "dork_queries"],
    "properties": {
        "schema_version": {"type": "string", "pattern": "^\\d+\\.\\d+$"},
        "description": {"type": "string"},
        "dork_queries": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["raw", "operators", "target"],
                "properties": {
                    "raw": {"type": "string", "minLength": 1},
                    "operators": {
                        "type": "object",
                        "patternProperties": {
                            "^(site|intitle|inurl|intext|filetype|inanchor|before|after|allintitle|allinurl|allintext|source|numrange)$": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 1,
                            }
                        },
                        "additionalProperties": False,
                        "minProperties": 1,
                    },
                    "target": {
                        "type": "string",
                        "enum": ["google", "bing", "duckduckgo", "yandex", "shodan", "censys"],
                    },
                    "description": {"type": "string"},
                    "language": {"type": "string"},
                },
            },
        },
    },
}


def validate_dork(instance: dict[str, Any]) -> list[str]:
    import jsonschema
    errors: list[str] = []
    try:
        jsonschema.validate(instance=instance, schema=DORK_SCHEMA)
    except jsonschema.ValidationError as e:
        errors.append(e.message)
    return errors
