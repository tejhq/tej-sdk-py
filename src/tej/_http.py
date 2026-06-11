"""Stdlib HTTP transport shared by the sync and async clients.

Zero runtime deps. Sync uses ``urllib.request``. Async wraps sync calls in
``asyncio.to_thread`` so concurrent fetches via ``asyncio.gather`` still get
real parallelism without dragging in ``httpx``/``aiohttp``.
"""

from __future__ import annotations

import json
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Mapping, Optional, Tuple

from ._version import __version__
from .exceptions import NetworkError, ServerError, TejError, from_status

DEFAULT_BASE_URL = "https://api.tejhq.dev"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 0.4
DEFAULT_BACKOFF_CAP = 4.0
USER_AGENT = f"tej-sdk-py/{__version__}"

RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

_SYMBOL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-&]{0,29}$")
_EXCHANGE_VALUES = frozenset({"nse", "bse"})
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def normalize_exchange(value: str) -> str:
    """Lowercase + validate against `nse` | `bse`."""
    if not isinstance(value, str):
        raise ValueError(f"exchange must be str, got {type(value).__name__}")
    v = value.strip().lower()
    if v not in _EXCHANGE_VALUES:
        raise ValueError(f"exchange must be 'nse' or 'bse', got {value!r}")
    return v


def normalize_symbol(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"symbol must be str, got {type(value).__name__}")
    v = value.strip().upper()
    if not _SYMBOL_RE.match(v):
        raise ValueError(
            f"symbol must match [A-Z0-9][A-Z0-9-&]{{0,29}}, got {value!r}"
        )
    return v


def validate_date(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be str (YYYY-MM-DD), got {type(value).__name__}")
    if not _DATE_RE.match(value):
        raise ValueError(f"{field} must be YYYY-MM-DD, got {value!r}")
    return value


def build_url(base_url: str, path: str, query: Optional[Mapping[str, Any]] = None) -> str:
    url = base_url.rstrip("/") + "/" + path.lstrip("/")
    if query:
        items = [(k, str(v)) for k, v in query.items() if v is not None]
        if items:
            url = url + "?" + urllib.parse.urlencode(items)
    return url


def _backoff_sleep(attempt: int, base: float, cap: float) -> float:
    expo = min(cap, base * (2 ** attempt))
    jitter = random.uniform(0, expo / 2)
    return expo / 2 + jitter


def _parse_body(raw: bytes, status: int, request_id: Optional[str]) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        if 200 <= status < 300:
            raise TejError(
                f"failed to decode JSON response: {exc}",
                status_code=status,
                request_id=request_id,
            ) from exc
        return None


def _raise_for_status(status: int, body: Any, request_id: Optional[str]) -> None:
    if 200 <= status < 300:
        return
    error_code: Optional[str] = None
    message = f"HTTP {status}"
    if isinstance(body, dict):
        error_code = body.get("error") if isinstance(body.get("error"), str) else None
        msg = body.get("message")
        if isinstance(msg, str) and msg:
            message = msg
        elif error_code:
            message = error_code
    raise from_status(status, message, error_code=error_code, request_id=request_id)


def request_json(
    method: str,
    url: str,
    *,
    headers: Optional[Mapping[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base: float = DEFAULT_BACKOFF_BASE,
    backoff_cap: float = DEFAULT_BACKOFF_CAP,
    sleep: Callable[[float], None] = time.sleep,
) -> Tuple[int, Any, Mapping[str, str]]:
    """One HTTP round-trip with retry/backoff.

    Returns ``(status, parsed_json_or_none, response_headers)``. Raises
    :class:`TejError` on 4xx/5xx after exhausting retries, or
    :class:`NetworkError` on transport failure.
    """
    merged_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        merged_headers.update(headers)

    last_exc: Optional[BaseException] = None
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(url, method=method, headers=dict(merged_headers))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.status
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                raw = resp.read()
                request_id = resp_headers.get("x-request-id")
                body = _parse_body(raw, status, request_id)
                if status in RETRYABLE_STATUSES and attempt < max_retries:
                    sleep(_backoff_sleep(attempt, backoff_base, backoff_cap))
                    continue
                _raise_for_status(status, body, request_id)
                return status, body, resp_headers
        except urllib.error.HTTPError as exc:
            status = exc.code
            resp_headers = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
            raw = exc.read() if hasattr(exc, "read") else b""
            request_id = resp_headers.get("x-request-id")
            body = _parse_body(raw, status, request_id)
            if status in RETRYABLE_STATUSES and attempt < max_retries:
                sleep(_backoff_sleep(attempt, backoff_base, backoff_cap))
                continue
            _raise_for_status(status, body, request_id)
            return status, body, resp_headers  # unreachable; keeps type checker happy
        except urllib.error.URLError as exc:
            last_exc = exc
            if attempt < max_retries:
                sleep(_backoff_sleep(attempt, backoff_base, backoff_cap))
                continue
            raise NetworkError(f"request to {url} failed: {exc.reason}") from exc
        except TimeoutError as exc:
            last_exc = exc
            if attempt < max_retries:
                sleep(_backoff_sleep(attempt, backoff_base, backoff_cap))
                continue
            raise NetworkError(f"request to {url} timed out after {timeout}s") from exc

    raise NetworkError(f"request to {url} failed after {max_retries} retries: {last_exc}")


def envelope_data(body: Any) -> list[dict[str, Any]]:
    """Extract the ``data`` array from a standard envelope response."""
    if not isinstance(body, dict):
        raise ServerError(f"unexpected response shape: {type(body).__name__}")
    data = body.get("data")
    if data is None:
        return []
    if not isinstance(data, list):
        raise ServerError(f"response 'data' must be a list, got {type(data).__name__}")
    return data
