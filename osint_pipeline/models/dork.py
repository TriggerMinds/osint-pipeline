from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class DorkOperator(str, Enum):
    SITE = "site"
    INTITLE = "intitle"
    INURL = "inurl"
    INTEXT = "intext"
    FILETYPE = "filetype"
    INANCHOR = "inanchor"
    BEFORE = "before"
    AFTER = "after"
    ALLINTITLE = "allintitle"
    ALLINURL = "allinurl"
    ALLINTEXT = "allintext"
    SOURCE = "source"
    NUMRANGE = "numrange"


class DorkQuery(BaseModel):
    raw: str
    operators: dict[DorkOperator, list[str]] = Field(default_factory=dict)
    target: str = "google"
    description: str = ""
    language: str = "en"


class DorkSchema(BaseModel):
    schema_version: str = "1.0"
    description: str = ""
    dork_queries: list[DorkQuery] = Field(default_factory=list)
