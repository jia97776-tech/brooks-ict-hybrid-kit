"""Counterfactual replay of the dormant environment vetoes (2026-07-21, C10 step 1).

structure.py has carried barbwire / climax_risk / micro_channel /
signal_bar_quality / hl_count since 2026-07-11 with the explicit note
"validate on replayed history before wiring". This script does that validation
against the resolved papertrack sample: for every resolved M15 poi_retest row
(win/loss), compute each veto on the M15 bars available AT SIGNAL TIME, then
ask — had this veto blocked the signal, how much R would it have saved?

Wiring criterion (desk adjudication 2026-07-21): a veto may gate only if
blocked losses outweigh killed winners (net_R_saved > 0) on n >= 30, and the
effect isn't carried by a single symbol. Otherwise it stays record-only.

Bars come from data/history/{SYM}_M15.jsonl (static replay files, no network).
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scanner_service.papertrack import _load  # noqa: E402
from scanner_service.sources import Bar  # noqa: E402
from scanner_service.structure import (  # noqa: E402
    barbwire,
    climax_risk,
    hl_count,
    micro_channel,
    signal_bar_quality,
)

HIST = ROOT / "data" / "history"
WINDOW = 40  # bars of context per signal (max detector lookback + ATR is ~15)


def load_hist(symbol: str) -> list[Bar]:
    f = HIST / f"{symbol}_M15.jsonl"
    if not f.exists():
        return []
    out = []
    with f.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            out.append(Bar(ts=int(d["ts"]), open=float(d["open"]), high=float(d["high"]),
                           low=float(d["low"]), close=float(d["close"])))
    return out


def main() -> None:
    rows = [r for r in _load()
            if r.get("outcome") in ("win", "loss")
            and r.get("result_r") is not None
            and r.get("tf") == "M15"
            and r.get("model", "poi_retest") == "poi_retest"]
    hist_cache: dict[str, list[Bar]] = {}
    stats = {k: {"hit": [], "miss": []} for k in
             ("barbwire", "climax", "micro_ct", "sbq_weak")}
    hit_syms = {k: defaultdict(float) for k in stats}
    hl_buckets: dict[str, list[float]] = defaultdict(list)
    covered = uncovered = 0

    for r in rows:
        sym = r["symbol"]
        if sym not in hist_cache:
            hist_cache[sym] = load_hist(sym)
        bars = hist_cache[sym]
        win = [b for b in bars if b.ts <= r["ts"]][-WINDOW:]
        if len(win) < WINDOW:
            uncovered += 1
            continue
        covered += 1
        rr, d = float(r["result_r"]), r["direction"]

        flags = {
            "barbwire": barbwire(win)[0],
            "climax": climax_risk(win, d)[0],
            "micro_ct": (lambda s: s is not None and s != d)(micro_channel(win)[0]),
            "sbq_weak": signal_bar_quality(win, d)[0] == "weak",
        }
        for k, hit in flags.items():
            (stats[k]["hit"] if hit else stats[k]["miss"]).append(rr)
            if hit:
                hit_syms[k][sym] += rr
        hl_buckets[str(min(hl_count(win[-10:], d), 3))].append(rr)

    print(f"sample: resolved M15 poi_retest win/loss rows={len(rows)} "
          f"covered={covered} uncovered={uncovered}\n")
    print(f"{'veto':<10}{'n_hit':>6}{'hitR_avg':>9}{'missR_avg':>10}"
          f"{'net_R_saved':>12}{'killed_wins':>12}{'blocked_loss':>13}  top_sym_share")
    for k, s in stats.items():
        hit, miss = s["hit"], s["miss"]
        if not hit:
            print(f"{k:<10}{0:>6}{'—':>9}{'—':>10}{'—':>12}{'—':>12}{'—':>13}")
            continue
        saved = -sum(hit)
        kw = sum(1 for x in hit if x > 0)
        bl = sum(1 for x in hit if x < 0)
        # concentration: which symbol contributes most of the saved R
        top = max(hit_syms[k].items(), key=lambda kv: abs(kv[1])) if hit_syms[k] else ("-", 0)
        share = (abs(top[1]) / abs(sum(hit)) * 100) if sum(hit) else 0
        print(f"{k:<10}{len(hit):>6}{sum(hit) / len(hit):>9.3f}"
              f"{(sum(miss) / len(miss)) if miss else 0:>10.3f}"
              f"{saved:>12.1f}{kw:>12}{bl:>13}  {top[0]} {share:.0f}%")
    print("\nhl_count bucket (feature, not veto): bucket n avgR")
    for k in sorted(hl_buckets):
        v = hl_buckets[k]
        print(f"  hl={k}{'+' if k == '3' else '':<2} n={len(v):<5} avgR={sum(v) / len(v):+.3f}")


if __name__ == "__main__":
    main()
