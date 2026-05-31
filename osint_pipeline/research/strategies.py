from __future__ import annotations

_ARCHIVE_SUFFIXES = [
    "site:archive.org",
    "site:archive.ph",
    "site:archive.is",
    "site:web.archive.org",
    "cache:",
    "site:ghostarchive.org",
    "source:news",
]

SEARXNG_STRATEGIES: dict[str, tuple[str, ...]] = {
    "default": (),
    "file_discovery": ("brave", "mojeek", "bing"),
    "multi_engine": ("brave", "mojeek", "yandex", "bing", "duckduckgo"),
    "regional_diverse": ("yandex", "baidu", "mojeek", "brave", "bing"),
}

PROFILE_SEARXNG: dict[str, dict] = {
    "smoke": {"strategy": "default", "engines": ()},
    "archive_first": {"strategy": "file_discovery", "engines": ("brave", "mojeek", "bing")},
    "deleted_content": {"strategy": "file_discovery", "engines": ("brave", "mojeek", "bing", "yandex")},
    "multi_engine": {"strategy": "multi_engine", "engines": ("brave", "mojeek", "yandex", "bing", "duckduckgo")},
    "foreign_index": {"strategy": "regional_diverse", "engines": ("yandex", "baidu", "mojeek", "brave", "bing")},
    "deep_archive": {"strategy": "file_discovery", "engines": ("brave", "mojeek", "bing")},
}


def build_discovery_strategy(
    profile_name: str | None,
    searxng_strategy: str = "default",
    searxng_engines: tuple[str, ...] = (),
    connectors_used: list[str] | None = None,
) -> dict:
    strategy: dict = {
        "profile": profile_name or "default",
        "searxng_strategy": searxng_strategy,
        "engines_requested": list(searxng_engines),
        "engines_used": [],
        "connectors_used": sorted(connectors_used or []),
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
