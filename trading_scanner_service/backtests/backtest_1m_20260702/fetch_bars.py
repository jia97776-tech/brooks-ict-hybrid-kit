"""Fetch and cache historical bars for the trading_scanner_service backtest.

Uses the exact same symbol/timeframe normalization as production
(scanner_service.sources), but adds pagination (MEXC: start/end unix
seconds; Gate TradFi: end_time unix seconds) since the production client
classes only expose a single `limit` param.

Caches to bars/<SYMBOL>_<TF>.jsonl (one JSON object per line, ascending ts).
Re-runnable: skips symbols/tf whose cache file already covers the requested
range (use --force to refetch).
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, "/home/ubuntu/trading_scanner_service")
from scanner_service.sources import (  # noqa: E402
    Bar, GATE_INTERVAL, MEXC_INTERVAL, _json_get, classify_symbol, normalize_symbol,
)

HERE = Path(__file__).resolve().parent
BARS_DIR = HERE / "bars"
BARS_DIR.mkdir(parents=True, exist_ok=True)

SYMBOLS = [
    "BTC", "ETH", "SOL", "DOGE",
    "XAUUSD", "XAGUSD", "XTIUSD",
    "NAS100", "US500", "US30",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
]

TF_SECONDS = {"M15": 900, "H4": 14400}

# Generous fetch ranges: decision-time window for candidate generation is
# ~33 days; these ranges add head-room for warmup windows (M15 240 bars /
# H4 180 bars + HTF-bias 60-bar lookback) plus forward settlement bars.
FETCH_DAYS = {"M15": 40, "H4": 70}

MEXC_CAP = 2000
GATE_CAP = 500


def fetch_mexc(normalized: str, tf: str, start_ts: int, end_ts: int) -> list[Bar]:
    interval = MEXC_INTERVAL[tf]
    tf_s = TF_SECONDS[tf]
    out: dict[int, Bar] = {}
    cur_end = end_ts
    while True:
        params = urllib.parse.urlencode({"interval": interval, "start": start_ts, "end": cur_end})
        url = f"https://contract.mexc.com/api/v1/contract/kline/{normalized}?{params}"
        payload = _json_get(url)
        data = payload.get("data") if isinstance(payload, dict) else None
        times = data.get("time", []) if isinstance(data, dict) else []
        if not times:
            break
        for idx, ts in enumerate(times):
            out[int(ts)] = Bar(
                ts=int(ts), open=float(data["open"][idx]), high=float(data["high"][idx]),
                low=float(data["low"][idx]), close=float(data["close"][idx]),
                volume=float(data.get("vol", [0.0] * len(times))[idx]),
            )
        earliest = int(min(times))
        if earliest <= start_ts or len(times) < MEXC_CAP:
            break
        cur_end = earliest - tf_s
        time.sleep(0.35)
    return sorted(out.values(), key=lambda b: b.ts)


def fetch_gate(normalized: str, tf: str, start_ts: int, end_ts: int) -> list[Bar]:
    interval = GATE_INTERVAL[tf]
    tf_s = TF_SECONDS[tf]
    out: dict[int, Bar] = {}
    cur_end = end_ts
    while True:
        params = urllib.parse.urlencode({"kline_type": interval, "limit": GATE_CAP, "end_time": cur_end})
        url = f"https://api.gateio.ws/api/v4/tradfi/symbols/{normalized}/klines?{params}"
        payload = _json_get(url)
        raw = payload.get("data", {}).get("list") if isinstance(payload, dict) else None
        if not raw:
            break
        for row in raw:
            ts = int(float(row.get("t", row.get("time"))))
            out[ts] = Bar(
                ts=ts, open=float(row["o"]), high=float(row["h"]), low=float(row["l"]),
                close=float(row["c"]), volume=float(row.get("v", 0.0)),
            )
        earliest = min(int(float(r.get("t", r.get("time")))) for r in raw)
        if earliest <= start_ts or len(raw) < GATE_CAP:
            break
        cur_end = earliest - tf_s
        time.sleep(0.35)
    return sorted(out.values(), key=lambda b: b.ts)


def cache_path(symbol: str, tf: str) -> Path:
    return BARS_DIR / f"{symbol}_{tf}.jsonl"


def save_bars(symbol: str, tf: str, bars: list[Bar]) -> None:
    path = cache_path(symbol, tf)
    with path.open("w", encoding="utf-8") as fh:
        for b in bars:
            fh.write(json.dumps({"ts": b.ts, "open": b.open, "high": b.high,
                                  "low": b.low, "close": b.close, "volume": b.volume}) + "\n")


def load_bars(symbol: str, tf: str) -> list[Bar]:
    path = cache_path(symbol, tf)
    if not path.exists():
        return []
    bars = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            bars.append(Bar(ts=d["ts"], open=d["open"], high=d["high"], low=d["low"],
                             close=d["close"], volume=d.get("volume", 0.0)))
    return bars


def main():
    force = "--force" in sys.argv
    now = int(time.time())
    report = {}
    for symbol in SYMBOLS:
        normalized = normalize_symbol(symbol)
        cls = classify_symbol(symbol)
        for tf in ("M15", "H4"):
            path = cache_path(symbol, tf)
            days = FETCH_DAYS[tf]
            start_ts = now - days * 86400
            if path.exists() and not force:
                existing = load_bars(symbol, tf)
                if existing and existing[0].ts <= start_ts + TF_SECONDS[tf] * 5 and existing[-1].ts >= now - 3 * TF_SECONDS[tf]:
                    span_days = (existing[-1].ts - existing[0].ts) / 86400
                    report[f"{symbol}_{tf}"] = {"n": len(existing), "span_days": round(span_days, 2), "cached": True}
                    print(f"[skip-cached] {symbol} {tf}: n={len(existing)} span={span_days:.1f}d")
                    continue
            try:
                if cls == "gate_tradfi":
                    bars = fetch_gate(normalized, tf, start_ts, now)
                else:
                    bars = fetch_mexc(normalized, tf, start_ts, now)
            except Exception as exc:
                print(f"[FAIL] {symbol} {tf}: {exc}")
                report[f"{symbol}_{tf}"] = {"n": 0, "span_days": 0, "error": str(exc)}
                continue
            save_bars(symbol, tf, bars)
            span_days = (bars[-1].ts - bars[0].ts) / 86400 if len(bars) > 1 else 0
            report[f"{symbol}_{tf}"] = {"n": len(bars), "span_days": round(span_days, 2), "cached": False}
            print(f"[fetched] {symbol} {tf}: n={len(bars)} span={span_days:.1f}d "
                  f"({time.strftime('%Y-%m-%d', time.gmtime(bars[0].ts)) if bars else '-'} -> "
                  f"{time.strftime('%Y-%m-%d', time.gmtime(bars[-1].ts)) if bars else '-'})")
            time.sleep(0.2)

    with (HERE / "fetch_report.json").open("w", encoding="utf-8") as fh:
        json.dump({"now": now, "coverage": report}, fh, indent=2)
    print("done. now=", now, time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(now)))


if __name__ == "__main__":
    main()
