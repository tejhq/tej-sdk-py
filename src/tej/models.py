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

from typing import Any, Dict, List, Literal, Optional, TypedDict

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
    record_date: Optional[str]
    type: str
    ratio_num: Optional[int]
    ratio_den: Optional[int]
    cash_amount: Optional[float]
    face_value_from: Optional[float]
    face_value_to: Optional[float]
    raw_subject: str


class Envelope(TypedDict, total=False):
    data: List[Dict[str, Any]]
    meta: Dict[str, Any]


__all__ = [
    "Action",
    "Envelope",
    "Exchange",
    "OHLCV",
    "SnapshotRow",
]
