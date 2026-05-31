from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models.dork import DorkSchema


def _inline_refs(schema: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    """Resolve $ref references inline so the schema is self-contained."""
    if isinstance(schema, dict):
        if "$ref" in schema:
            ref_path = schema["$ref"]
            key = ref_path.split("/")[-1]
            resolved = defs.get(key, {})
            return _inline_refs(resolved, defs)
        return {k: _inline_refs(v, defs) for k, v in schema.items()}
    if isinstance(schema, list):
        return [_inline_refs(item, defs) for item in schema]
    return schema


def generate_dork_schema() -> dict[str, Any]:
    raw = DorkSchema.model_json_schema()
    defs = raw.pop("$defs", {})

    schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "OSINT Dork Query Schema",
        "description": (
            "Schema-constrained dork queries for OSINT search engine enumeration. "
            "Generated from Pydantic models — do not edit manually."
        ),
        "type": "object",
        "required": ["dork_queries"],
        "properties": {},
    }

    # Resolve each property inline
    for prop_name, prop_schema in raw.get("properties", {}).items():
        schema["properties"][prop_name] = _inline_refs(prop_schema, defs)

    # Add required from root
    if "required" in raw:
        schema["required"] = raw["required"]

    # Add enum constraint to operators propertyNames
    op_def = defs.get("DorkOperator", {})
    op_values = op_def.get("enum", [])
    dork_query_props = schema["properties"].get("dork_queries", {}).get("items", {}).get("properties", {})
    if "operators" in dork_query_props:
        dork_query_props["operators"]["propertyNames"] = {"enum": op_values}

    return schema


def write_dork_schema(path: str | Path | None = None) -> dict[str, Any]:
    schema = generate_dork_schema()
    if path:
        dest = Path(path)
        dest.write_text(
            json.dumps(schema, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return schema
