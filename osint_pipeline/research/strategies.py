from __future__ import annotations

import re

_ARCHIVE_SUFFIXES = [
    "site:archive.org",
    "site:archive.ph",
    "site:archive.is",
    "site:web.archive.org",
    "cache:",
    "site:ghostarchive.org",
    "source:news",
]


def build_discovery_strategy(
    profile_name: str | None,
    engines: list[str] | None = None,
) -> dict:
    strategy: dict = {
        "profile": profile_name or "default",
        "engines_requested": engines or [],
        "engines_used": [],
        "archive_sources": [],
        "deleted_content_query": False,
    }

    if profile_name == "deleted_content":
        strategy["deleted_content_query"] = True
        strategy["archive_sources"] = [
            "web.archive.org", "archive.ph", "archive.is",
            "commoncrawl", "ghostarchive.org",
        ]
    elif profile_name == "archive_first":
        strategy["archive_sources"] = ["web.archive.org", "archive.ph", "archive.is"]
    elif profile_name == "deep_archive":
        strategy["archive_sources"] = [
            "web.archive.org", "archive.ph", "archive.is",
            "commoncrawl",
        ]

    return strategy


def build_deleted_content_queries(query: str) -> list[str]:
    suffixes = []
    for s in _ARCHIVE_SUFFIXES:
        if s.startswith("site:") or s.startswith("source:"):
            suffixes.append(f"{query} {s}")
        elif s.startswith("cache:"):
            suffixes.append(f"{s}{query}")
        else:
            suffixes.append(f"{query} {s}")
    return suffixes


def mark_engines_used(strategy: dict, connector_results: list) -> None:
    engines = set()
    for cr in connector_results:
        engines.add(cr.connector)
    strategy["engines_used"] = sorted(engines)
