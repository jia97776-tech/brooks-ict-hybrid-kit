"""Download Bitget TradFi kline history via endTime paging.

Usage:
  python3 download_tradfi_history.py            # XAUUSD + NAS100, default depths
  python3 download_tradfi_history.py SYMBOL...  # override symbols

Output: ~/trading_scanner_service/data/history/{SYMBOL}_{TF}.csv
Columns: ts,open,high,low,close (volume omitted — CFD feed reports 0).
Resumable: existing files are extended backwards/forwards and deduped by ts.
"""

from __future__ import annotations

import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://www.bitgettradfi.com/v1/kline/getMoreKlineDataV2"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "history"
SLEEP_S = 0.4  # be polite to an undocumented endpoint

# tf -> (kLineStep, max depth in days; None = until the feed runs out)
PLAN = {
    "1d": ("1d", None),
    "4h": ("4h", None),
    "15m": ("15m", None),
    "5m": ("5m", 365),
    "1m": ("1m", 90),
}


def fetch(symbol: str, step: str, end_ms: int) -> list:
    params = urllib.parse.urlencode(
        {"symbolId": symbol, "kLineStep": step, "kLineType": 5, "endTime": end_ms})
    req = urllib.request.Request(f"{BASE}?{params}", headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.load(resp)
            if payload.get("code") == "00000":
                return payload.get("data") or []
        except Exception:
            pass
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"fetch failed {symbol} {step} end={end_ms}")


def download(symbol: str, tf: str, step: str, max_days) -> None:
    out = OUT_DIR / f"{symbol}_{tf}.csv"
    rows: dict[int, tuple] = {}
    if out.exists():
        with out.open() as fh:
            for r in csv.reader(fh):
                if r and r[0].isdigit():
                    rows[int(r[0])] = tuple(r)
    now_ms = int(time.time() * 1000)
    cutoff_ms = now_ms - int(max_days * 86400 * 1000) if max_days else 0
    end = now_ms
    pages = 0
    while True:
        data = fetch(symbol, step, end)
        pages += 1
        if not data:
            break
        new = 0
        for r in data:
            ts = int(r[0])
            if ts not in rows:
                rows[ts] = (str(ts // 1000), r[1], r[2], r[3], r[4])
                new += 1
        oldest = int(data[0][0])
        print(f"  {symbol} {tf} page {pages}: +{new} bars, oldest "
              f"{time.strftime('%Y-%m-%d', time.gmtime(oldest / 1000))}", flush=True)
        if new == 0 or oldest <= cutoff_ms or oldest >= end:
            break
        end = oldest
        time.sleep(SLEEP_S)
    ordered = [rows[k] for k in sorted(rows)]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ts", "open", "high", "low", "close"])
        w.writerows(ordered)
    span_d = (int(ordered[-1][0]) - int(ordered[0][0])) / 86400 if ordered else 0
    print(f"  -> {out.name}: {len(ordered)} bars, span {span_d:.0f} days", flush=True)


def main() -> None:
    symbols = [s.upper() for s in sys.argv[1:]] or ["XAUUSD", "NAS100"]
    for symbol in symbols:
        for tf, (step, max_days) in PLAN.items():
            print(f"[{symbol}] {tf} ...", flush=True)
            download(symbol, tf, step, max_days)


if __name__ == "__main__":
    main()
