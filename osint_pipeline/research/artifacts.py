from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from ..models.evidence import EvidenceCollection
from ..models.lineage import QueryLineage
from ..graphrag import EvidenceGraph
from .sanitize import sanitize_error_message


class TimingBreakdown(BaseModel):
    expand: float = 0.0
    dork: float = 0.0
    fetch: float = 0.0
    crawl: float = 0.0
    extract: float = 0.0
    rank: float = 0.0

    @property
    def total(self) -> float:
        return self.expand + self.dork + self.fetch + self.crawl + self.extract + self.rank


class ConnectorExecutionResult(BaseModel):
    connector: str
    query: str
    sources_found: int = 0
    error: Optional[str] = None


class GraphSummary(BaseModel):
    nodes: int = 0
    edges: int = 0


class ResearchArtifact(BaseModel):
    run_id: str = ""
    query: str = ""
    status: str = "in_progress"
    timing: TimingBreakdown = Field(default_factory=TimingBreakdown)
    expansions: list = Field(default_factory=list)
    dorks: list = Field(default_factory=list)
    routes: int = 0
    connector_results: list[ConnectorExecutionResult] = Field(default_factory=list)
    sources_fetched: int = 0
    claims_extracted: int = 0
    errors: list[str] = Field(default_factory=list)
    lineages: list = Field(default_factory=list)
    evidence: Optional[dict] = None
    graph: Optional[GraphSummary] = None
    quality_controls: Optional[dict] = None

    def add_error(self, msg: str) -> None:
        self.errors.append(sanitize_error_message(msg))

    def model_dump_safe(self) -> dict:
        self.errors = [sanitize_error_message(e) for e in self.errors]
        for cr in self.connector_results:
            cr.query = sanitize_error_message(cr.query)
            if cr.error:
                cr.error = sanitize_error_message(cr.error)
        d = self.model_dump(exclude_none=True)
        return d
