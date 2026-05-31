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

Valid operators: site, intitle, inurl, intext, filetype, inanchor, before, after, allintitle, allinurl, allintext, source, cache, link, related, numrange
Valid targets: google, bing, duckduckgo, yandex, searxng, archive_cdx, gdelt, commoncrawl, openalex, github, reddit, wikidata
Risk levels: safe, low, medium, high

Generate 5-10 dorks covering:
1. Document types (pdf, xls, doc, csv)
2. Specific sites/domains
3. Admin/login pages
4. Exposed directories/databases
5. Cached/archived content
6. News articles via gdelt
7. Social media
8. Academic publications via openalex
9. Code repositories via github
10. Entity data via wikidata

Use diverse targets. Generate at least 2-3 dorks with target set to news-specific
sources like gdelt, and 1-2 for openalex."""



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
        warnings: list[str] = []

        parse_result = parse_llm_json(raw)
        if not parse_result.success:
            raise DorkGeneratorError(
                f"LLM returned invalid JSON: {parse_result.error}"
            )

        if parse_result.repaired:
            warnings.append(
                "LLM output was malformed JSON and required repair"
            )

        data = parse_result.data
        raw_dorks = data.get("dork_queries", [])

        if not raw_dorks:
            raise DorkGeneratorError(
                "LLM returned empty dork_queries array"
            )

        dorks: list[DorkQuery] = []
        errors: list[str] = []

        for i, d in enumerate(raw_dorks):
            idx = f"dork_queries[{i}]"

            # raw — must be present and non-empty
            raw_val = d.get("raw")
            if not raw_val or not isinstance(raw_val, str) or not raw_val.strip():
                errors.append(f"{idx}.raw: missing or empty")
                continue

            # operators — each key must be a valid DorkOperator
            ops: dict[DorkOperator, list[str]] = {}
            raw_ops = d.get("operators", {})
            if not isinstance(raw_ops, dict):
                errors.append(f"{idx}.operators: expected object, got {type(raw_ops).__name__}")
                continue
            for k, v in raw_ops.items():
                try:
                    op = DorkOperator(k)
                except ValueError:
                    warnings.append(
                        f"{idx}.operators: unknown operator '{k}' — skipped"
                    )
                    continue
                ops[op] = v if isinstance(v, list) else [v]

            # target — must be a valid DorkTarget
            target_raw = d.get("target")
            if not target_raw:
                errors.append(f"{idx}.target: missing")
                continue
            try:
                target = DorkTarget(target_raw)
            except ValueError:
                errors.append(
                    f"{idx}.target: unknown target '{target_raw}'. "
                    f"Valid: {[t.value for t in DorkTarget]}"
                )
                continue

            # risk_level — must be a valid RiskLevel
            risk_raw = d.get("risk_level")
            if not risk_raw:
                errors.append(f"{idx}.risk_level: missing")
                continue
            try:
                risk = RiskLevel(risk_raw)
            except ValueError:
                errors.append(
                    f"{idx}.risk_level: unknown risk_level '{risk_raw}'. "
                    f"Valid: {[r.value for r in RiskLevel]}"
                )
                continue

            dorks.append(
                DorkQuery(
                    raw=raw_val.strip(),
                    operators=ops,
                    target=target,
                    description=d.get("description", ""),
                    language=d.get("language", ""),
                    purpose=d.get("purpose", ""),
                    expected_signal=d.get("expected_signal", ""),
                    risk_level=risk,
                )
            )

        if errors:
            warnings.extend(
                f"Dork generation produced {len(errors)} invalid item(s):\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

        if not dorks:
            warnings.append("No valid dork queries were generated by LLM")

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
            validation_warnings=warnings,
            dork_queries=dorks,
        )

        final = validate_llm_output(DorkSchema, schema.model_dump())
        if not final.success:
            raise DorkGeneratorError(
                f"Generated dork schema failed Pydantic validation: {final.error}"
            )

        return schema
