from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ConflictMarker(str, Enum):
    CONSISTENT = "consistent"
    CONFLICTING = "conflicting"
    UNCERTAIN = "uncertain"
    ARCHIVE_ONLY = "archive_only"
    DISAPPEARED = "disappeared"


class EvidenceClaim(BaseModel):
    claim: str = Field(min_length=1)
    supporting_urls: list[str] = Field(default_factory=list)
    contradicting_urls: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    conflict_status: ConflictMarker = ConflictMarker.UNCERTAIN
    language: str = "en"
    category: Optional[str] = None


class Evidence(BaseModel):
    source_url: str
    snapshot_date: Optional[str] = None
    language: str
    source_type: str
    discovered_by_query: str
    claims: list[EvidenceClaim] = Field(default_factory=list)
    raw_snippet: Optional[str] = None
    archive_url: Optional[str] = None
    confidence_score: float = Field(ge=0, le=1, default=0.5)


class EvidenceCollection(BaseModel):
    query: str
    items: list[Evidence] = Field(default_factory=list)
