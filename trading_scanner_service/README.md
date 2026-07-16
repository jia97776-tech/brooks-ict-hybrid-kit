# Local Trading Scanner Service

Local HTTP scanner for Codex live-desk use.

## Data Source Rule

- Gate-only since 2026-07-14. There is no cross-venue fallback.
- Crypto uses Gate USDT-M futures.
- FX, metals, indexes, oil, and US stocks use Gate TradFi.
- If Gate is unavailable, the request fails with `SourceError` instead of
  silently mixing quotes from another venue.

## Run

```bash
python3 run_server.py
```

## Test

```bash
python3 -m unittest discover -s tests -v
```

## Endpoints

- `GET /price/{symbol}`
- `GET /bars?symbol={symbol}&tf=M15` (M1/M5/M15/M30/H1/H4/D1/W1)
- `GET /multi-bars?symbol={symbol}&tfs=1m,5m,15m,1h,4h,1d,1w`
- `POST /scanner/run-once?mode=intraday|swing|both` (M15 / H4 / both)
- `GET /scanner/status`
- `POST /scan/run?mode=...`
- `GET /scan/status/{job_id}`
- `GET /signals?limit=100`
- `GET /symbols`
- `GET /healthz`
- `GET /openapi.json`

## Scanner Logic (2026-07-01 rebuild)

Structure layer (`scanner_service/structure.py`): confirmed fractal swings
(k=2 both sides), liquidity sweeps (wick through a prior untaken swing,
close back inside, no acceptance since), independent MSS (close through the
last opposing swing) and CISD (close through the open of the delivery leg),
and DOL targets from real untaken swing liquidity.

Candidate states:

- `READY`: sweep + MSS and/or CISD confirmed on a close + planned RR >= 1.
- `CONDITIONAL_READY`: sweep with something missing; `reason` says what.
- `ARMED`: no sweep; liquidity map only.

Key fields: `poi` = sweep zone `[swept_level, extreme]`, `sl` = extreme +
0.25 ATR, `dol`/`dol_runner` = nearest/next untaken liquidity, `rr` =
planned RR from the POI retest, `rr_now` = chase-RR from current price,
`late` = price left the sweep zone, `target_crowded` = near target consumed
(< 0.8 ATR away), `equal_liquidity` = clustered equal highs/lows at the DOL.

Default universe: 28 symbols across crypto, metals, oil, indexes, USD FX
majors, and four US stocks. UK100/HK50/USDCNH/XBRUSD are not supported.
