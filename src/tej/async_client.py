"""Asynchronous client for tej-api.

>>> import asyncio
>>> from tej import AsyncClient
>>>
>>> async def main():
...     async with AsyncClient() as c:
...         rows = await c.ohlcv("RELIANCE", "nse", "2025-01-01", "2025-01-31")
...         return len(rows)
>>> asyncio.run(main())
21

The zero-runtime-dependency rule means we cannot pull in ``httpx`` or
``aiohttp``. ``asyncio.to_thread`` runs the blocking stdlib ``urllib`` call in
the default executor, which still gives real parallelism for ``gather``-style
concurrent fan-out (each in-flight request occupies one worker thread). For
ten or so concurrent EOD requests this is indistinguishable from native async
I/O. If you need to fan out hundreds of requests, raise the loop's executor
size with ``loop.set_default_executor(ThreadPoolExecutor(max_workers=N))``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
from types import TracebackType
from typing import Any, cast

from . import _http
from .client import _screener_query
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


class AsyncClient:
    """Asynchronous client. Same surface as :class:`Client` with `await`."""

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

    async def __aenter__(self) -> AsyncClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        return None

    async def _get(self, path: str, query: Mapping[str, Any] | None = None) -> Any:
        url = _http.build_url(self.base_url, path, query)
        result = await asyncio.to_thread(
            _http.request_json,
            "GET",
            url,
            headers=self._headers,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )
        _, body, _ = result
        return body

    # ---- system probes -------------------------------------------------

    async def health(self) -> dict[str, Any]:
        body = await self._get("/health")
        return body if isinstance(body, dict) else {}

    async def ready(self) -> dict[str, Any]:
        body = await self._get("/ready")
        return body if isinstance(body, dict) else {}

    # ---- market data ---------------------------------------------------

    async def ohlcv(
        self,
        symbol: str,
        exchange: str,
        from_: str | None = None,
        to: str | None = None,
    ) -> list[OHLCV]:
        ex = _http.normalize_exchange(exchange)
        sym = _http.normalize_symbol(symbol)
        query: dict[str, str] = {}
        if from_ is not None:
            query["from"] = _http.validate_date(from_, "from_")
        if to is not None:
            query["to"] = _http.validate_date(to, "to")
        body = await self._get(f"/v1/ohlcv/{ex}/{sym}", query or None)
        return _http.envelope_data(body)  # type: ignore[return-value]

    async def snapshot(self, exchange: str, date: str) -> list[SnapshotRow]:
        ex = _http.normalize_exchange(exchange)
        d = _http.validate_date(date, "date")
        body = await self._get(f"/v1/snapshot/{ex}", {"date": d})
        return _http.envelope_data(body)  # type: ignore[return-value]

    async def actions(self, symbol: str) -> list[Action]:
        sym = _http.normalize_symbol(symbol)
        body = await self._get(f"/v1/actions/{sym}")
        return _http.envelope_data(body)  # type: ignore[return-value]

    # ---- free key tier -------------------------------------------------

    async def adjusted(
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
        body = await self._get(f"/v1/adjusted/{ex}/{sym}", _range_query(from_, to))
        return _http.envelope_data(body)  # type: ignore[return-value]

    async def symbols(
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
        body = await self._get(f"/v1/symbols/{ex}", query)
        return _http.envelope_data(body)  # type: ignore[return-value]

    async def me(self) -> dict[str, Any]:
        """Account, keys and today's usage for the calling key."""
        body = await self._get("/v1/me")
        return body if isinstance(body, dict) else {}

    # ---- pro tier ------------------------------------------------------

    async def metrics(
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
        body = await self._get(f"/v1/metrics/{ex}/{sym}", _range_query(from_, to))
        return _http.envelope_data(body)  # type: ignore[return-value]

    async def universe(
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
        body = await self._get(f"/v1/universe/{n}", query)
        return _http.envelope_data(body)  # type: ignore[return-value]

    async def batch(
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
        body = await self._get("/v1/batch", query)
        data = body.get("data") if isinstance(body, dict) else None
        return data if isinstance(data, dict) else {}

    async def resolve(
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
        body = await self._get("/v1/resolve", {"q": q, "exchange": ex, "limit": str(limit)})
        return _http.envelope_data(body)  # type: ignore[return-value]

    async def screener(
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

        See :meth:`tej.Client.screener` for the argument semantics.
        """
        body = await self._get(
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

    async def screener_envelope(
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
        body = await self._get(
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

    async def ohlcv_envelope(
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
        body = await self._get(f"/v1/ohlcv/{ex}/{sym}", query or None)
        return cast(Envelope, body) if isinstance(body, dict) else Envelope(data=[])


def _range_query(from_: str | None, to: str | None) -> dict[str, str] | None:
    query: dict[str, str] = {}
    if from_ is not None:
        query["from"] = _http.validate_date(from_, "from_")
    if to is not None:
        query["to"] = _http.validate_date(to, "to")
    return query or None
