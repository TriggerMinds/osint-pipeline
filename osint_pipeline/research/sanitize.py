from __future__ import annotations

import re

_SENSITIVE_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Proxy URLs with credentials: socks5://user:pass@host:port
    (re.compile(r"(socks5|socks4|http|https)://[^@\s]+@", re.IGNORECASE),
     r"\1://***:***@"),
    # Authorization: Bearer <token>
    (re.compile(r"(Authorization\s*:\s*Bearer\s+)\S+", re.IGNORECASE),
     r"\1***"),
    # api_key= in query strings
    (re.compile(r"(api_key|apiKey|apikey)=[^&\s]+", re.IGNORECASE),
     r"\1=***"),
    # key= in query strings
    (re.compile(r"(&?key)=[^&\s]+", re.IGNORECASE),
     r"\1=***"),
    # token= in query strings
    (re.compile(r"(token|access_token|auth_token)=[^&\s]+", re.IGNORECASE),
     r"\1=***"),
    # GitHub token pattern
    (re.compile(r"(gh[ps]_[a-zA-Z0-9]{10,})"),
     "***"),
    # DeepSeek / OpenAI key pattern
    (re.compile(r"(sk-[a-zA-Z0-9_-]{10,})"),
     "***"),
    # Secret key pattern
    (re.compile(r"(secret|client_secret|client-id|client_id)=[^&\s]+"),
     r"\1=***"),
]


def sanitize_error_message(text: str) -> str:
    if not text:
        return text
    result = text
    for pattern, replacement in _SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result
