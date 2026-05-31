from .query import ExpandedQuery, MultilingualQuery
from .source import SourceMetadata, SourceResult, SourceType, FetchStatus
from .evidence import Evidence, EvidenceClaim, EvidenceCollection, ConflictMarker
from .dork import DorkQuery, DorkOperator, DorkSchema

__all__ = [
    "ExpandedQuery", "MultilingualQuery",
    "SourceMetadata", "SourceResult", "SourceType", "FetchStatus",
    "Evidence", "EvidenceClaim", "EvidenceCollection", "ConflictMarker",
    "DorkQuery", "DorkOperator", "DorkSchema",
]
