from __future__ import annotations

from typing import Any, Dict, List

import pytest

from tej import (
    BadRequestError,
    Client,
    NotFoundError,
    ProRequiredError,
    RateLimitError,
    ServerError,
    TejError,
)


def test_ohlcv_returns_list_of_dicts(server, ohlcv_response):
    server.route(
        "/v1/ohlcv/nse/RELIANCE",
        lambda p, q: (200, ohlcv_response),
    )
    c = Client(base_url=server.base_url, max_retries=0)
    rows = c.ohlcv("RELIANCE", "nse", "2025-01-01", "2025-01-31")
    assert isinstance(rows, list)
    assert rows[0]["close"] == 1441.75
    method, path, query = server.requests[-1]
    assert method == "GET"
    assert path == "/v1/ohlcv/nse/RELIANCE"
    assert query == {"from": ["2025-01-01"], "to": ["2025-01-31"]}


def test_ohlcv_lowercases_exchange_uppercases_symbol(server, ohlcv_response):
    server.route(
        "/v1/ohlcv/nse/RELIANCE",
        lambda p, q: (200, ohlcv_response),
    )
    c = Client(base_url=server.base_url, max_retries=0)
    c.ohlcv("reliance", "NSE")
    assert server.requests[-1][1] == "/v1/ohlcv/nse/RELIANCE"


def test_ohlcv_omits_unset_date_params(server, ohlcv_response):
    server.route(
        "/v1/ohlcv/nse/RELIANCE",
        lambda p, q: (200, ohlcv_response),
    )
    c = Client(base_url=server.base_url, max_retries=0)
    c.ohlcv("RELIANCE", "nse")
    assert server.requests[-1][2] == {}


def test_snapshot(server, snapshot_response):
    server.route("/v1/snapshot/nse", lambda p, q: (200, snapshot_response))
    c = Client(base_url=server.base_url, max_retries=0)
    rows = c.snapshot("nse", "2025-01-02")
    assert rows[0]["symbol"] == "RELIANCE"
    assert server.requests[-1][2] == {"date": ["2025-01-02"]}


def test_actions(server, actions_response):
    server.route("/v1/actions/RELIANCE", lambda p, q: (200, actions_response))
    c = Client(base_url=server.base_url, max_retries=0)
    rows = c.actions("RELIANCE")
    assert rows[0]["type"] == "dividend"


def test_health_and_ready(server):
    server.route("/health", lambda p, q: (200, {"status": "ok", "time": "2025-01-02T00:00:00Z"}))
    server.route("/ready", lambda p, q: (200, {"status": "ready"}))
    c = Client(base_url=server.base_url, max_retries=0)
    assert c.health()["status"] == "ok"
    assert c.ready()["status"] == "ready"


@pytest.mark.parametrize(
    "status,err_cls",
    [
        (400, BadRequestError),
        (402, ProRequiredError),
        (404, NotFoundError),
        (429, RateLimitError),
        (500, ServerError),
        (503, ServerError),
    ],
)
def test_status_to_exception_mapping(server, status, err_cls):
    server.route(
        "/v1/actions/RELIANCE",
        lambda p, q: (status, {"error": "boom", "message": "kaboom"}),
    )
    c = Client(base_url=server.base_url, max_retries=0)
    with pytest.raises(err_cls) as exc:
        c.actions("RELIANCE")
    assert exc.value.status_code == status
    assert exc.value.error_code == "boom"
    assert exc.value.request_id == "test-req-id"


def test_retry_then_success(server, ohlcv_response):
    state: Dict[str, int] = {"calls": 0}

    def flaky(_p: str, _q: Any) -> Any:
        state["calls"] += 1
        if state["calls"] < 3:
            return 503, {"error": "unavailable"}
        return 200, ohlcv_response

    server.route("/v1/ohlcv/nse/RELIANCE", flaky)
    c = Client(base_url=server.base_url, max_retries=3)
    rows = c.ohlcv("RELIANCE", "nse")
    assert len(rows) == 1
    assert state["calls"] == 3


def test_retry_gives_up_after_max(server):
    server.route(
        "/v1/actions/RELIANCE",
        lambda p, q: (503, {"error": "still_dead"}),
    )
    c = Client(base_url=server.base_url, max_retries=2)
    with pytest.raises(ServerError):
        c.actions("RELIANCE")


def test_invalid_symbol_raises_value_error_before_network(server):
    c = Client(base_url=server.base_url, max_retries=0)
    with pytest.raises(ValueError):
        c.ohlcv("not a valid symbol!", "nse")
    assert server.requests == []


def test_invalid_exchange_raises_value_error(server):
    c = Client(base_url=server.base_url, max_retries=0)
    with pytest.raises(ValueError):
        c.snapshot("mcx", "2025-01-02")


def test_invalid_date_raises_value_error(server):
    c = Client(base_url=server.base_url, max_retries=0)
    with pytest.raises(ValueError):
        c.snapshot("nse", "2025/01/02")


def test_api_key_sets_authorization_header(server, ohlcv_response):
    captured: List[str] = []

    class CapturingHandler:
        def __call__(self, p: str, q: Any) -> Any:
            return 200, ohlcv_response

    server.route("/v1/ohlcv/nse/RELIANCE", CapturingHandler())
    c = Client(base_url=server.base_url, api_key="tej_live_abc", max_retries=0)
    assert c._headers["Authorization"] == "Bearer tej_live_abc"


def test_context_manager(server, ohlcv_response):
    server.route("/v1/ohlcv/nse/RELIANCE", lambda p, q: (200, ohlcv_response))
    with Client(base_url=server.base_url, max_retries=0) as c:
        rows = c.ohlcv("RELIANCE", "nse")
    assert len(rows) == 1


def test_ohlcv_envelope_returns_meta(server, ohlcv_response):
    server.route("/v1/ohlcv/nse/RELIANCE", lambda p, q: (200, ohlcv_response))
    c = Client(base_url=server.base_url, max_retries=0)
    env = c.ohlcv_envelope("RELIANCE", "nse")
    assert env["meta"]["symbol"] == "RELIANCE"
    assert len(env["data"]) == 1
