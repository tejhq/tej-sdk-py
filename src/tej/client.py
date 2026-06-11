"""Synchronous client for tej-api.

>>> from tej import Client
>>> c = Client()
>>> rows = c.ohlcv("RELIANCE", "nse", "2025-01-01", "2025-01-31")
>>> len(rows)
21
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Dict, List, Mapping, Optional, Type

from . import _http
from .models import Action, Envelope, OHLCV, SnapshotRow


class Client:
    """Synchronous client.

    Args:
        base_url: API base URL. Defaults to https://api.tejhq.dev.
        api_key: Optional API key, sent as ``Authorization: Bearer <key>``.
            Not required for any free-tier endpoint.
        timeout: Per-request timeout in seconds.
        max_retries: How many times to retry on 5xx / 429 / network errors
            with exponential backoff. Default 3.
        user_agent_suffix: Appended to the default User-Agent. Useful for
            attribution from your own app.
        default_headers: Extra headers merged into every request.
    """

    def __init__(
        self,
        *,
        base_url: str = _http.DEFAULT_BASE_URL,
        api_key: Optional[str] = None,
        timeout: float = _http.DEFAULT_TIMEOUT,
        max_retries: int = _http.DEFAULT_MAX_RETRIES,
        user_agent_suffix: Optional[str] = None,
        default_headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

        headers: Dict[str, str] = {}
        if default_headers:
            headers.update(default_headers)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if user_agent_suffix:
            headers["User-Agent"] = f"{_http.USER_AGENT} {user_agent_suffix}"
        self._headers = headers

    # context-manager parity with AsyncClient even though there is no socket
    # to close in the stdlib transport; lets users write the same shape of
    # code under either client.
    def __enter__(self) -> "Client":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        self.close()

    def close(self) -> None:
        return None

    def _get(self, path: str, query: Optional[Mapping[str, Any]] = None) -> Any:
        url = _http.build_url(self.base_url, path, query)
        _, body, _ = _http.request_json(
            "GET",
            url,
            headers=self._headers,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )
        return body

    # ---- system probes -------------------------------------------------

    def health(self) -> Dict[str, Any]:
        body = self._get("/health")
        return body if isinstance(body, dict) else {}

    def ready(self) -> Dict[str, Any]:
        body = self._get("/ready")
        return body if isinstance(body, dict) else {}

    # ---- market data ---------------------------------------------------

    def ohlcv(
        self,
        symbol: str,
        exchange: str,
        from_: Optional[str] = None,
        to: Optional[str] = None,
    ) -> List[OHLCV]:
        """End-of-day OHLCV rows for one symbol over a date range.

        Args:
            symbol: Trading symbol, e.g. ``"RELIANCE"``. Case-insensitive.
            exchange: ``"nse"`` or ``"bse"``. Case-insensitive.
            from_: Inclusive start ``YYYY-MM-DD``. Defaults to ``to`` minus
                90 days on the server.
            to: Inclusive end ``YYYY-MM-DD``. Defaults to today (UTC) on
                the server.
        """
        ex = _http.normalize_exchange(exchange)
        sym = _http.normalize_symbol(symbol)
        query: Dict[str, str] = {}
        if from_ is not None:
            query["from"] = _http.validate_date(from_, "from_")
        if to is not None:
            query["to"] = _http.validate_date(to, "to")
        body = self._get(f"/v1/ohlcv/{ex}/{sym}", query or None)
        return _http.envelope_data(body)  # type: ignore[return-value]

    def snapshot(self, exchange: str, date: str) -> List[SnapshotRow]:
        """Every symbol's bhavcopy line for one trading date on one exchange."""
        ex = _http.normalize_exchange(exchange)
        d = _http.validate_date(date, "date")
        body = self._get(f"/v1/snapshot/{ex}", {"date": d})
        return _http.envelope_data(body)  # type: ignore[return-value]

    def actions(self, symbol: str) -> List[Action]:
        """All corporate actions ever recorded for one symbol."""
        sym = _http.normalize_symbol(symbol)
        body = self._get(f"/v1/actions/{sym}")
        return _http.envelope_data(body)  # type: ignore[return-value]

    # ---- envelope variants (with meta) ---------------------------------

    def ohlcv_envelope(
        self,
        symbol: str,
        exchange: str,
        from_: Optional[str] = None,
        to: Optional[str] = None,
    ) -> Envelope:
        ex = _http.normalize_exchange(exchange)
        sym = _http.normalize_symbol(symbol)
        query: Dict[str, str] = {}
        if from_ is not None:
            query["from"] = _http.validate_date(from_, "from_")
        if to is not None:
            query["to"] = _http.validate_date(to, "to")
        body = self._get(f"/v1/ohlcv/{ex}/{sym}", query or None)
        return body if isinstance(body, dict) else {"data": []}
