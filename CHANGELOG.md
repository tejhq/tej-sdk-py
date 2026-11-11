# Changelog

## 0.7.0

- `FORow` gains `iv`, `delta`, `gamma`, `theta`, `vega` (options that traded that day), returned by `fo_chain()` and `fo_contract()`.
- `FOStatsRow` gains `atm_iv` and `iv_skew`.

## 0.6.0

- `fo_stats()`: daily F&O figures per expiry (put-call ratio by OI and volume, max pain, futures buildup, basis, rollover %) since 2010. Retail and Pro.
- Unusual activity, NSE, Retail and Pro: `unusual()` and `unusual_envelope()` for one day, strongest first, and `unusual_history()` for one stock since 2010. Signals: volume, move, gap, delivery, fut_oi, high_52w, low_52w.
- `FOStatsRow` and `UnusualRow` models.

## 0.5.0

- F&O (NSE futures and options, end of day, since 2010), Retail and Pro: `fo_chain()`, `fo_chain_envelope()`, `fo_expiries()`, `fo_futures()`, `fo_contract()` on both clients.
- `FORow` and `FOExpiry` models.

## 0.4.0

- `delivery()` on both clients: NSE delivery quantity and % per day since 2010. Free key.
- `DeliveryRow` model.

## 0.3.0

- `screener()` and `screener_envelope()` on both clients: cross-sectional filters on the metrics tree, point-in-time universe restriction, sort and paging. Pro tier.
- `ScreenerRow` model.

## 0.2.0

- Free key endpoints: `adjusted()`, `symbols()`, `me()`.
- Pro endpoints: `metrics()`, `universe()`, `batch()`, `resolve()`.
- `AuthError` for HTTP 401 with `error_code` `key_required` or `invalid_key`.
- PEP 604 unions throughout, mypy target 3.10.

## 0.1.0

- First release: `ohlcv()`, `snapshot()`, `actions()`, sync and async clients, zero runtime dependencies.
