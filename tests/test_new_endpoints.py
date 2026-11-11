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


def test_delivery_sends_key_and_range(server):
    body = {
        "data": [{"date": "2026-10-30", "volume": 100, "delivery_qty": 55, "delivery_pct": 55.0}],
        "meta": {"count": 1},
    }
    server.route("/v1/delivery/nse/RELIANCE", lambda p, q: (200, body))
    c = Client(base_url=server.base_url, api_key="tej_live_" + "a" * 32, max_retries=0)
    rows = c.delivery("reliance", from_="2026-10-01", to="2026-10-30")
    assert rows[0]["delivery_pct"] == 55.0
    assert server.requests[-1][2] == {"from": ["2026-10-01"], "to": ["2026-10-30"]}

    async def main():
        async with AsyncClient(base_url=server.base_url, max_retries=0) as ac:
            return await ac.delivery("RELIANCE")

    assert asyncio.run(main())[0]["delivery_qty"] == 55


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


def test_screener_query_and_validation(server):
    server.route(
        "/v1/screener",
        lambda p, q: (
            200,
            {
                "data": [{"symbol": "TBZ", "date": "2026-09-07", "ret_21d": 0.95}],
                "meta": {"date": "2026-09-07", "total": 64, "count": 1},
            },
        ),
    )
    c = Client(base_url=server.base_url, api_key="tej_live_" + "a" * 32, max_retries=0)
    rows = c.screener(
        "NSE",
        universe="liquid500",
        filters={"ret_21d.gt": 0.05, "pct_off_52w_high.gte": -0.05, "avg_turnover_20d.gte": 5e7},
        sort="ret_21d",
        limit=5,
    )
    assert rows[0]["symbol"] == "TBZ"
    assert server.requests[-1][2] == {
        "exchange": ["nse"],
        "universe": ["liquid500"],
        "ret_21d.gt": ["0.05"],
        "pct_off_52w_high.gte": ["-0.05"],
        "avg_turnover_20d.gte": ["50000000.0"],
        "sort": ["ret_21d"],
        "limit": ["5"],
        "offset": ["0"],
    }
    env = c.screener_envelope(date="2026-09-08")
    assert env["meta"]["total"] == 64
    assert server.requests[-1][2]["date"] == ["2026-09-08"]

    for bad in (
        dict(filters={"foo.gt": 1}),
        dict(filters={"ret_1d.like": 1}),
        dict(filters={"ret_1d.gt": "x"}),
        dict(filters={f"ret_{n}d.gt": 0 for n in range(11)}),
        dict(universe="nifty50"),
        dict(sort="name"),
        dict(order="up"),
        dict(limit=0),
        dict(limit=501),
        dict(offset=-1),
        dict(date="2026/09/08"),
    ):
        with pytest.raises(ValueError):
            c.screener(**bad)


def test_screener_async(server):
    server.route("/v1/screener", lambda p, q: (200, {"data": [{"symbol": "X"}], "meta": {}}))

    async def main():
        async with AsyncClient(base_url=server.base_url, max_retries=0) as c:
            return await c.screener(filters={"ret_1d.gt": 0.1}, limit=1)

    assert asyncio.run(main())[0]["symbol"] == "X"


def _fo_row(**kw):
    row = {
        "date": "2026-10-30",
        "instrument": "OPTIDX",
        "expiry": "2026-11-03",
        "strike": 23000.0,
        "option_type": "CE",
        "open": 1,
        "high": 1,
        "low": 1,
        "close": 1,
        "settle_price": 1,
        "contracts": 10,
        "turnover": 1.0,
        "open_interest": 100,
        "oi_change": 5,
        "underlying": 23053.1,
        "lot_size": 65,
    }
    row.update(kw)
    return row


def test_fo_chain_and_envelope(server):
    meta = {"date": "2026-10-30", "expiry": "2026-11-03", "underlying": 23053.1}
    body = {"data": [_fo_row()], "meta": meta}
    server.route("/v1/fo/chain/NIFTY", lambda p, q: (200, body))
    c = Client(base_url=server.base_url, api_key="tej_live_" + "a" * 32, max_retries=0)
    assert c.fo_chain("nifty")[0]["strike"] == 23000.0
    assert server.requests[-1][2] == {}
    env = c.fo_chain_envelope("NIFTY", date="2026-10-30", expiry="2026-11-03")
    assert env["meta"]["underlying"] == 23053.1
    assert server.requests[-1][2] == {"date": ["2026-10-30"], "expiry": ["2026-11-03"]}


