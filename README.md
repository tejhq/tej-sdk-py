# tej

[![PyPI](https://img.shields.io/pypi/v/tejhq.svg)](https://pypi.org/project/tejhq/)
[![Python](https://img.shields.io/pypi/pyversions/tejhq.svg)](https://pypi.org/project/tejhq/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Python SDK for [tej-api](https://api.tejhq.dev): open, free, end-of-day market data for NSE and BSE. No signup, no keys, no catch.

**Zero runtime dependencies.** Sync and async clients with identical surface. Returns plain `list[dict]` rows so you can feed them straight to polars, pandas, or your own code without an extra conversion step.

## Install

```bash
pip install tejhq
```

That is the entire install. No `httpx`, no `aiohttp`, no `pydantic`. Just stdlib. Distribution is `tejhq`; import as `tej`.

## Quick start (sync)

```python
from tej import Client

c = Client()

# Last 90 days of RELIANCE (default range)
rows = c.ohlcv("RELIANCE", "nse")
print(rows[-1])
# {'date': '2026-06-05', 'open': 1442.0, 'high': 1455.7, ...}

# Full history since 2010
rows = c.ohlcv("RELIANCE", "nse", "2010-01-04", "2026-06-05")
print(len(rows))  # ~4040

# Full-market snapshot for one trading date
snap = c.snapshot("nse", "2025-05-28")
print(len(snap))  # ~2700 symbols

# Corporate actions (dividends, splits, bonuses)
acts = c.actions("RELIANCE")
print(acts[0])
# {'exchange': 'NSE', 'type': 'dividend', 'ex_date': '2024-10-28', 'cash_amount': 10.0, ...}
```

## Quick start (async)

```python
import asyncio
from tej import AsyncClient

async def main():
    async with AsyncClient() as c:
        # Fan out 10 symbols concurrently
        symbols = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
                   "SBIN", "HINDUNILVR", "ITC", "LT", "AXISBANK"]
        results = await asyncio.gather(*[c.ohlcv(s, "nse") for s in symbols])
        for sym, rows in zip(symbols, results):
            print(sym, len(rows))

asyncio.run(main())
```

## Use with polars / pandas

`tej` returns `list[dict]` so you bring your own dataframe library.

```python
import polars as pl
from tej import Client

rows = Client().ohlcv("RELIANCE", "nse", "2010-01-04", "2026-06-05")
df = pl.DataFrame(rows)
df = df.with_columns(pl.col("date").str.to_date())
df.head()
```

```python
import pandas as pd
from tej import Client

rows = Client().ohlcv("RELIANCE", "nse", "2025-01-01", "2025-06-01")
df = pd.DataFrame(rows)
df["date"] = pd.to_datetime(df["date"])
df.set_index("date", inplace=True)
df["close"].plot()
```

Optional extras install the dataframe library alongside the SDK:

```bash
pip install "tejhq[polars]"
pip install "tejhq[pandas]"
```

## API reference (free tier)

| Method | Endpoint | Returns |
| --- | --- | --- |
| `c.ohlcv(symbol, exchange, from_=None, to=None)` | `GET /v1/ohlcv/{exchange}/{symbol}` | `list[OHLCV]` |
| `c.snapshot(exchange, date)` | `GET /v1/snapshot/{exchange}?date=` | `list[SnapshotRow]` |
| `c.actions(symbol)` | `GET /v1/actions/{symbol}` | `list[Action]` |
| `c.health()` | `GET /health` | `dict` |
| `c.ready()` | `GET /ready` | `dict` |

Need the response envelope (with `meta`)? Use `c.ohlcv_envelope(...)`, which returns the raw `{"data": [...], "meta": {...}}` dict.

`AsyncClient` exposes the same surface with `await`:

```python
async with AsyncClient() as c:
    rows = await c.ohlcv("RELIANCE", "nse")
```

## Configuration

```python
from tej import Client

c = Client(
    base_url="https://api.tejhq.dev",   # override for self-hosted or staging
    api_key=None,                        # not needed for free tier
    timeout=30.0,                        # seconds
    max_retries=3,                       # exponential backoff on 5xx/429/network
    user_agent_suffix="my-app/1.0",      # for attribution
    default_headers={"X-My-Header": "hi"},
)
```

## Errors

All errors inherit from `tej.TejError`. The specific subclass tells you what happened:

| Exception | When |
| --- | --- |
| `BadRequestError` | HTTP 400, bad path or query parameter (also raised locally on invalid args before the request goes out, as a plain `ValueError`) |
| `NotFoundError` | HTTP 404 |
| `ProRequiredError` | HTTP 402, endpoint is part of the Pro tier (`/v1/adjusted`, `/v1/symbols`, `/v1/metrics`, `/v1/universe`) |
| `RateLimitError` | HTTP 429 |
| `ServerError` | HTTP 5xx |
| `NetworkError` | DNS, connection, TLS, or timeout failure |
| `TejError` | Anything else |

```python
from tej import Client, ProRequiredError

try:
    Client().ohlcv("RELIANCE", "nse")
except ProRequiredError as e:
    print(e.error_code)  # 'pro_required'
    print(e.request_id)  # tej-api request id from response headers
```

## Why a separate package

[tej-api](https://github.com/tejhq/tej-api) is a Go service. [tej-bazaar](https://github.com/tejhq/tej-bazaar) is the Python ingestion pipeline. This repo is the thin client that anyone can `pip install` without dragging in either, and that releases on its own cadence as the API evolves.

## Coverage

- **NSE bhavcopy + corp actions**: 2010-01-04 to today, ~4,047 trading days, ~7M rows
- **BSE bhavcopy + corp actions**: 2024-07-08 to today (the SEBI CMTS cutover), ~470 days, ~1M rows
- **Cron refresh**: weekdays 20:00 IST

Free-tier endpoints are served at the Cloudflare edge from pre-rendered JSON, so most requests return in well under a second and repeat requests are cache hits. Keyless access is rate limited to 100 requests per 10 seconds per IP at the edge and 120 per minute at origin; the SDK retries 429s with backoff. A free API key with higher limits is coming; pass it as `api_key=` when it does.

## License

MIT. Use it, fork it, ship products on top of it.

## Links

- API docs: [tejhq.dev/docs](https://tejhq.dev/docs)
- OpenAPI spec: [api.tejhq.dev/openapi.yaml](https://api.tejhq.dev/openapi.yaml)
- Bulk parquet downloads: [data.tejhq.dev](https://data.tejhq.dev) and [huggingface.co/datasets/tejhq/indian-markets](https://huggingface.co/datasets/tejhq/indian-markets)
- Issues: [github.com/tejhq/tej-sdk-py/issues](https://github.com/tejhq/tej-sdk-py/issues)
