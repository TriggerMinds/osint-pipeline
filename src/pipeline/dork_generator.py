from __future__ import annotations
import json
from typing import Dict, List
from ..models.intent import UserIntent
from ..models.query import DorkQuery, DorkOperator, ExpandedQuery
from ..providers import LLMProvider, get_provider

DORK_SYSTEM_PROMPT = """You are a search dork specialist for OSINT. Generate precise search engine dork queries.

Output valid JSON with the following STRICT schema:
{
  "dork_queries": [
    {
      "raw_query": "site:example.com intitle:secret filetype:pdf",
      "operators": {"site": ["example.com"], "intitle": ["secret"], "filetype": ["pdf"]},
      "target_source": "google",
      "description": "Find PDF documents containing 'secret' on example.com",
      "language": "en"
    }
  ]
}

Valid operators: site, intitle, inurl, intext, filetype, inanchor, link, related, cache, numrange, before, after, allintitle, allinurl, allintext, source

Target sources: google, bing, duckduckgo, yandex, shodan, censys

Generate diverse dorks targeting:
1. Document types (PDF, XLS, DOC, CSV, PPT)
2. Specific sites/domains
3. Admin panels, login pages
4. Exposed directories, databases
5. Cached/archived versions
6. News articles, press releases
7. Social media, forums

Output ONLY valid JSON, no markdown."""


class DorkGenerator:
    def __init__(self, provider_name: str = "deepseek") -> None:
        self.provider: LLMProvider = get_provider(provider_name)

    async def generate(
        self,
        intent: UserIntent,
        expanded_queries: List[ExpandedQuery],
    ) -> List[DorkQuery]:
        if not intent.dork_friendly:
            return []

        base_queries = []
        for eq in expanded_queries:
            base_queries.extend(eq.queries)

        context = {
            "query": intent.original_query,
            "entities": intent.primary_entities + intent.secondary_entities,
            "locations": intent.locations,
            "question_type": intent.question_type.value,
        }

        messages = [
            {"role": "system", "content": DORK_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(context, indent=2)},
        ]

        raw = await self.provider.chat(
            messages,
            response_format={"type": "json_object"},
            temperature=0.4,
        )

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}

        dorks = []
        for d in data.get("dork_queries", []):
            parsed_ops = {}
            for op_name, values in d.get("operators", {}).items():
                try:
                    op_enum = DorkOperator(op_name)
                    parsed_ops[op_enum] = values if isinstance(values, list) else [values]
                except ValueError:
                    pass

            dorks.append(DorkQuery(
                raw_query=d.get("raw_query", ""),
                operators=parsed_ops,
                target_source=d.get("target_source", "google"),
                description=d.get("description", ""),
                language=d.get("language", "en"),
            ))

        return dorks
