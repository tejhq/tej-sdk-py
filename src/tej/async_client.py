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
from types import TracebackType
from typing import Any, Dict, List, Mapping, Optional, Type

from . import _http
from .models import Action, Envelope, OHLCV, SnapshotRow


class AsyncClient:
    """Asynchronous client. Same surface as :class:`Client` with `await`."""

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

    async def __aenter__(self) -> "AsyncClient":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        return None

    async def _get(self, path: str, query: Optional[Mapping[str, Any]] = None) -> Any:
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

    async def health(self) -> Dict[str, Any]:
        body = await self._get("/health")
        return body if isinstance(body, dict) else {}

    async def ready(self) -> Dict[str, Any]:
        body = await self._get("/ready")
        return body if isinstance(body, dict) else {}

    # ---- market data ---------------------------------------------------

    async def ohlcv(
        self,
        symbol: str,
        exchange: str,
        from_: Optional[str] = None,
        to: Optional[str] = None,
    ) -> List[OHLCV]:
        ex = _http.normalize_exchange(exchange)
        sym = _http.normalize_symbol(symbol)
        query: Dict[str, str] = {}
        if from_ is not None:
            query["from"] = _http.validate_date(from_, "from_")
        if to is not None:
            query["to"] = _http.validate_date(to, "to")
        body = await self._get(f"/v1/ohlcv/{ex}/{sym}", query or None)
        return _http.envelope_data(body)  # type: ignore[return-value]

    async def snapshot(self, exchange: str, date: str) -> List[SnapshotRow]:
        ex = _http.normalize_exchange(exchange)
        d = _http.validate_date(date, "date")
        body = await self._get(f"/v1/snapshot/{ex}", {"date": d})
        return _http.envelope_data(body)  # type: ignore[return-value]

    async def actions(self, symbol: str) -> List[Action]:
        sym = _http.normalize_symbol(symbol)
        body = await self._get(f"/v1/actions/{sym}")
        return _http.envelope_data(body)  # type: ignore[return-value]

    async def ohlcv_envelope(
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
        body = await self._get(f"/v1/ohlcv/{ex}/{sym}", query or None)
        return body if isinstance(body, dict) else {"data": []}
