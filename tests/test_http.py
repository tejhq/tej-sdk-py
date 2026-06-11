from __future__ import annotations

import pytest

from tej._http import build_url, normalize_exchange, normalize_symbol, validate_date


def test_normalize_exchange():
    assert normalize_exchange("nse") == "nse"
    assert normalize_exchange("NSE") == "nse"
    assert normalize_exchange("  BSE  ") == "bse"
    with pytest.raises(ValueError):
        normalize_exchange("mcx")
    with pytest.raises(ValueError):
        normalize_exchange("")


def test_normalize_symbol():
    assert normalize_symbol("reliance") == "RELIANCE"
    assert normalize_symbol("M&M") == "M&M"
    assert normalize_symbol("HDFC-BANK") == "HDFC-BANK"
    with pytest.raises(ValueError):
        normalize_symbol("has space")
    with pytest.raises(ValueError):
        normalize_symbol("a" * 31)


def test_validate_date():
    assert validate_date("2025-01-02", "from_") == "2025-01-02"
    with pytest.raises(ValueError):
        validate_date("2025/01/02", "from_")
    with pytest.raises(ValueError):
        validate_date("2025-1-2", "from_")


def test_build_url_no_query():
    assert build_url("https://api.tejhq.dev", "/v1/health") == "https://api.tejhq.dev/v1/health"


def test_build_url_with_query():
    url = build_url("https://api.tejhq.dev/", "v1/ohlcv/nse/RELIANCE", {"from": "2025-01-01"})
    assert url == "https://api.tejhq.dev/v1/ohlcv/nse/RELIANCE?from=2025-01-01"


def test_build_url_skips_none_values():
    url = build_url("https://api.tejhq.dev", "/v1/ohlcv/nse/X", {"from": "2025-01-01", "to": None})
    assert "to=" not in url
    assert "from=2025-01-01" in url
