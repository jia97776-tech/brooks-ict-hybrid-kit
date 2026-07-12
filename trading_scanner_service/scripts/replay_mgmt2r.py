"""Replay A-watch style M1/M5 triggers on recent READY parents and compare
two management plans on the same fills:

  Plan A (+1R scale):  at +1R close half, move stop on remainder to BE;
                       remainder exits at DOL or back at BE.
  Plan B (mgmt2r):     at +1R move stop to BE only (conservative BE proxy for
                       "trail to structure from +1R" -- structure trailing
                       would sit wider, so BE overstates wash-outs; B suffers
                       more because it is full size between +1R and +2R);
                       at +2R close half; remainder exits at DOL or BE.

Both plans: original SL before +1R = -1R full. Same-bar double-touch is
resolved conservatively (stop first). Undecided after MAX_BARS LTF bars ->
mark-to-mid exit, flagged expired.

Read-only: loads data/signals.jsonl via papertrack._load(), never writes.
Rerunnable / idempotent.

  python3 scripts/replay_mgmt2r.py
"""

from __future__ import annotations

import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scanner_service.a_watch import CRYPTO, detect_continuation_triggers  # noqa: E402
from scanner_service.ltf_refine import detect_ltf_trigger, ltf_tf  # noqa: E402
from scanner_service.papertrack import _load  # noqa: E402
from scanner_service.sources import MarketDataRouter, SourceError  # noqa: E402

LOOKBACK_S = 4 * 86400
MAX_BARS = 96  # LTF bars before mark-to-mid expiry
BAR_LIMIT = 1000


def sim_plan(plan: str, direction: str, entry: float, sl: float, dol: float,
             bars: list) -> tuple[float, str]:
    """Return (total_R, outcome). bars = LTF bars strictly after trigger.
    Conservative intra-bar ordering: stop side always checked first."""
    short = direction == "SHORT"
    sign = -1.0 if short else 1.0
    risk = abs(entry - sl)
    dol_r = sign * (dol - entry) / risk
    one_r = entry + sign * risk
    two_r = entry + sign * 2 * risk

    hit_1r = False        # +1R reached: A scales half, both move stop to BE
    be_from = None        # BE stop effective from this bar index (next bar —
                          # the stop physically moves after the 1R bar closes;
                          # targets are resting limits so they may fill same bar)
    booked = 0.0          # realized R from the scaled-out half
    half_off = False      # True once half position is closed (A at 1R, B at 2R)

    def touch(bar, level, stop_side: bool) -> bool:
        if short:
            return bar.high >= level if stop_side else bar.low <= level
        return bar.low <= level if stop_side else bar.high >= level

    for i, b in enumerate(bars):
        if not hit_1r:
            if touch(b, sl, True):                      # original stop first
                return -1.0, "sl"
            if dol_r < 1.0 and touch(b, dol, False):
                return dol_r, "dol_full"                # DOL nearer than +1R
            if not touch(b, one_r, False):
                continue
            hit_1r = True
            be_from = i + 1
            if plan == "A":
                booked, half_off = 0.5, True            # half at +1R (limit)
        elif be_from is not None and i >= be_from and touch(b, entry, True):
            # conservative intra-bar order: BE stop before further targets
            return booked, ("be_wash" if booked == 0 else "half_be")
        if plan == "B" and not half_off:
            if dol_r < 2.0 and touch(b, dol, False):
                return dol_r, "dol_full"                # DOL nearer than +2R
            if touch(b, two_r, False):
                booked, half_off = 1.0, True            # half at +2R (limit)
        if half_off and touch(b, dol, False):
            return booked + 0.5 * dol_r, "dol"
    # undecided -> mark-to-mid on last seen bar (expired)
    last = bars[-1] if bars else None
    if last is None:
        return 0.0, "no_bars"
    mid_r = sign * ((last.high + last.low) / 2 - entry) / risk
    size = 0.5 if half_off else 1.0
    if hit_1r:  # BE floor: open part can't lose (stop at entry)
        mid_r = max(mid_r, 0.0)
    return booked + size * mid_r, "expired"


