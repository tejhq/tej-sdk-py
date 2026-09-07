from __future__ import annotations


class TejError(Exception):
    """Base exception for all tej SDK errors."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.request_id = request_id

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        if self.error_code:
            parts.append(f"error={self.error_code}")
        if self.request_id:
            parts.append(f"request_id={self.request_id}")
        return " ".join(parts)


class BadRequestError(TejError):
    """400: invalid path or query parameter."""


class NotFoundError(TejError):
    """404: resource not found."""


class AuthError(TejError):
    """HTTP 401: no API key was sent where one is required, or the key is
    malformed, unknown, or revoked. ``error_code`` is ``key_required`` or
    ``invalid_key``. Get a free key at https://tejhq.dev/keys."""


class ProRequiredError(TejError):
    """402: endpoint is part of the Pro tier."""


class RateLimitError(TejError):
    """429: client exceeded rate limit."""


class ServerError(TejError):
    """5xx: upstream failure."""


class NetworkError(TejError):
    """Transport-level failure (DNS, connection, timeout, TLS)."""


def from_status(status: int, message: str, **kwargs: object) -> TejError:
    cls: type[TejError]
    if status == 400:
        cls = BadRequestError
    elif status == 401:
        cls = AuthError
    elif status == 402:
        cls = ProRequiredError
    elif status == 404:
        cls = NotFoundError
    elif status == 429:
        cls = RateLimitError
    elif 500 <= status < 600:
        cls = ServerError
    else:
        cls = TejError
    return cls(message, status_code=status, **kwargs)  # type: ignore[arg-type]
