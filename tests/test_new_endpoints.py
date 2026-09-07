"""Free key and Pro endpoints, sync and async, against the canned server."""

from __future__ import annotations

import asyncio

import pytest

from tej import AsyncClient, AuthError, Client, ProRequiredError


@pytest.fixture
def adjusted_response():
    return {
        "data": [
            {
                "date": "2025-01-02",
                "open": 1,
                "high": 1,
                "low": 1,
                "close": 1,
                "volume": 1,
                "turnover": 1.0,
                "adj_factor_cumulative": 0.5,
                "adj_close": 0.5,
            }
        ],
        "meta": {"count": 1},
    }


def test_adjusted_sends_key_and_range(server, adjusted_response):
    server.route("/v1/adjusted/nse/RELIANCE", lambda p, q: (200, adjusted_response))
    c = Client(base_url=server.base_url, api_key="tej_live_" + "a" * 32, max_retries=0)
    rows = c.adjusted("reliance", "NSE", "2025-01-01", "2025-01-31")
    assert rows[0]["adj_close"] == 0.5
    assert server.requests[-1][2] == {"from": ["2025-01-01"], "to": ["2025-01-31"]}


def test_keyless_gated_endpoint_raises_auth_error(server):
    server.route(
        "/v1/adjusted/nse/TCS",
        lambda p, q: (401, {"error": "key_required", "message": "needs a key"}),
    )
    c = Client(base_url=server.base_url, max_retries=0)
    with pytest.raises(AuthError) as ei:
        c.adjusted("TCS", "nse")
    assert ei.value.error_code == "key_required"


def test_free_key_on_pro_endpoint_raises_pro_required(server):
    server.route(
        "/v1/metrics/nse/TCS", lambda p, q: (402, {"error": "pro_required", "message": "pro"})
    )
    c = Client(base_url=server.base_url, api_key="tej_live_" + "a" * 32, max_retries=0)
    with pytest.raises(ProRequiredError):
        c.metrics("TCS", "nse")


def test_symbols_requires_filter_and_uppercases(server):
    server.route(
        "/v1/symbols/nse",
        lambda p, q: (
            200,
            {
                "data": [
                    {
                        "isin": "INE",
                        "symbol": "X",
                        "valid_from": "2020-01-01",
                        "valid_to": "2020-02-01",
                        "trading_days": 20,
                    }
                ],
                "meta": {},
            },
        ),
    )
    c = Client(base_url=server.base_url, max_retries=0)
    with pytest.raises(ValueError):
        c.symbols("nse")
    c.symbols("nse", isin="ine040a01034")
    assert server.requests[-1][2] == {"isin": ["INE040A01034"]}
    c.symbols("nse", symbol="hdfcbank")
    assert server.requests[-1][2] == {"symbol": ["HDFCBANK"]}


def test_universe_validates_name_and_sends_as_of(server):
    server.route(
        "/v1/universe/liquid100",
        lambda p, q: (
            200,
            {
                "data": [
                    {
                        "rank": 1,
                        "symbol": "A",
                        "isin": "I",
                        "name": "A Ltd",
                        "avg_turnover_63d": 1.0,
                    }
                ],
                "meta": {},
            },
        ),
    )
    c = Client(base_url=server.base_url, max_retries=0)
    with pytest.raises(ValueError):
        c.universe("nifty50")
    rows = c.universe("liquid100", "nse", "2019-03-15")
    assert rows[0]["rank"] == 1
    assert server.requests[-1][2] == {"exchange": ["nse"], "as_of": ["2019-03-15"]}


def test_batch_joins_symbols_and_returns_dict(server):
    server.route(
        "/v1/batch",
        lambda p, q: (200, {"data": {"RELIANCE": [], "TCS": [{"date": "2025-01-02"}]}, "meta": {}}),
    )
    c = Client(base_url=server.base_url, max_retries=0)
    out = c.batch(["reliance", "tcs"], "nse", "2025-01-01")
    assert out["TCS"][0]["date"] == "2025-01-02" and out["RELIANCE"] == []
    q = server.requests[-1][2]
    assert (
        q["symbols"] == ["RELIANCE,TCS"]
        and q["exchange"] == ["nse"]
        and q["from"] == ["2025-01-01"]
    )
    with pytest.raises(ValueError):
        c.batch([])
    with pytest.raises(ValueError):
        c.batch([f"S{i}" for i in range(51)])


def test_resolve_params_and_validation(server):
    server.route(
        "/v1/resolve",
        lambda p, q: (
            200,
            {"data": [{"symbol": "RELIANCE", "score": 0.96, "matched_on": "name"}], "meta": {}},
        ),
    )
    c = Client(base_url=server.base_url, max_retries=0)
    hits = c.resolve("reliance industries", limit=3)
    assert hits[0]["symbol"] == "RELIANCE"
    assert server.requests[-1][2] == {
        "q": ["reliance industries"],
        "exchange": ["both"],
        "limit": ["3"],
    }
    with pytest.raises(ValueError):
        c.resolve("x")
    with pytest.raises(ValueError):
        c.resolve("abc", limit=0)


def test_me(server):
    server.route("/v1/me", lambda p, q: (200, {"email": "a@b.c", "tier": "free", "keys": []}))
    c = Client(base_url=server.base_url, api_key="tej_live_" + "a" * 32, max_retries=0)
    assert c.me()["tier"] == "free"


def test_async_parity(server, adjusted_response):
    server.route("/v1/adjusted/nse/RELIANCE", lambda p, q: (200, adjusted_response))
    server.route("/v1/resolve", lambda p, q: (200, {"data": [{"symbol": "RELIANCE"}], "meta": {}}))
    server.route("/v1/batch", lambda p, q: (200, {"data": {"TCS": []}, "meta": {}}))

    async def main():
        async with AsyncClient(base_url=server.base_url, max_retries=0) as c:
            a, r, b = await asyncio.gather(
                c.adjusted("RELIANCE", "nse"),
                c.resolve("reliance"),
                c.batch(["TCS"]),
            )
            return a, r, b

    a, r, b = asyncio.run(main())
    assert a[0]["adj_close"] == 0.5 and r[0]["symbol"] == "RELIANCE" and b == {"TCS": []}
