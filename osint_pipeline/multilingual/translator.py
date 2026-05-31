from __future__ import annotations

import json

from ..config import get_settings
from ..models.query import MultilingualQuery

TRANSLATION_PROMPT = """You are a multilingual search query translator for OSINT.

Translate the given search query into the target language, keeping proper nouns, technical terms, and search operators untranslated.

Output valid JSON:
{
  "translated": "translated query text",
  "transliteration": null
}

Set transliteration to a romanized version for non-Latin scripts, null otherwise."""  # noqa: E501

TARGET_LANGUAGES = [
    "nl", "en", "de", "fr", "ru", "zh", "ar", "es", "fa", "tr", "uk", "ja", "ko",
]


class MultilingualTranslator:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def translate(self, query: str, languages: list[str] | None = None) -> list[MultilingualQuery]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=self.settings.deepseek_api_key,
            base_url=self.settings.deepseek_base_url,
        )

        targets = languages or TARGET_LANGUAGES
        results: list[MultilingualQuery] = []

        for lang in targets:
            if lang == "en":
                results.append(MultilingualQuery(original=query, target_language="en", translated=query))
                continue

            resp = await client.chat.completions.create(
                model=self.settings.deepseek_model,
                messages=[
                    {"role": "system", "content": TRANSLATION_PROMPT},
                    {
                        "role": "user",
                        "content": f"Source language: en\nTarget language: {lang}\nQuery: {query}",
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )

            raw = resp.choices[0].message.content or "{}"
            data = json.loads(raw)

            results.append(
                MultilingualQuery(
                    original=query,
                    target_language=lang,
                    translated=data.get("translated", query),
                    transliteration=data.get("transliteration"),
                )
            )

        return results
