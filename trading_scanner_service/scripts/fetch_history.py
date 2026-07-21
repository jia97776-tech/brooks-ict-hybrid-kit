"""Deep kline history downloader (breaks the local router's 1000-bar cap).

Sources (Bitget-only, same endpoints/symbol maps as scanner_service.sources):
  - Crypto (11): Bitget USDT-M futures.
      recent chunk : /api/v2/mix/market/candles          (limit 1000, no paging needed)
      deep history : /api/v2/mix/market/history-candles  (limit 200, endTime paging - PROBED OK)
  - Non-crypto (metals/indexes/oil/FX): bitgettradfi getMoreKlineDataV2.
      PROBED 2026-07-10: accepts endTime (ms) paging, 1000 bars/page, ascending;
      XAGUSD/US30/EURUSD/USOUSD all return data >=100 days back on 5m.
  - No cross-venue fallback (no MEXC/Gate). If Bitget fails, the TF is left partial.

Output: data/history/{SYMBOL}_{TF}.jsonl  (one bar per line: ts,open,high,low,close; ts=seconds, bar open time)
Idempotent + incremental: existing files are topped up at the front (recent) and
extended backwards from their oldest ts. Polite: >=0.2s between requests, 3 retries with backoff.

Usage:
  python3 scripts/fetch_history.py            # all 24 symbols, all TFs
  python3 scripts/fetch_history.py BTC XAUUSD # subset
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "history"
SLEEP_S = 0.25
UA = {"User-Agent": "Mozilla/5.0 (deep-history-fetch)"}

CRYPTO = ["BTC", "ETH", "SOL", "DOGE", "XRP", "SUI", "HYPE", "PEPE", "ZEC", "TAO", "WLD"]
# display -> bitgettradfi symbolId (same map as sources.BITGET_TRADFI)
TRADFI = {
    "XAUUSD": "XAUUSD", "XAGUSD": "XAGUSD", "XTIUSD": "USOUSD",
    "NAS100": "NAS100", "US500": "US500", "US30": "US30",
    "EURUSD": "EURUSD", "GBPUSD": "GBPUSD", "USDJPY": "USDJPY",
    "USDCHF": "USDCHF", "USDCAD": "USDCAD", "AUDUSD": "AUDUSD", "NZDUSD": "NZDUSD",
}

# tf -> (seconds, target depth days)  [targets exceed spec: M5>=90d, M15>=180d]
PLAN = {
    "M5": (300, 120),
    "M15": (900, 300),
    "D1": (86400, 700),
}
BITGET_GRAN = {"M5": "5m", "M15": "15m", "D1": "1D"}
TRADFI_STEP = {"M5": "5m", "M15": "15m", "D1": "1d"}


def _get(url: str, attempts: int = 3, timeout: float = 15.0):
    last = None
    for a in range(attempts):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.0 * (a + 1))
    raise RuntimeError(f"GET failed after {attempts}: {url}: {last}")


# ---------------- source page fetchers: return list[(ts_s,o,h,l,c)] ascending ----------------

def bitget_recent(sym: str, tf: str) -> list[tuple]:
    q = urllib.parse.urlencode({"symbol": f"{sym}USDT", "productType": "usdt-futures",
                                "granularity": BITGET_GRAN[tf], "limit": 1000})
    p = _get(f"https://api.bitget.com/api/v2/mix/market/candles?{q}")
    rows = p.get("data") or []
    return [(int(r[0]) // 1000, float(r[1]), float(r[2]), float(r[3]), float(r[4])) for r in rows]


def bitget_page(sym: str, tf: str, end_ms: int) -> list[tuple]:
    q = urllib.parse.urlencode({"symbol": f"{sym}USDT", "productType": "usdt-futures",
                                "granularity": BITGET_GRAN[tf], "limit": 200, "endTime": end_ms})
    p = _get(f"https://api.bitget.com/api/v2/mix/market/history-candles?{q}")
    if p.get("code") != "00000":
        raise RuntimeError(f"bitget history-candles error {sym} {tf}: {p}")
    rows = p.get("data") or []
    return [(int(r[0]) // 1000, float(r[1]), float(r[2]), float(r[3]), float(r[4])) for r in rows]


def tradfi_page(sym_id: str, tf: str, end_ms: int) -> list[tuple]:
    q = urllib.parse.urlencode({"symbolId": sym_id, "kLineStep": TRADFI_STEP[tf],
                                "kLineType": 5, "endTime": end_ms})
    p = _get(f"https://www.bitgettradfi.com/v1/kline/getMoreKlineDataV2?{q}")
    if p.get("code") != "00000":
        raise RuntimeError(f"tradfi kline error {sym_id} {tf}: {p}")
    rows = p.get("data") or []
    return [(int(r[0]) // 1000, float(r[1]), float(r[2]), float(r[3]), float(r[4])) for r in rows]


# ---------------- generic backward-paging driver ----------------

def page_back(fetch, start_end_ms: int, cutoff_s: int, stop_at_s: int | None,
              rows: dict[int, tuple], label: str) -> None:
    """Page backwards from start_end_ms until cutoff_s (or stop_at_s coverage), merging into rows."""
    end_ms = start_end_ms
    pages = 0
    while True:
        data = fetch(end_ms)
        pages += 1
        if not data:
            print(f"    {label}: feed exhausted after {pages} pages", flush=True)
            break
        new = 0
        for r in data:
            if r[0] not in rows:
                rows[r[0]] = r
                new += 1
        oldest = data[0][0]
        if pages % 10 == 0 or new == 0:
            print(f"    {label}: page {pages} +{new}, oldest {time.strftime('%Y-%m-%d', time.gmtime(oldest))}", flush=True)
        if oldest <= cutoff_s:
            break
        if stop_at_s is not None and oldest <= stop_at_s:
            break
        if new == 0 and oldest * 1000 >= end_ms:
            break  # no progress
        end_ms = oldest * 1000 - 1
        time.sleep(SLEEP_S)


def load_jsonl(path: Path) -> dict[int, tuple]:
    rows: dict[int, tuple] = {}
    if path.exists():
        with path.open() as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                    rows[int(d["ts"])] = (int(d["ts"]), float(d["open"]), float(d["high"]),
                                          float(d["low"]), float(d["close"]))
                except Exception:  # noqa: BLE001
                    continue
    return rows


def save_jsonl(path: Path, rows: dict[int, tuple]) -> list[tuple]:
    ordered = [rows[k] for k in sorted(rows)]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w") as fh:
        for ts, o, h, l, c in ordered:
            fh.write(json.dumps({"ts": ts, "open": o, "high": h, "low": l, "close": c}) + "\n")
    tmp.replace(path)
    return ordered


def quality(sym: str, tf: str, ordered: list[tuple], tf_s: int) -> None:
    if not ordered:
        print(f"  [{sym} {tf}] EMPTY", flush=True)
        return
    ts = [r[0] for r in ordered]
    assert all(b > a for a, b in zip(ts, ts[1:])), f"{sym} {tf}: ts not strictly increasing"
    gaps = sum(1 for a, b in zip(ts, ts[1:]) if b - a > tf_s)
    big = max((b - a for a, b in zip(ts, ts[1:])), default=0)
    d0 = time.strftime("%Y-%m-%d", time.gmtime(ts[0]))
    d1 = time.strftime("%Y-%m-%d", time.gmtime(ts[-1]))
    days = (ts[-1] - ts[0]) / 86400
    print(f"  [{sym} {tf}] {len(ts)} bars, {d0} -> {d1} ({days:.0f}d), gaps>{tf_s}s: {gaps}, max gap {big/3600:.1f}h", flush=True)


def fetch_symbol_tf(sym: str, tf: str) -> None:
    tf_s, depth_days = PLAN[tf]
    path = OUT_DIR / f"{sym}_{tf}.jsonl"
    rows = load_jsonl(path)
    now = int(time.time())
    cutoff = now - depth_days * 86400
    had_max = max(rows) if rows else None
    had_min = min(rows) if rows else None

    is_crypto = sym in CRYPTO
    try:
        if is_crypto:
            # front top-up: recent 1000 via candles endpoint
            for r in bitget_recent(sym, tf):
                rows.setdefault(r[0], r)
            time.sleep(SLEEP_S)
            fetch = lambda end_ms: bitget_page(sym, tf, end_ms)  # noqa: E731
            # backward from oldest known point (or from recent chunk) to cutoff
            oldest_known = min(rows) if rows else now
            page_back(fetch, oldest_known * 1000 - 1, cutoff, None, rows, f"{sym} {tf} bitget")
            # bridge any middle hole (old file newer-edge to fresh chunk older-edge)
            if had_max is not None:
                ks = sorted(rows)
                for a, b in zip(ks, ks[1:]):
                    if b - a > 50 * tf_s and a >= had_max - tf_s and tf != "D1":
                        page_back(fetch, b * 1000 - 1, cutoff, a, rows, f"{sym} {tf} bridge")
                        break
        else:
            sym_id = TRADFI[sym]
            fetch = lambda end_ms: tradfi_page(sym_id, tf, end_ms)  # noqa: E731
            # tradfi pages are 1000 bars ending at endTime; page from now to cutoff,
            # early-stop when we reach already-cached contiguous history
            page_back(fetch, now * 1000, cutoff,
                      had_max if had_max and had_min is not None and had_min <= cutoff else None,
                      rows, f"{sym} {tf} tradfi")
            if rows and min(rows) > cutoff:
                page_back(fetch, min(rows) * 1000 - 1, cutoff, None, rows, f"{sym} {tf} tradfi-deep")
    except Exception as exc:  # noqa: BLE001
        # Bitget-only: do not fall back to another venue (keeps history pure).
        print(f"  [{sym} {tf}] bitget source failed (no cross-venue fallback): {exc}", flush=True)

    ordered = save_jsonl(path, rows)
    quality(sym, tf, ordered, tf_s)


def main() -> None:
    want = [s.upper() for s in sys.argv[1:]]
    symbols = want or (CRYPTO + list(TRADFI))
    for sym in symbols:
        for tf in PLAN:
            try:
                fetch_symbol_tf(sym, tf)
            except Exception as exc:  # noqa: BLE001
                print(f"  [{sym} {tf}] FAILED (non-blocking): {exc}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
