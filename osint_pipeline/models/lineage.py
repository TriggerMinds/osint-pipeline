from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class QueryLineage(BaseModel):
    """Tracks how a specific query was derived and routed."""
    id: str = ""
    original_query: str = ""
    expanded_query: str = ""
    language: str = "en"
    dork_raw: str = ""
    dork_target: str = ""
    connector: str = ""
    retrieved_url: str = ""
    archive_snapshot_date: Optional[str] = None


class ResearchRun(BaseModel):
    """Top-level container for one research execution."""
    id: str = ""
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    original_query: str = ""
    query_lineages: list[QueryLineage] = Field(default_factory=list)
    total_sources: int = 0
    status: str = "in_progress"
