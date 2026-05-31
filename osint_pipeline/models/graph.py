from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class GraphEntity(BaseModel):
    id: str
    name: str
    type: str = "unknown"
    source_urls: list[str] = Field(default_factory=list)
    confidence: float = 1.0


class GraphRelation(BaseModel):
    source_entity_id: str
    target_entity_id: str
    relation_type: str = "related_to"
    confidence: float = 1.0


class KnowledgeGraph(BaseModel):
    query: str = ""
    entities: dict[str, GraphEntity] = Field(default_factory=dict)
    relations: list[GraphRelation] = Field(default_factory=list)
