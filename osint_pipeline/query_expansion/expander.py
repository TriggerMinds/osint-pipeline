from __future__ import annotations

from ..config import get_settings
from ..models.query import ExpandedQuery
from ..utils.validation import parse_llm_json, validate_llm_output

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


class QueryExpanderError(Exception):
    pass


class QueryExpander:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def expand(self, query: str) -> list[ExpandedQuery]:
        from openai import AsyncOpenAI

        api_key = self.settings.deepseek_api_key
        if not api_key:
            raise QueryExpanderError("DeepSeek API key not configured")

        client = AsyncOpenAI(
            api_key=api_key,
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

        parse_result = parse_llm_json(raw)
        if not parse_result.success:
            raise QueryExpanderError(
                f"LLM returned invalid JSON: {parse_result.error}"
            )

        data = parse_result.data

        results: list[ExpandedQuery] = []
        for exp in data.get("expansions", []):
            eq = ExpandedQuery(
                original=query,
                variants=exp.get("variants", []),
                language=exp.get("language", "en"),
                rationale=exp.get("rationale", ""),
            )
            val = validate_llm_output(ExpandedQuery, eq.model_dump())
            if not val.success:
                raise QueryExpanderError(
                    f"Validation failed for expansion: {val.error}"
                )
            results.append(eq)

        # Verify at minimum nl/en/de/fr
        langs_found = {r.language for r in results}
        required = {"nl", "en", "de", "fr"}
        missing = required - langs_found
        if missing:
            raise QueryExpanderError(
                f"Missing required language expansions: {missing}"
            )

        return results
