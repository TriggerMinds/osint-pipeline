from __future__ import annotations


class ConnectorError(Exception):
    """Base error for all connector failures."""
    def __init__(self, message: str, *, original: Exception | None = None) -> None:
        self.original = original
        super().__init__(message)


class ConnectorTimeoutError(ConnectorError):
    """Request timed out."""
    def __init__(self, message: str = "request timed out", *, original: Exception | None = None) -> None:
        super().__init__(message, original=original)


class ConnectorHTTPStatusError(ConnectorError):
    """Non-retryable HTTP status returned."""
    def __init__(self, status: int, url: str, *, original: Exception | None = None) -> None:
        self.status = status
        self.url = url
        super().__init__(f"HTTP {status}", original=original)


class ConnectorRetriesExhaustedError(ConnectorError):
    """Retryable status persisted across all retry attempts."""
    def __init__(self, status: int, url: str, retries: int, *, original: Exception | None = None) -> None:
        self.status = status
        self.url = url
        self.retries = retries
        super().__init__(
            f"HTTP {status} after {retries + 1} attempt(s)",
            original=original,
        )