def test_fo_expiries_futures_contract(server):
    fut = _fo_row(instrument="FUTIDX", strike=None, option_type=None)
    expiries = {"data": [{"expiry": "2026-11-03"}], "meta": {}}
    server.route("/v1/fo/expiries/NIFTY", lambda p, q: (200, expiries))
    server.route("/v1/fo/futures/NIFTY", lambda p, q: (200, {"data": [fut], "meta": {}}))
    server.route("/v1/fo/contract/NIFTY", lambda p, q: (200, {"data": [_fo_row()], "meta": {}}))
    c = Client(base_url=server.base_url, max_retries=0)
    assert c.fo_expiries("NIFTY", "2026-10-30")[0]["expiry"] == "2026-11-03"
    assert c.fo_futures("NIFTY", "2026-10-01")[0]["strike"] is None
    c.fo_contract("NIFTY", "2026-11-24", 23000, "ce", from_="2026-10-01")
    assert server.requests[-1][2] == {
        "expiry": ["2026-11-24"],
        "strike": ["23000"],
        "option_type": ["CE"],
        "from": ["2026-10-01"],
    }
    c.fo_contract("NIFTY", "2026-11-24")
    assert server.requests[-1][2] == {"expiry": ["2026-11-24"]}


def test_fo_contract_validation():
    c = Client(max_retries=0)
    with pytest.raises(ValueError, match="together"):
        c.fo_contract("NIFTY", "2026-11-24", strike=23000)
    with pytest.raises(ValueError, match="option_type"):
        c.fo_contract("NIFTY", "2026-11-24", 23000, "XX")
    with pytest.raises(ValueError, match="positive"):
        c.fo_contract("NIFTY", "2026-11-24", -1, "CE")


def test_fo_async(server):
    server.route("/v1/fo/chain/NIFTY", lambda p, q: (200, {"data": [_fo_row()], "meta": {}}))
    server.route("/v1/fo/contract/NIFTY", lambda p, q: (200, {"data": [_fo_row()], "meta": {}}))

    async def main():
        async with AsyncClient(base_url=server.base_url, max_retries=0) as c:
            return await asyncio.gather(
                c.fo_chain("NIFTY"), c.fo_contract("NIFTY", "2026-11-24", 23000, "PE")
            )

    chain, contract = asyncio.run(main())
    assert chain[0]["lot_size"] == 65 and contract[0]["option_type"] == "CE"


def test_fo_stats(server):
    row = {
        "date": "2026-11-09",
        "kind": "index",
        "expiry": "2026-11-24",
        "is_nearest": True,
        "pcr_oi": 1.1,
    }
    server.route("/v1/fo/stats/NIFTY", lambda p, q: (200, {"data": [row], "meta": {}}))
    c = Client(base_url=server.base_url, max_retries=0)
    assert c.fo_stats("nifty", "2026-11-01", expiry="2026-11-24")[0]["pcr_oi"] == 1.1
    assert server.requests[-1][2] == {"from": ["2026-11-01"], "expiry": ["2026-11-24"]}
    c.fo_stats("NIFTY")
    assert server.requests[-1][2] == {}


def _unusual_row(**kw):
    row = {
        "date": "2026-11-09",
        "symbol": "DIVISLAB",
        "isin": "INE361B01024",
        "signal": "move",
        "value": 0.12,
        "normal": 0.016,
        "z": 7.45,
    }
    row.update(kw)
    return row


def test_unusual_day_and_history(server):
    day = {"data": [_unusual_row()], "meta": {"exchange": "nse", "date": "2026-11-09", "count": 1}}
    server.route("/v1/unusual/nse", lambda p, q: (200, day))
    server.route(
        "/v1/unusual/nse/DIVISLAB", lambda p, q: (200, {"data": [_unusual_row()], "meta": {}})
    )
    c = Client(base_url=server.base_url, max_retries=0)
    assert c.unusual()[0]["symbol"] == "DIVISLAB"
    assert server.requests[-1][2] == {}
    env = c.unusual_envelope("2026-11-09", signal="FUT_OI")
    assert env["meta"]["date"] == "2026-11-09"
    assert server.requests[-1][2] == {"date": ["2026-11-09"], "signal": ["fut_oi"]}
    assert c.unusual_history("divislab", "2015-01-01", signal="move")[0]["z"] == 7.45
    assert server.requests[-1][2] == {"from": ["2015-01-01"], "signal": ["move"]}


def test_unusual_validation():
    c = Client(base_url="http://127.0.0.1:9", max_retries=0)
    with pytest.raises(ValueError):
        c.unusual(signal="momentum")
    with pytest.raises(ValueError):
        c.unusual(exchange="bse")


def test_async_unusual_and_fo_stats(server):
    server.route(
        "/v1/unusual/nse",
        lambda p, q: (200, {"data": [_unusual_row()], "meta": {"date": "2026-11-09"}}),
    )
    server.route("/v1/fo/stats/NIFTY", lambda p, q: (200, {"data": [{"pcr_oi": 0.9}], "meta": {}}))

    async def main():
        async with AsyncClient(base_url=server.base_url, max_retries=0) as c:
            return await c.unusual(signal="move"), await c.fo_stats("NIFTY")

    u, s = asyncio.run(main())
    assert u[0]["signal"] == "move" and s[0]["pcr_oi"] == 0.9
