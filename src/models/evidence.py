from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ConflictMarker(str, Enum):
    CONSISTENT = "consistent"
    CONFLICTING = "conflicting"
    UNCERTAIN = "uncertain"
    ARCHIVE_ONLY = "archive_only"
    DISAPPEARED = "disappeared"


class EvidenceClaim(BaseModel):
    claim_text: str
    supporting_sources: List[str] = Field(default_factory=list)
    contradicting_sources: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, default=0.5)
    conflict_status: ConflictMarker = ConflictMarker.UNCERTAIN
    language: str = "en"
    category: Optional[str] = None


class Evidence(BaseModel):
    source_url: str
    snapshot_date: Optional[str] = None
    language: str
    source_type: str
    query_used: str
    extracted_claims: List[EvidenceClaim] = Field(default_factory=list)
    raw_text_snippet: Optional[str] = None
    is_archive_only: bool = False
    is_disappeared: bool = False
    archive_url: Optional[str] = None
    confidence_score: float = Field(ge=0, le=1, default=0.5)


class EvidenceCollection(BaseModel):
    query: str
    evidence_list: List[Evidence] = Field(default_factory=list)
    conflicting_claims: List[EvidenceClaim] = Field(default_factory=list)
    archive_only_sources: List[str] = Field(default_factory=list)
    disappeared_sources: List[str] = Field(default_factory=list)
