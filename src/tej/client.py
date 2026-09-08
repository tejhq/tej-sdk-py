"""Synchronous client for tej-api.

>>> from tej import Client
>>> c = Client()
>>> rows = c.ohlcv("RELIANCE", "nse", "2025-01-01", "2025-01-31")
>>> len(rows)
21
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import TracebackType
from typing import Any, cast

from . import _http
from .models import (
    OHLCV,
    Action,
    AdjustedRow,
    Envelope,
    MetricsRow,
    ResolveHit,
    ScreenerRow,
    SnapshotRow,
    SymbolInterval,
    UniverseMember,
)


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
        api_key: str | None = None,
        timeout: float = _http.DEFAULT_TIMEOUT,
        max_retries: int = _http.DEFAULT_MAX_RETRIES,
        user_agent_suffix: str | None = None,
        default_headers: Mapping[str, str] | None = None,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

        headers: dict[str, str] = {}
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
    def __enter__(self) -> Client:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        return None

    def _get(self, path: str, query: Mapping[str, Any] | None = None) -> Any:
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

    def health(self) -> dict[str, Any]:
        body = self._get("/health")
        return body if isinstance(body, dict) else {}

    def ready(self) -> dict[str, Any]:
        body = self._get("/ready")
        return body if isinstance(body, dict) else {}

    # ---- market data ---------------------------------------------------

    def ohlcv(
        self,
        symbol: str,
        exchange: str,
        from_: str | None = None,
        to: str | None = None,
    ) -> list[OHLCV]:
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
        query: dict[str, str] = {}
        if from_ is not None:
            query["from"] = _http.validate_date(from_, "from_")
        if to is not None:
            query["to"] = _http.validate_date(to, "to")
        body = self._get(f"/v1/ohlcv/{ex}/{sym}", query or None)
        return _http.envelope_data(body)  # type: ignore[return-value]

    def snapshot(self, exchange: str, date: str) -> list[SnapshotRow]:
        """Every symbol's bhavcopy line for one trading date on one exchange."""
        ex = _http.normalize_exchange(exchange)
        d = _http.validate_date(date, "date")
        body = self._get(f"/v1/snapshot/{ex}", {"date": d})
        return _http.envelope_data(body)  # type: ignore[return-value]

    def actions(self, symbol: str) -> list[Action]:
        """All corporate actions ever recorded for one symbol."""
        sym = _http.normalize_symbol(symbol)
        body = self._get(f"/v1/actions/{sym}")
        return _http.envelope_data(body)  # type: ignore[return-value]

    # ---- free key tier -------------------------------------------------

    def adjusted(
        self,
        symbol: str,
        exchange: str,
        from_: str | None = None,
        to: str | None = None,
    ) -> list[AdjustedRow]:
        """Back-adjusted prices for one symbol. Needs a free API key.

        Same range semantics as :meth:`ohlcv`. Adds ``adj_factor_cumulative``
        and ``adj_close``, continuous through splits, bonuses and dividends.
        """
        ex = _http.normalize_exchange(exchange)
        sym = _http.normalize_symbol(symbol)
        body = self._get(f"/v1/adjusted/{ex}/{sym}", _range_query(from_, to))
        return _http.envelope_data(body)  # type: ignore[return-value]

    def symbols(
        self,
        exchange: str,
        *,
        symbol: str | None = None,
        isin: str | None = None,
    ) -> list[SymbolInterval]:
        """Symbol history by ``symbol`` or ``isin``. Needs a free API key.

        One row per contiguous run of an ISIN under a symbol.
        """
        if symbol is None and isin is None:
            raise ValueError("pass symbol= or isin=")
        ex = _http.normalize_exchange(exchange)
        query: dict[str, str] = {}
        if symbol is not None:
            query["symbol"] = _http.normalize_symbol(symbol)
        if isin is not None:
            query["isin"] = isin.strip().upper()
        body = self._get(f"/v1/symbols/{ex}", query)
        return _http.envelope_data(body)  # type: ignore[return-value]

    def me(self) -> dict[str, Any]:
        """Account, keys and today's usage for the calling key."""
        body = self._get("/v1/me")
        return body if isinstance(body, dict) else {}

    # ---- pro tier ------------------------------------------------------

    def metrics(
        self,
        symbol: str,
        exchange: str,
        from_: str | None = None,
        to: str | None = None,
    ) -> list[MetricsRow]:
        """Per-day derived metrics on adjusted close. Needs a Pro key.

        Returns at 1/5/21/63/126/252 days and YTD, 52-week high and low with
        distance, average volume and turnover. Rolling fields are ``None``
        until a full window of history exists.
        """
        ex = _http.normalize_exchange(exchange)
        sym = _http.normalize_symbol(symbol)
        body = self._get(f"/v1/metrics/{ex}/{sym}", _range_query(from_, to))
        return _http.envelope_data(body)  # type: ignore[return-value]

    def universe(
        self,
        name: str = "liquid500",
        exchange: str = "nse",
        as_of: str | None = None,
    ) -> list[UniverseMember]:
        """Point-in-time liquidity universe. Needs a Pro key.

        ``name`` is ``liquid100``, ``liquid250`` or ``liquid500``: the top N
        by trailing 63-day turnover at the latest monthly rebalance on or
        before ``as_of`` (default today). Delisted names stay in the months
        they qualified for, so there is no survivorship bias.
        """
        n = name.strip().lower()
        if n not in ("liquid100", "liquid250", "liquid500"):
            raise ValueError("name must be liquid100, liquid250 or liquid500")
        query: dict[str, str] = {"exchange": _http.normalize_exchange(exchange)}
        if as_of is not None:
            query["as_of"] = _http.validate_date(as_of, "as_of")
        body = self._get(f"/v1/universe/{n}", query)
        return _http.envelope_data(body)  # type: ignore[return-value]

    def batch(
        self,
        symbols: Iterable[str],
        exchange: str = "nse",
        from_: str | None = None,
        to: str | None = None,
    ) -> dict[str, list[OHLCV]]:
        """OHLCV for up to 50 symbols in one request. Needs a Pro key.

        Returns a dict keyed by symbol; unknown symbols map to ``[]``.
        """
        syms = [_http.normalize_symbol(s) for s in symbols]
        if not syms:
            raise ValueError("symbols must not be empty")
        if len(syms) > 50:
            raise ValueError("at most 50 symbols per batch")
        query = _range_query(from_, to) or {}
        query["symbols"] = ",".join(syms)
        query["exchange"] = _http.normalize_exchange(exchange)
        body = self._get("/v1/batch", query)
        data = body.get("data") if isinstance(body, dict) else None
        return data if isinstance(data, dict) else {}

    def resolve(
        self,
        q: str,
        exchange: str = "both",
        limit: int = 5,
    ) -> list[ResolveHit]:
        """Resolve free text to symbols. Needs a Pro key.

        ``"Reliance Industries"``, ``"tata mot"``, ``"infosis"`` or a former
        ticker like ``"ZOMATO"`` all resolve. Best match first, with
        ``score`` and ``matched_on``.
        """
        q = q.strip()
        if not 2 <= len(q) <= 80:
            raise ValueError("q must be 2 to 80 characters")
        if not 1 <= limit <= 25:
            raise ValueError("limit must be 1 to 25")
        ex = "both" if exchange.lower() == "both" else _http.normalize_exchange(exchange)
        body = self._get("/v1/resolve", {"q": q, "exchange": ex, "limit": str(limit)})
        return _http.envelope_data(body)  # type: ignore[return-value]

    def screener(
        self,
        exchange: str = "nse",
        *,
        date: str | None = None,
        universe: str | None = None,
        filters: Mapping[str, float] | None = None,
        sort: str | None = None,
        order: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ScreenerRow]:
        """Screen the whole market on one trading day. Needs a Pro key.

        ``filters`` maps ``"<column>.<op>"`` to a number, e.g.
        ``{"ret_21d.gt": 0.05, "pct_off_52w_high.gte": -0.05}``, with op
        in ``gt``, ``gte``, ``lt``, ``lte``. At most ten, all ANDed. ``date``
        snaps back to the latest trading day on or before it. ``universe``
        (``liquid100``, ``liquid250``, ``liquid500``) restricts to the
        point-in-time membership on that day. Use :meth:`screener_envelope`
        for ``meta.total`` and the date actually used.
        """
        body = self._get(
            "/v1/screener",
            _screener_query(
                exchange,
                date,
                universe,
                filters,
                sort,
                order,
                limit,
                offset,
            ),
        )
        return _http.envelope_data(body)  # type: ignore[return-value]

    def screener_envelope(
        self,
        exchange: str = "nse",
        *,
        date: str | None = None,
        universe: str | None = None,
        filters: Mapping[str, float] | None = None,
        sort: str | None = None,
        order: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Envelope:
        """:meth:`screener` with the ``meta`` block: ``date`` used, ``total`` matches."""
        body = self._get(
            "/v1/screener",
            _screener_query(
                exchange,
                date,
                universe,
                filters,
                sort,
                order,
                limit,
                offset,
            ),
        )
        return cast(Envelope, body) if isinstance(body, dict) else Envelope(data=[])

    # ---- envelope variants (with meta) ---------------------------------

    def ohlcv_envelope(
        self,
        symbol: str,
        exchange: str,
        from_: str | None = None,
        to: str | None = None,
    ) -> Envelope:
        ex = _http.normalize_exchange(exchange)
        sym = _http.normalize_symbol(symbol)
        query: dict[str, str] = {}
        if from_ is not None:
            query["from"] = _http.validate_date(from_, "from_")
        if to is not None:
            query["to"] = _http.validate_date(to, "to")
        body = self._get(f"/v1/ohlcv/{ex}/{sym}", query or None)
        return cast(Envelope, body) if isinstance(body, dict) else Envelope(data=[])


def _range_query(from_: str | None, to: str | None) -> dict[str, str] | None:
    query: dict[str, str] = {}
    if from_ is not None:
        query["from"] = _http.validate_date(from_, "from_")
    if to is not None:
        query["to"] = _http.validate_date(to, "to")
    return query or None


SCREENER_COLUMNS = frozenset(
    {
        "adj_close",
        "ret_1d",
        "ret_5d",
        "ret_21d",
        "ret_63d",
        "ret_126d",
        "ret_252d",
        "ret_ytd",
        "high_52w",
        "low_52w",
        "pct_off_52w_high",
        "pct_off_52w_low",
        "avg_vol_20d",
        "avg_vol_60d",
        "avg_turnover_20d",
    }
)
SCREENER_OPS = frozenset({"gt", "gte", "lt", "lte"})
SCREENER_UNIVERSES = frozenset({"liquid100", "liquid250", "liquid500"})


def _screener_query(
    exchange: str,
    date: str | None,
    universe: str | None,
    filters: Mapping[str, float] | None,
    sort: str | None,
    order: str | None,
    limit: int,
    offset: int,
) -> dict[str, str]:
    query: dict[str, str] = {"exchange": _http.normalize_exchange(exchange)}
    if date is not None:
        query["date"] = _http.validate_date(date, "date")
    if universe is not None:
        u = universe.strip().lower()
        if u not in SCREENER_UNIVERSES:
            raise ValueError("universe must be liquid100, liquid250 or liquid500")
        query["universe"] = u
    if filters:
        if len(filters) > 10:
            raise ValueError("at most 10 filters per screen")
        for key, value in filters.items():
            col, _, op = key.partition(".")
            col, op = col.strip().lower(), op.strip().lower()
            if col not in SCREENER_COLUMNS or op not in SCREENER_OPS:
                raise ValueError(
                    f"filter {key!r} must be '<column>.<op>' with op in gt, gte, lt, lte"
                )
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"filter {key!r} value must be a number")
            query[f"{col}.{op}"] = repr(float(value))
    if sort is not None:
        st = sort.strip().lower()
        if st != "symbol" and st not in SCREENER_COLUMNS:
            raise ValueError("sort must be 'symbol' or a metrics column")
        query["sort"] = st
    if order is not None:
        o = order.strip().lower()
        if o not in ("asc", "desc"):
            raise ValueError("order must be 'asc' or 'desc'")
        query["order"] = o
    if not 1 <= limit <= 500:
        raise ValueError("limit must be 1 to 500")
    if offset < 0:
        raise ValueError("offset must be 0 or more")
    query["limit"] = str(limit)
    query["offset"] = str(offset)
    return query
