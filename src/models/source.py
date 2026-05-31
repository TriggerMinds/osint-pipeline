from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    SEARXNG = "searxng"
    GDELT = "gdelt"
    COMMON_CRAWL = "common_crawl"
    INTERNET_ARCHIVE = "internet_archive"
    WAYBACK = "wayback"
    WAYMORE = "waymore"
    CRAWL4AI = "crawl4ai"


class FetchStatus(str, Enum):
    PENDING = "pending"
    FETCHING = "fetching"
    SUCCESS = "success"
    NOT_FOUND = "not_found"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    ARCHIVE_ONLY = "archive_only"


class SourceMetadata(BaseModel):
    url: str
    timestamp: str
    snapshot_date: Optional[str] = None
    language: str = "unknown"
    source_type: SourceType
    query_used: str
    title: Optional[str] = None
    domain: Optional[str] = None
    status_code: Optional[int] = None
    content_length: Optional[int] = None
    fetch_status: FetchStatus = FetchStatus.PENDING


class SourceResult(BaseModel):
    source_metadata: SourceMetadata
    content_markdown: Optional[str] = None
    content_text: Optional[str] = None
    content_html: Optional[str] = None
    error_message: Optional[str] = None
    is_archive_snapshot: bool = False
    archive_url: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None
