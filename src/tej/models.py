"""Row schemas for tej-api responses.

These are `TypedDict`s rather than dataclasses so that values returned by the
SDK are plain `dict`s, usable directly with `polars.DataFrame(rows)`,
`pandas.DataFrame(rows)`, or any other tabular library, without an extra
conversion step.

All date fields are strings formatted as ``YYYY-MM-DD`` (matching the API's
``format: date`` declaration). Parse with ``datetime.date.fromisoformat`` or
``polars.col("date").str.to_date()`` if you need a date object.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

Exchange = Literal["nse", "bse", "NSE", "BSE"]


class OHLCV(TypedDict):
    date: str
    open: float
    high: float
    low: float
    close: float
    last: float
    prev_close: float
    volume: int
    turnover: float
    trades: int


class SnapshotRow(TypedDict):
    symbol: str
    series: str
    isin: str
    name: str
    open: float
    high: float
    low: float
    close: float
    last: float
    prev_close: float
    volume: int
    turnover: float
    trades: int


class Action(TypedDict, total=False):
    exchange: str
    symbol: str
    isin: str
    company: str
    ex_date: str
    record_date: str | None
    type: str
    ratio_num: int | None
    ratio_den: int | None
    cash_amount: float | None
    face_value_from: float | None
    face_value_to: float | None
    raw_subject: str


class AdjustedRow(TypedDict):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    turnover: float
    adj_factor_cumulative: float
    adj_close: float


class SymbolInterval(TypedDict):
    isin: str
    symbol: str
    valid_from: str
    valid_to: str
    trading_days: int


class MetricsRow(TypedDict):
    date: str
    isin: str
    adj_close: float
    ret_1d: float | None
    ret_5d: float | None
    ret_21d: float | None
    ret_63d: float | None
    ret_126d: float | None
    ret_252d: float | None
    ret_ytd: float | None
    high_52w: float | None
    low_52w: float | None
    pct_off_52w_high: float | None
    pct_off_52w_low: float | None
    avg_vol_20d: float | None
    avg_vol_60d: float | None
    avg_turnover_20d: float | None


class UniverseMember(TypedDict):
    rank: int
    symbol: str
    isin: str
    name: str
    avg_turnover_63d: float


class ResolveHit(TypedDict, total=False):
    exchange: str
    symbol: str
    isin: str
    name: str
    score: float
    matched_on: Literal["symbol", "former_symbol", "name", "symbol_prefix", "name_prefix", "fuzzy"]
    former_symbols: list[str]


class Envelope(TypedDict, total=False):
    data: list[dict[str, Any]]
    meta: dict[str, Any]


__all__ = [
    "Action",
    "Envelope",
    "Exchange",
    "OHLCV",
    "SnapshotRow",
]
