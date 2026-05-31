from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    SEARXNG = "searxng"
    GDELT = "gdelt"
    COMMON_CRAWL = "common_crawl"
    INTERNET_ARCHIVE = "internet_archive"
    WAYBACK = "wayback"
    CRAWL4AI = "crawl4ai"


class FetchStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    NOT_FOUND = "not_found"
    ERROR = "error"
    ARCHIVE_ONLY = "archive_only"


class SourceMetadata(BaseModel):
    url: str
    source_type: SourceType
    language: str = "unknown"
    discovered_by_query: str = ""
    discovered_at: str = ""
    snapshot_date: Optional[str] = None
    title: Optional[str] = None
    domain: Optional[str] = None
    status_code: Optional[int] = None
    fetch_status: FetchStatus = FetchStatus.PENDING
    archive_url: Optional[str] = None


class SourceResult(BaseModel):
    metadata: SourceMetadata
    content: Optional[str] = None
    error: Optional[str] = None
