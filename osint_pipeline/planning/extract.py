from __future__ import annotations

import re
from typing import Optional

from .models import QuerySeed

URL_RE = re.compile(r"https?://[^\s,;)]+")
DOMAIN_RE = re.compile(r"(?:https?://)?(?:www\.)?([a-zA-Z0-9][a-zA-Z0-9.-]+\.(?!pdf|doc|docx|xls|xlsx|csv|zip|pptx|txt)[a-zA-Z]{2,})(?:[/:\s]|$)", re.IGNORECASE)
FILENAME_RE = re.compile(r"(\S+\.(?:pdf|doc|docx|xls|xlsx|csv|zip|pptx|txt))", re.IGNORECASE)
QUOTED_RE = re.compile(r""""([^"]+)"|'([^']+)'""")
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
DATERANGE_RE = re.compile(r"(\d{4})\s*[-–]\s*(\d{4})")

LANGUAGE_HINTS: dict[str, str] = {
    "nl": r"\b(dat|het|een|voor|niet|zijn|ook|naar|zou|deze)\b",
    "en": r"\b(the|and|that|have|this|with|from|which|their|about)\b",
    "de": r"\b(der|die|und|das|nicht|sich|auch|werden|auf|eine)\b",
    "fr": r"\b(les|des|dans|une|pour|sur|avec|elle|nous|leur)\b",
}


def extract_query_seed(query: str) -> QuerySeed:
    urls = list(set(URL_RE.findall(query)))
    domains = list(set(m[0].strip() for m in DOMAIN_RE.finditer(query) if m[0]))
    filenames = list(set(FILENAME_RE.findall(query)))
    quoted = list(set(
        m.group(1) or m.group(2) for m in QUOTED_RE.finditer(query) if m.group(1) or m.group(2)
    ))
    years = list(set(YEAR_RE.findall(query)))
    date_ranges_raw = DATERANGE_RE.findall(query)
    date_range: Optional[dict] = None
    if date_ranges_raw:
        date_range = {"start": date_ranges_raw[0][0], "end": date_ranges_raw[0][1]}
    elif years:
        date_range = {"start": min(years), "end": max(years)}

    languages_hint = []
    for lang, pattern in LANGUAGE_HINTS.items():
        if re.search(pattern, query, re.IGNORECASE):
            languages_hint.append(lang)
    if not languages_hint:
        languages_hint = ["nl", "en"]

    entities = []
    if not urls and not filenames:
        words = query.split()
        entities = [w for w in words if len(w) > 4 and w[0].isupper()]

    return QuerySeed(
        raw_query=query,
        entities=entities,
        domains=domains,
        urls=urls,
        filenames=filenames,
        quoted_phrases=quoted,
        languages_hint=languages_hint,
        date_range=date_range,
    )
