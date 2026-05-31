from __future__ import annotations

from ..config import get_settings
from ..models.query import MultilingualQuery
from ..utils.validation import parse_llm_json, validate_llm_output

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


class TranslatorError(Exception):
    pass


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

            parse_result = parse_llm_json(raw)
            if not parse_result.success:
                raise TranslatorError(
                    f"LLM returned invalid JSON for language '{lang}': {parse_result.error}"
                )

            data = parse_result.data

            translated = data.get("translated")
            if not translated or not isinstance(translated, str) or not translated.strip():
                raise TranslatorError(
                    f"LLM missing or empty 'translated' field for language '{lang}'"
                )

            mq = MultilingualQuery(
                original=query,
                target_language=lang,
                translated=translated,
                transliteration=data.get("transliteration"),
            )
            val = validate_llm_output(MultilingualQuery, mq.model_dump())
            if not val.success:
                raise TranslatorError(
                    f"Pydantic validation failed for language '{lang}': {val.error}"
                )

            results.append(mq)

        return results
