from __future__ import annotations
import json
from typing import List
from ..models.query import MultilingualQuery
from ..providers import LLMProvider, get_provider

TRANSLATION_PROMPT = """You are a multilingual search query translator for OSINT research. Translate the given search query into the target language.

Output valid JSON with:
- translated_query: the query in target language
- transliteration: romanized version if non-Latin script (null if not needed)

Keep search-specific terms, proper nouns, and technical terms untranslated. Preserve booleans, quotes, operators."""


DEFAULT_LANGUAGES = [
    "en", "ru", "zh", "ar", "es", "fr", "de", "fa", "tr", "uk", "pt", "ja", "ko",
]


class MultilingualQueryGenerator:
    def __init__(
        self,
        provider_name: str = "deepseek",
        target_languages: List[str] = None,
    ) -> None:
        self.provider: LLMProvider = get_provider(provider_name)
        self.target_languages = target_languages or DEFAULT_LANGUAGES

    async def generate(self, query: str, intent_languages: set = None) -> List[MultilingualQuery]:
        results = []
        languages = self.target_languages.copy()

        if intent_languages:
            for lang in intent_languages:
                if lang not in languages:
                    languages.append(lang)

        for lang in languages:
            if lang == "en":
                results.append(MultilingualQuery(
                    original_query=query,
                    language="en",
                    translated_query=query,
                ))
                continue

            messages = [
                {"role": "system", "content": TRANSLATION_PROMPT},
                {"role": "user", "content": (
                    f"Source language: en\n"
                    f"Target language: {lang}\n"
                    f"Query: {query}\n"
                    f"Translate this OSINT search query for maximum search effectiveness."
                )},
            ]

            raw = await self.provider.chat(
                messages,
                response_format={"type": "json_object"},
                temperature=0.1,
            )

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {}

            results.append(MultilingualQuery(
                original_query=query,
                language=lang,
                translated_query=data.get("translated_query", query),
                transliteration=data.get("transliteration"),
            ))

        return results
