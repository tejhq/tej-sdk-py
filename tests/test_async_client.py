from __future__ import annotations

import asyncio

import pytest

from tej import AsyncClient, NotFoundError


async def test_ohlcv_async(server, ohlcv_response):
    server.route("/v1/ohlcv/nse/RELIANCE", lambda p, q: (200, ohlcv_response))
    async with AsyncClient(base_url=server.base_url, max_retries=0) as c:
        rows = await c.ohlcv("RELIANCE", "nse", "2025-01-01", "2025-01-31")
    assert rows[0]["close"] == 1441.75


async def test_snapshot_async(server, snapshot_response):
    server.route("/v1/snapshot/nse", lambda p, q: (200, snapshot_response))
    async with AsyncClient(base_url=server.base_url, max_retries=0) as c:
        rows = await c.snapshot("nse", "2025-01-02")
    assert rows[0]["isin"] == "INE002A01018"


async def test_actions_async(server, actions_response):
    server.route("/v1/actions/RELIANCE", lambda p, q: (200, actions_response))
    async with AsyncClient(base_url=server.base_url, max_retries=0) as c:
        rows = await c.actions("RELIANCE")
    assert rows[0]["cash_amount"] == 10.0


async def test_exception_mapping_async(server):
    server.route("/v1/actions/RELIANCE", lambda p, q: (404, {"error": "not_found"}))
    async with AsyncClient(base_url=server.base_url, max_retries=0) as c:
        with pytest.raises(NotFoundError):
            await c.actions("RELIANCE")


async def test_concurrent_fan_out(server, ohlcv_response):
    # 10 different symbols in parallel; the to_thread bridge should give us
    # actual concurrency, so wall-clock < 10 * single-request latency.
    for sym in ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
                "SBIN", "HINDUNILVR", "ITC", "LT", "AXISBANK"]:
        server.route(f"/v1/ohlcv/nse/{sym}", lambda p, q: (200, ohlcv_response))
    async with AsyncClient(base_url=server.base_url, max_retries=0) as c:
        results = await asyncio.gather(
            *[c.ohlcv(s, "nse") for s in ["RELIANCE", "TCS", "INFY", "HDFCBANK",
                                          "ICICIBANK", "SBIN", "HINDUNILVR",
                                          "ITC", "LT", "AXISBANK"]]
        )
    assert len(results) == 10
    assert all(r[0]["close"] == 1441.75 for r in results)


async def test_retry_async(server, ohlcv_response):
    state = {"calls": 0}

    def flaky(p, q):
        state["calls"] += 1
        if state["calls"] < 2:
            return 503, {"error": "x"}
        return 200, ohlcv_response

    server.route("/v1/ohlcv/nse/RELIANCE", flaky)
    async with AsyncClient(base_url=server.base_url, max_retries=2) as c:
        rows = await c.ohlcv("RELIANCE", "nse")
    assert len(rows) == 1
    assert state["calls"] == 2
