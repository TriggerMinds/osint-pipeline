from __future__ import annotations

from typing import Any

from ..models.evidence import EvidenceCollection


class GraphRAGAdapter:
    def __init__(self) -> None:
        self._available = self._check()

    def _check(self) -> bool:
        try:
            import graphrag  # noqa: F401
            return True
        except ImportError:
            return False

    @property
    def available(self) -> bool:
        return self._available

    async def build(self, evidence: EvidenceCollection) -> dict[str, Any]:
        if not self._available:
            return {"error": "GraphRAG not installed", "entities": [], "relations": []}

        # Stub — GraphRAG integration placeholder
        return {
            "entities": [],
            "relations": [],
            "source_count": len(evidence.items),
            "claim_count": sum(len(e.claims) for e in evidence.items),
        }
