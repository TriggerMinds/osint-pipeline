from __future__ import annotations

import json

from ..config import get_settings
from ..models.query import ExpandedQuery

EXPANSION_PROMPT = """You are a query expansion specialist for OSINT research.

Given a user query, generate search query variants in multiple languages and covering different angles.

Output valid JSON with this exact schema:
{
  "expansions": [
    {
      "language": "en",
      "variants": ["query variant 1", "query variant 2"],
      "rationale": "why these variants"
    }
  ]
}

Languages to include: nl, en, de, fr (at minimum).
Generate 3-5 variants per language.
Use synonyms, entity-focused, temporal, relationship, and document-type angles."""  # noqa: E501


class QueryExpander:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def expand(self, query: str) -> list[ExpandedQuery]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=self.settings.deepseek_api_key,
            base_url=self.settings.deepseek_base_url,
        )

        resp = await client.chat.completions.create(
            model=self.settings.deepseek_model,
            messages=[
                {"role": "system", "content": EXPANSION_PROMPT},
                {"role": "user", "content": f"Expand this query for OSINT research: {query}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)

        results: list[ExpandedQuery] = []
        for exp in data.get("expansions", []):
            results.append(
                ExpandedQuery(
                    original=query,
                    variants=exp.get("variants", []),
                    language=exp.get("language", "en"),
                    rationale=exp.get("rationale", ""),
                )
            )

        return results
