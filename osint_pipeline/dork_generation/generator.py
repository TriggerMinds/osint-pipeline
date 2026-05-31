from __future__ import annotations

import json

from ..config import get_settings
from ..models.dork import DorkOperator, DorkQuery, DorkSchema, DorkTarget, RiskLevel, ExpandedIntent
from ..models.query import ExpandedQuery
from ..utils.validation import parse_llm_json, validate_llm_output


class DorkGeneratorError(Exception):
    pass


DORK_SYSTEM_PROMPT = """You are a search engine dork specialist for OSINT.

Generate precise search dork queries. Output ONLY valid JSON matching this schema:
{
  "intent": "brief description of the research intent",
  "entities": ["entity1", "entity2"],
  "languages": ["nl", "en", "de", "fr"],
  "negative_terms": ["term_to_exclude"],
  "validation_rules": {"key": "rule description"},
  "dork_queries": [
    {
      "raw": "site:example.com intitle:secret filetype:pdf",
      "operators": {"site": ["example.com"], "intitle": ["secret"], "filetype": ["pdf"]},
      "target": "google",
      "description": "Find PDFs with 'secret' in title on example.com",
      "language": "en",
      "purpose": "Find sensitive documents",
      "expected_signal": "PDF files matching the query pattern",
      "risk_level": "medium"
    }
  ]
}

Valid operators: site, intitle, inurl, intext, filetype, inanchor, before, after, allintitle, allinurl, allintext, source, numrange
Valid targets: google, bing, duckduckgo, yandex, searxng, archive_cdx, gdelt, commoncrawl, openalex, github, reddit, wikidata
Risk levels: safe, low, medium, high

Generate 5-10 dorks covering:
1. Document types (pdf, xls, doc, csv)
2. Specific sites/domains
3. Admin/login pages
4. Exposed directories/databases
5. Cached/archived content
6. News articles
7. Social media"""  # noqa: E501


class DorkGenerator:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def generate(
        self, query: str, expanded: list[ExpandedQuery] | None = None
    ) -> DorkSchema:
        from openai import AsyncOpenAI

        api_key = self.settings.deepseek_api_key
        if not api_key:
            raise DorkGeneratorError(
                "DeepSeek API key not configured. Set OSINT_DEEPSEEK_API_KEY in .env"
            )

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=self.settings.deepseek_base_url,
        )

        context = {
            "query": query,
            "expanded_variants": [v for e in (expanded or []) for v in e.variants],
        }

        resp = await client.chat.completions.create(
            model=self.settings.deepseek_model,
            messages=[
                {"role": "system", "content": DORK_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(context, indent=2)},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        raw = resp.choices[0].message.content or "{}"

        # Parse JSON with repair attempt
        parse_result = parse_llm_json(raw)
        if not parse_result.success:
            raise DorkGeneratorError(
                f"LLM returned invalid JSON: {parse_result.error}"
            )

        data = parse_result.data

        # Build DorkSchema
        dorks: list[DorkQuery] = []
        for d in data.get("dork_queries", []):
            ops: dict[DorkOperator, list[str]] = {}
            for k, v in d.get("operators", {}).items():
                try:
                    ops[DorkOperator(k)] = v if isinstance(v, list) else [v]
                except ValueError:
                    pass

            try:
                target = DorkTarget(d.get("target", "google"))
            except ValueError:
                target = DorkTarget.GOOGLE

            try:
                risk = RiskLevel(d.get("risk_level", "safe"))
            except ValueError:
                risk = RiskLevel.SAFE

            dorks.append(
                DorkQuery(
                    raw=d.get("raw", ""),
                    operators=ops,
                    target=target,
                    description=d.get("description", ""),
                    language=d.get("language", "en"),
                    purpose=d.get("purpose", ""),
                    expected_signal=d.get("expected_signal", ""),
                    risk_level=risk,
                )
            )

        schema = DorkSchema(
            description=f"Dork queries for: {query}",
            intent=ExpandedIntent(
                original_query=query,
                intent=data.get("intent", ""),
                entities=data.get("entities", []),
                languages=data.get("languages", ["nl", "en", "de", "fr"]),
            ),
            entities=data.get("entities", []),
            languages=data.get("languages", ["nl", "en", "de", "fr"]),
            negative_terms=data.get("negative_terms", []),
            validation_rules=data.get("validation_rules", {}),
            dork_queries=dorks,
        )

        # Final Pydantic validation
        final = validate_llm_output(DorkSchema, schema.model_dump())
        if not final.success:
            raise DorkGeneratorError(
                f"Generated dork schema failed validation: {final.error}"
            )

        return schema
