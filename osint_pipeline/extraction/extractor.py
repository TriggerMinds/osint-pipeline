from __future__ import annotations

from ..config import get_settings
from ..models.evidence import Evidence, EvidenceClaim, ConflictMarker, EvidenceCollection
from ..models.source import SourceResult
from ..utils.validation import parse_llm_json, validate_llm_output

EXTRACT_PROMPT = """You are an evidence extraction specialist for OSINT.

Extract factual claims from the provided content. Output valid JSON:
{
  "claims": [
    {
      "claim": "The extracted factual statement",
      "confidence": 0.85,
      "category": "event|person|location|document|relation|other"
    }
  ]
}

Rules:
- Only extract claims explicitly supported by the text.
- Do NOT infer or hallucinate.
- Confidence: 0.3-0.5 vague, 0.5-0.8 clear, 0.8-1.0 explicit + specific.
- Empty claims list if content is meaningless."""  # noqa: E501


class EvidenceExtractorError(Exception):
    pass


class EvidenceExtractor:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def extract(
        self, sources: list[SourceResult], query: str = "",
    ) -> EvidenceCollection:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=self.settings.deepseek_api_key,
            base_url=self.settings.deepseek_base_url,
        )

        collection = EvidenceCollection(query=query)

        for src in sources:
            text = (src.content or "")[:8000]
            if not text:
                continue

            resp = await client.chat.completions.create(
                model=self.settings.deepseek_model,
                messages=[
                    {"role": "system", "content": EXTRACT_PROMPT},
                    {
                        "role": "user",
                        "content": f"URL: {src.metadata.url}\nContent:\n{text}",
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )

            raw = resp.choices[0].message.content or "{}"

            parse_result = parse_llm_json(raw)
            if not parse_result.success:
                raise EvidenceExtractorError(
                    f"LLM returned invalid JSON for {src.metadata.url}: {parse_result.error}"
                )

            data = parse_result.data
            raw_claims = data.get("claims")
            if not isinstance(raw_claims, list):
                raw_claims = []

            claims: list[EvidenceClaim] = []
            errors: list[str] = []

            for i, c in enumerate(raw_claims):
                idx = f"claims[{i}]"

                claim_text = c.get("claim")
                if not claim_text or not isinstance(claim_text, str) or not claim_text.strip():
                    errors.append(f"{idx}.claim: missing or empty")
                    continue

                confidence = c.get("confidence")
                if confidence is None or not isinstance(confidence, (int, float)):
                    errors.append(f"{idx}.confidence: missing or invalid")
                    continue

                ec = EvidenceClaim(
                    claim=claim_text,
                    supporting_urls=[src.metadata.url],
                    confidence=confidence,
                    category=c.get("category"),
                    language=src.metadata.language,
                )
                val = validate_llm_output(EvidenceClaim, ec.model_dump())
                if not val.success:
                    errors.append(f"{idx}: Pydantic validation failed: {val.error}")
                    continue

                claims.append(ec)

            if errors:
                raise EvidenceExtractorError(
                    f"Evidence extraction for {src.metadata.url} produced {len(errors)} "
                    f"invalid claim(s):\n" + "\n".join(f"  - {e}" for e in errors)
                )

            evidence = Evidence(
                source_url=src.metadata.url,
                snapshot_date=src.metadata.snapshot_date,
                language=src.metadata.language,
                source_type=src.metadata.source_type.value,
                discovered_by_query=src.metadata.discovered_by_query,
                claims=claims,
                raw_snippet=text[:500],
                archive_url=src.metadata.archive_url,
            )
            collection.items.append(evidence)

        self._detect_conflicts(collection)
        return collection

    def _detect_conflicts(self, collection: EvidenceCollection) -> None:
        groups: dict[str, list[EvidenceClaim]] = {}
        for ev in collection.items:
            for claim in ev.claims:
                key = claim.claim.lower().strip()[:120]
                groups.setdefault(key, []).append(claim)

        for key, claims in groups.items():
            if len(claims) < 2:
                continue
            confs = [c.confidence for c in claims]
            max_diff = max(confs) - min(confs)
            status = ConflictMarker.CONFLICTING if max_diff > 0.4 else ConflictMarker.CONSISTENT
            for c in claims:
                c.conflict_status = status
