from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GraphEntity(BaseModel):
    id: str
    name: str
    type: str = "unknown"
    aliases: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    source_urls: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, default=0.5)


class GraphRelation(BaseModel):
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    attributes: Dict[str, Any] = Field(default_factory=dict)
    source_urls: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, default=0.5)
    temporal_context: Optional[str] = None


class KnowledgeGraph(BaseModel):
    entities: Dict[str, GraphEntity] = Field(default_factory=dict)
    relations: List[GraphRelation] = Field(default_factory=list)
    query: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
