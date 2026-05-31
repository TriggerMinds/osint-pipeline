from __future__ import annotations

from typing import Any

from ..utils.schema_gen import generate_dork_schema

# Generated from Pydantic models — do not edit manually.
# To regenerate: python -c "from osint_pipeline.utils.schema_gen import write_dork_schema; write_dork_schema('DORK_SCHEMA.json')"  # noqa: E501
DORK_SCHEMA: dict[str, Any] = generate_dork_schema()


def validate_dork(instance: dict[str, Any]) -> list[str]:
    import jsonschema

    errors: list[str] = []
    try:
        jsonschema.validate(instance=instance, schema=DORK_SCHEMA)
    except jsonschema.ValidationError as e:
        errors.append(e.message)
    return errors
