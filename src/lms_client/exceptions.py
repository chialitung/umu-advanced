"""Custom exceptions for the LMS client SDK."""

from __future__ import annotations

from typing import Any


class LMSAPIError(Exception):
    """Base exception for all LMS API errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: Any = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body

    def __str__(self) -> str:
        parts = [self.args[0]]
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        return " ".join(parts)


class LMSAuthError(LMSAPIError):
    """Raised when authentication fails (401/403)."""

    pass


class LMSNotFoundError(LMSAPIError):
    """Raised when a requested resource is not found (404)."""

    pass


class LMSValidationError(LMSAPIError):
    """Raised when request parameters are invalid (400/422)."""

    pass


class LMSRateLimitError(LMSAPIError):
    """Raised when rate limit is exceeded (429)."""

    pass
