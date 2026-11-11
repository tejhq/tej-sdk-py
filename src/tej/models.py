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


class DeliveryRow(TypedDict):
    date: str
    volume: int
    delivery_qty: int
    delivery_pct: float


class FORow(TypedDict):
    """One F&O contract on one day. ``strike``/``option_type`` are None for
    futures; ``underlying``/``lot_size`` are None before 2024-07-08.
    ``iv`` and the Greeks are set on options that traded that day: Black-76
    on the same-expiry forward, delta and gamma against the forward, theta
    per calendar day, vega per volatility point."""

    date: str
    instrument: str
    expiry: str
    strike: float | None
    option_type: str | None
    open: float
    high: float
    low: float
    close: float
    settle_price: float
    contracts: int
    turnover: float
    open_interest: int
    oi_change: int
    underlying: float | None
    lot_size: int | None
    iv: float | None
    delta: float | None
    gamma: float | None
    theta: float | None
    vega: float | None


class FOExpiry(TypedDict):
    expiry: str
    instrument: str
    contracts: int
    open_interest: int
    strikes: int


class FOStatsRow(TypedDict):
    """Daily F&O figures for one symbol and expiry, computed by TejHQ.

    Option fields are None for an expiry with only futures, and futures
    fields are None for a weekly expiry with only options. ``buildup`` is
    one of long_buildup, short_buildup, short_covering, long_unwinding.
    """

    date: str
    kind: str
    expiry: str
    is_nearest: bool
    ce_oi: int | None
    pe_oi: int | None
    ce_oi_change: int | None
    pe_oi_change: int | None
    ce_contracts: int | None
    pe_contracts: int | None
    pcr_oi: float | None
    pcr_volume: float | None
    max_pain: float | None
    strikes: int | None
    fut_settle: float | None
    fut_settle_change: float | None
    fut_oi: int | None
    fut_oi_change: int | None
    fut_contracts: int | None
    buildup: str | None
    underlying: float | None
    basis: float | None
    rollover_pct: float | None
    atm_iv: float | None
    iv_skew: float | None


class UnusualRow(TypedDict):
    """One stock doing something far outside its own recent normal on a day.

    ``value`` is what happened, ``normal`` what is usual for the stock and
    ``z`` the distance in standard deviations.
    """

    date: str
    symbol: str
    isin: str | None
    signal: str
    value: float | None
    normal: float | None
    z: float | None
    close: float | None
    ret_1d: float | None
    volume_ratio: float | None
    turnover: float | None


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


class ScreenerRow(MetricsRow):
    """One instrument on one day with its metrics, from ``/v1/screener``."""

    symbol: str


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
