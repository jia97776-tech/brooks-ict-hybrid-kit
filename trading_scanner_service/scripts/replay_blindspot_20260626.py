"""Replay 2026-06-26 SOL rally / BTC V-reversal through the rebuilt scanner.

Old system blind spot: bias locked SHORT, zero LONG candidates through a +10%
rally. Test: does the new sweep/MSS/CISD scanner emit LONG candidates during
the move, and at what price relative to the rally?
"""
import calendar
import json
import sys
import time
import urllib.request

sys.path.insert(0, "/home/ubuntu/trading_scanner_service")
from scanner_service.sources import Bar  # noqa: E402
from scanner_service.scanner import scan_symbol  # noqa: E402

WINDOW = 240  # bars fed to scanner per step, mirrors live M15 fetch


def utc(s):
    return calendar.timegm(time.strptime(s, "%Y-%m-%d %H:%M"))


def fetch(symbol, interval, start, end):
    url = (f"https://contract.mexc.com/api/v1/contract/kline/{symbol}"
           f"?interval={interval}&start={start}&end={end}")
    req = urllib.request.Request(url, headers={"User-Agent": "replay-test"})
    d = json.load(urllib.request.urlopen(req, timeout=15)).get("data", {})
    bars = []
    for i, ts in enumerate(d.get("time", [])):
        bars.append(Bar(ts=int(ts), open=float(d["open"][i]), high=float(d["high"][i]),
                        low=float(d["low"][i]), close=float(d["close"][i])))
    return bars


def replay(name, symbol, replay_start, replay_end):
    # fetch enough history so the first replay step has a full window
    bars = fetch(symbol, "Min15", utc(replay_start) - WINDOW * 900 - 3600, utc(replay_end))
    print(f"\n=== {name} ({symbol}) M15 replay {replay_start} -> {replay_end} UTC, {len(bars)} bars ===")
    lo = min(b.low for b in bars if utc(replay_start) <= b.ts <= utc(replay_end))
    hi = max(b.high for b in bars if utc(replay_start) <= b.ts <= utc(replay_end))
    print(f"replay range: low {lo}  high {hi}")
    prev_key = None
    for i in range(len(bars)):
        if bars[i].ts < utc(replay_start) or bars[i].ts > utc(replay_end):
            continue
        window = bars[max(0, i - WINDOW + 1):i + 1]
        c = scan_symbol(symbol, window)
        key = (c["direction"], c["state"], c["mss"], c["cisd"])
        if key != prev_key and c["direction"] != "WAIT":
            t = time.strftime("%m-%d %H:%M", time.gmtime(bars[i].ts))
            print(f"{t}  {c['direction']:5} {c['state']:18} px={c['price']:<9} "
                  f"mss={c['mss']} cisd={c['cisd']} dol={c['dol']} late={c['late']} "
                  f"crowd={c['target_crowded']}")
        prev_key = key


replay("SOL +10% rally (old system: zero long candidates)", "SOL_USDT",
       "2026-06-26 00:00", "2026-06-27 00:00")
replay("BTC V-reversal (user: 没监控到吗)", "BTC_USDT",
       "2026-06-26 00:00", "2026-06-27 00:00")
