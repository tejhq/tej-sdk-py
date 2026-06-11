"""Stdlib-only test fixtures.

We spin up a real ``http.server`` on a free port and route a handful of canned
responses. This is enough to exercise URL building, retry, exception mapping,
and async fan-out without pulling in ``pytest-httpserver`` or ``respx``.
"""

from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Dict, Generator, List, Tuple
from urllib.parse import parse_qs, urlsplit

import pytest

Response = Tuple[int, Dict[str, Any]]
Handler = Callable[[str, Dict[str, List[str]]], Response]


class _Server:
    def __init__(self) -> None:
        self.requests: List[Tuple[str, str, Dict[str, List[str]]]] = []
        self.handlers: Dict[str, Handler] = {}
        self.default_handler: Handler = lambda p, q: (404, {"error": "not_found"})
        self._httpd: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.port = 0

    def route(self, path: str, handler: Handler) -> None:
        self.handlers[path] = handler

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        server = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *_: Any, **__: Any) -> None:
                return

            def do_GET(self) -> None:  # noqa: N802
                split = urlsplit(self.path)
                path = split.path
                query = parse_qs(split.query)
                server.requests.append(("GET", path, query))
                handler = server.handlers.get(path, server.default_handler)
                status, body = handler(path, query)
                payload = json.dumps(body).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("X-Request-ID", "test-req-id")
                self.end_headers()
                self.wfile.write(payload)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        self.port = sock.getsockname()[1]
        sock.close()

        self._httpd = HTTPServer(("127.0.0.1", self.port), H)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)


@pytest.fixture
def server() -> Generator[_Server, None, None]:
    s = _Server()
    s.start()
    try:
        yield s
    finally:
        s.stop()


@pytest.fixture
def ohlcv_response() -> Dict[str, Any]:
    return {
        "data": [
            {
                "date": "2025-01-02",
                "open": 1432.5,
                "high": 1445.0,
                "low": 1428.1,
                "close": 1441.75,
                "last": 1441.8,
                "prev_close": 1430.2,
                "volume": 8421300,
                "turnover": 12104500000.5,
                "trades": 184320,
            }
        ],
        "meta": {"exchange": "NSE", "symbol": "RELIANCE", "count": 1},
    }


@pytest.fixture
def snapshot_response() -> Dict[str, Any]:
    return {
        "data": [
            {
                "symbol": "RELIANCE",
                "series": "EQ",
                "isin": "INE002A01018",
                "name": "RELIANCE INDUSTRIES",
                "open": 1432.5,
                "high": 1445.0,
                "low": 1428.1,
                "close": 1441.75,
                "last": 1441.8,
                "prev_close": 1430.2,
                "volume": 8421300,
                "turnover": 12104500000.5,
                "trades": 184320,
            }
        ],
        "meta": {"exchange": "NSE", "date": "2025-01-02", "count": 1},
    }


@pytest.fixture
def actions_response() -> Dict[str, Any]:
    return {
        "data": [
            {
                "exchange": "NSE",
                "symbol": "RELIANCE",
                "isin": "INE002A01018",
                "company": "Reliance Industries",
                "ex_date": "2024-10-28",
                "record_date": "2024-10-28",
                "type": "dividend",
                "ratio_num": None,
                "ratio_den": None,
                "cash_amount": 10.0,
                "face_value_from": None,
                "face_value_to": None,
                "raw_subject": "Interim Dividend - Rs 10/- Per Share",
            }
        ],
        "meta": {"symbol": "RELIANCE", "count": 1},
    }
