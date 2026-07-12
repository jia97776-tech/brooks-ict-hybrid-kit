"""Fetch and cache LTF (M1/M5) bars for the model-B (ltf_refine) backtest.

Mirrors fetch_bars.py's pagination approach (MEXC start/end, Gate TradFi
end_time), pinned to the SAME GLOBAL_NOW used by the M15/H4 fetch so the LTF
bar coverage lines up with signals_backtest.jsonl's decision timestamps.

Per scanner_service.ltf_refine.ltf_tf(): US500/NAS100/US30 refine on M1,
everything else refines on M5.

Caches to bars/<SYMBOL>_<TF>.jsonl (same directory/format as fetch_bars.py).
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SERVICE_ROOT))
from scanner_service.sources import (  # noqa: E402
    Bar, GATE_INTERVAL, MEXC_INTERVAL, _json_get, classify_symbol, normalize_symbol,
)

HERE = Path(__file__).resolve().parent
BARS_DIR = HERE / "bars"
BARS_DIR.mkdir(parents=True, exist_ok=True)

# GLOBAL_NOW from fetch_report.json -- pin LTF fetch end to the same instant
# the M15/H4 candidate backtest used, so decision ts <= GLOBAL_NOW always has
# LTF coverage available for the 24h forward trigger search (except right at
# the tail, which is expected and reported honestly).
GLOBAL_NOW = json.loads((HERE / "fetch_report.json").read_text())["now"]

M1_SYMBOLS = {"US500", "NAS100", "US30"}

SYMBOLS_LTF = {
    "US500": "M1", "NAS100": "M1", "US30": "M1",
    "BTC": "M5", "ETH": "M5", "SOL": "M5", "DOGE": "M5",
    "XAUUSD": "M5", "XAGUSD": "M5", "XTIUSD": "M5",
    "EURUSD": "M5", "GBPUSD": "M5", "USDJPY": "M5", "AUDUSD": "M5",
    "USDCAD": "M5", "USDCHF": "M5", "NZDUSD": "M5",
}

TF_SECONDS = {"M1": 60, "M5": 300}

# 33-day decision window + warmup/tail headroom (earliest M15 decision ts is
# ~2026-05-30, GLOBAL_NOW is 2026-07-02 16:58 -> ~34 days; add margin).
FETCH_DAYS = 36

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
    end_ts = GLOBAL_NOW
    start_ts = end_ts - FETCH_DAYS * 86400
    report = {}
    for symbol, tf in SYMBOLS_LTF.items():
        normalized = normalize_symbol(symbol)
        cls = classify_symbol(symbol)
        path = cache_path(symbol, tf)
        if path.exists() and not force:
            existing = load_bars(symbol, tf)
            if existing and existing[0].ts <= start_ts + TF_SECONDS[tf] * 5 and existing[-1].ts >= end_ts - 3 * TF_SECONDS[tf]:
                span_days = (existing[-1].ts - existing[0].ts) / 86400
                report[f"{symbol}_{tf}"] = {"n": len(existing), "span_days": round(span_days, 2), "cached": True}
                print(f"[skip-cached] {symbol} {tf}: n={len(existing)} span={span_days:.1f}d")
                continue
        try:
            if cls == "gate_tradfi":
                bars = fetch_gate(normalized, tf, start_ts, end_ts)
            else:
                bars = fetch_mexc(normalized, tf, start_ts, end_ts)
        except Exception as exc:
            print(f"[FAIL] {symbol} {tf}: {exc}")
            report[f"{symbol}_{tf}"] = {"n": 0, "span_days": 0, "error": str(exc)}
            continue
        save_bars(symbol, tf, bars)
        span_days = (bars[-1].ts - bars[0].ts) / 86400 if len(bars) > 1 else 0
        report[f"{symbol}_{tf}"] = {"n": len(bars), "span_days": round(span_days, 2), "cached": False}
        print(f"[fetched] {symbol} {tf}: n={len(bars)} span={span_days:.1f}d "
              f"({time.strftime('%Y-%m-%d %H:%M', time.gmtime(bars[0].ts)) if bars else '-'} -> "
              f"{time.strftime('%Y-%m-%d %H:%M', time.gmtime(bars[-1].ts)) if bars else '-'})")
        time.sleep(0.2)

    with (HERE / "fetch_ltf_report.json").open("w", encoding="utf-8") as fh:
        json.dump({"global_now": GLOBAL_NOW, "start_ts": start_ts, "coverage": report}, fh, indent=2)
    print("done. global_now=", GLOBAL_NOW, time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(GLOBAL_NOW)))


if __name__ == "__main__":
    main()