def main() -> None:
    now = int(time.time())
    rows = _load()
    parents, seen = [], set()
    for r in rows:
        if (r.get("state") == "READY"
                and r.get("swept_level") is not None
                and r.get("model", "poi_retest") == "poi_retest"
                and r.get("sl") is not None and r.get("dol") is not None
                and now - r["ts"] <= LOOKBACK_S):
            k = (r["symbol"], r["tf"], r["direction"], r["ts"], r["swept_level"])
            if k not in seen:
                seen.add(k)
                parents.append(r)

    router = MarketDataRouter()
    bar_cache: dict[tuple, list] = {}
    fetch_fail_syms, skipped_depth, fetch_fail_parents = set(), 0, 0
    triggers, trig_seen = [], set()

    for p in parents:
        tf, tf_sec = ltf_tf(p["symbol"])
        ck = (p["symbol"], tf)
        if ck not in bar_cache:
            try:
                bar_cache[ck] = router.bars(p["symbol"], tf, BAR_LIMIT)
            except SourceError as exc:
                bar_cache[ck] = None
                print(f"[warn] bars failed {p['symbol']} {tf}: {exc}", file=sys.stderr)
        bars = bar_cache[ck]
        if bars is None:
            fetch_fail_parents += 1
            fetch_fail_syms.add(p["symbol"])
            continue
        if p["ts"] < bars[0].ts:  # parent older than data depth
            skipped_depth += 1
            continue
        cands = []
        c = detect_ltf_trigger(p, bars)
        if c is not None:
            cands.append(c)
        cands.extend(detect_continuation_triggers(p, bars))
        for c in cands:
            sig = (p["symbol"], p["direction"], c["_trigger_ts"])  # dedupe same bar
            if sig in trig_seen:
                continue
            trig_seen.add(sig)
            sim_bars = [b for b in bars if b.ts > c["_trigger_ts"]][:MAX_BARS]
            if not sim_bars:
                continue
            entry, slv, dol = float(c["price"]), float(c["sl"]), float(c["dol"])
            if abs(entry - slv) <= 0:
                continue
            rec = {"symbol": p["symbol"], "ltf": tf, "model": c["model"],
                   "crypto": p["symbol"].upper() in CRYPTO}
            for plan in ("A", "B"):
                r_val, outc = sim_plan(plan, p["direction"], entry, slv, dol, sim_bars)
                rec[plan] = r_val
                rec[plan + "_out"] = outc
            triggers.append(rec)

    def stats(rs: list[dict], plan: str) -> tuple[int, float, float, int]:
        vals = [t[plan] for t in rs]
        n = len(vals)
        if n == 0:
            return 0, 0.0, 0.0, 0
        wins = sum(1 for v in vals if v > 0)
        exp = sum(1 for t in rs if t[plan + "_out"] == "expired")
        return n, sum(vals) / n, wins / n, exp

    print(f"parents(4d READY poi_retest, deduped) = {len(parents)}")
    print(f"skipped: data-depth = {skipped_depth}, bars-fetch-fail = "
          f"{fetch_fail_parents} (symbols: {sorted(fetch_fail_syms) or '-'})")
    print(f"triggers simulated = {len(triggers)} "
          f"(poi={sum(1 for t in triggers if t['model'] == 'ltf_refine')}, "
          f"cont={sum(1 for t in triggers if t['model'] == 'continuation')})")
    print()
    header = f"{'slice':<22}{'n':>4} | {'A avgR':>8}{'A win%':>8}{'A exp':>6} |" \
             f" {'B avgR':>8}{'B win%':>8}{'B exp':>6}"
    print(header)
    print("-" * len(header))

    slices: list[tuple[str, list[dict]]] = [("ALL", triggers)]
    for tfv in ("M1", "M5"):
        slices.append((f"tf={tfv}", [t for t in triggers if t["ltf"] == tfv]))
    for lbl, flag in (("crypto", True), ("non-crypto", False)):
        slices.append((lbl, [t for t in triggers if t["crypto"] is flag]))
    for lbl, sub in slices:
        na, aa, wa, ea = stats(sub, "A")
        nb, ab, wb, eb = stats(sub, "B")
        print(f"{lbl:<22}{na:>4} | {aa:>8.3f}{wa:>7.0%}{ea:>6} |"
              f" {ab:>8.3f}{wb:>7.0%}{eb:>6}")

    by_sym = defaultdict(list)
    for t in triggers:
        by_sym[t["symbol"]].append(t)
    print("\nper-symbol (n>=3):")
    for sym in sorted(by_sym, key=lambda s: -len(by_sym[s])):
        sub = by_sym[sym]
        if len(sub) < 3:
            continue
        na, aa, _, _ = stats(sub, "A")
        _, ab, _, _ = stats(sub, "B")
        print(f"  {sym:<8} n={na:<3} A={aa:+.3f}  B={ab:+.3f}")


if __name__ == "__main__":
    main()
