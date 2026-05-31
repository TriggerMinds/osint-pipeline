from __future__ import annotations
from enum import Enum
from typing import List, Optional, Set
from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    FACTUAL = "factual"
    INVESTIGATIVE = "investigative"
    TEMPORAL = "temporal"
    COMPARATIVE = "comparative"
    VERIFICATION = "verification"
    RELATIONSHIP = "relationship"
    UNKNOWN = "unknown"


class IntentConfidence(BaseModel):
    type_confidence: float = Field(ge=0, le=1, default=0.5)
    entity_confidence: float = Field(ge=0, le=1, default=0.5)
    temporal_confidence: float = Field(ge=0, le=1, default=0.5)
    overall: float = Field(ge=0, le=1, default=0.5)


class UserIntent(BaseModel):
    original_query: str
    question_type: QuestionType = QuestionType.UNKNOWN
    primary_entities: List[str] = Field(default_factory=list)
    secondary_entities: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    timeframe_start: Optional[str] = None
    timeframe_end: Optional[str] = None
    preferred_languages: Set[str] = Field(default_factory=lambda: {"en"})
    target_sources: List[str] = Field(default_factory=list)
    dork_friendly: bool = False
    requires_archival: bool = False
    requires_multilingual: bool = False
    sub_questions: List[str] = Field(default_factory=list)
    confidence: IntentConfidence = Field(default_factory=IntentConfidence)
    raw_llm_output: Optional[str] = None
