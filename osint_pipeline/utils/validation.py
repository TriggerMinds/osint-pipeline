from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

M = TypeVar("M", bound=BaseModel)


@dataclass
class ParseResult:
    success: bool
    data: Any = None
    model: BaseModel | None = None
    error: str = ""
    repaired: bool = False


def parse_llm_json(raw: str) -> ParseResult:
    if not raw or not raw.strip():
        return ParseResult(success=False, error="Empty LLM response")

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        return ParseResult(success=True, data=data)
    except json.JSONDecodeError:
        pass

    # One repair attempt: find first { ... } or [ ... ] block
    repaired = _repair_json(cleaned)
    if repaired is not None:
        try:
            data = json.loads(repaired)
            return ParseResult(success=True, data=data, repaired=True)
        except json.JSONDecodeError:
            pass

    return ParseResult(
        success=False,
        error=f"Invalid JSON after repair attempt. Raw preview: {raw[:300]}",
    )


def validate_llm_output(model_class: type[M], data: Any) -> ParseResult:
    if isinstance(data, dict):
        try:
            instance = model_class(**data)
            return ParseResult(success=True, data=data, model=instance)
        except ValidationError as e:
            return ParseResult(
                success=False,
                data=data,
                error=f"Pydantic validation failed: {e}",
            )
    return ParseResult(
        success=False,
        data=data,
        error=f"Expected dict, got {type(data).__name__}",
    )


def _repair_json(text: str) -> str | None:
    brace_depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if brace_depth == 0:
                start = i
            brace_depth += 1
        elif ch == "}":
            brace_depth -= 1
            if brace_depth == 0 and start >= 0:
                return text[start : i + 1]
    return None
