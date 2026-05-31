from __future__ import annotations

import json
from typing import Any

from ..config import get_settings
from ..models.dork import DorkOperator, DorkQuery, DorkSchema
from ..models.query import ExpandedQuery

DORK_SYSTEM_PROMPT = """You are a search engine dork specialist for OSINT.

Generate precise search dork queries. Output ONLY valid JSON matching this schema:
{
  "dork_queries": [
    {
      "raw": "site:example.com intitle:secret filetype:pdf",
      "operators": {"site": ["example.com"], "intitle": ["secret"], "filetype": ["pdf"]},
      "target": "google",
      "description": "Find PDFs with 'secret' in title on example.com",
      "language": "en"
    }
  ]
}

Valid operators: site, intitle, inurl, intext, filetype, inanchor, before, after, allintitle, allinurl, allintext, source, numrange
Valid targets: google, bing, duckduckgo, yandex, shodan, censys

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

        client = AsyncOpenAI(
            api_key=self.settings.deepseek_api_key,
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
        data = json.loads(raw)

        dorks: list[DorkQuery] = []
        for d in data.get("dork_queries", []):
            ops: dict[DorkOperator, list[str]] = {}
            for k, v in d.get("operators", {}).items():
                try:
                    ops[DorkOperator(k)] = v if isinstance(v, list) else [v]
                except ValueError:
                    pass
            dorks.append(
                DorkQuery(
                    raw=d.get("raw", ""),
                    operators=ops,
                    target=d.get("target", "google"),
                    description=d.get("description", ""),
                    language=d.get("language", "en"),
                )
            )

        return DorkSchema(
            description=f"Dork queries for: {query}",
            dork_queries=dorks,
        )
