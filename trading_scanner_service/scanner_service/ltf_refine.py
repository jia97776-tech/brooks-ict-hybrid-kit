"""Model-B paper-tracking: LTF-confirmation entries for pending sweep signals.

Model A (poi_retest) assumes a limit fill at the POI mid with the stop beyond
the sweep extreme. Model B (ltf_refine) mirrors the user's live playbook:
after the M15 signal, wait for price to re-enter the POI zone, then require an
M5 close-through of the pullback structure (LTF MSS) as the entry trigger,
with the stop beyond that LTF structure plus buffer — tighter stop, higher
planned R, but more noise stop-outs. Both models paper-track in parallel;
after enough samples the stats say which expectancy is actually better.

Run from cron every 5 minutes:
  python3 -m scanner_service.ltf_refine
"""

from __future__ import annotations

import json
import sys
import time

from scanner_service.papertrack import (
    FILL_WINDOW_S,
    RECORD_FIELDS,
    _load,
    _write_all,
    session_of,
)
from scanner_service.structure import SWING_K, average_true_range, find_swings

SL_BUFFER_ATR = 0.25

# Index sweeps often print as a single 1-minute wick with an instant V-reclaim
# (user: "us500/nas 就一分钟一根针扫荡立刻V反收回") — M5 structure forms too
# late there, so indexes refine on M1; everything else on M5.
M1_SYMBOLS = {"US500", "NAS100", "US30"}


def ltf_tf(symbol: str) -> tuple[str, int]:
    if symbol.upper() in M1_SYMBOLS:
        return "M1", 60
    return "M5", 300


def detect_ltf_trigger(parent: dict, m5_bars) -> dict | None:
    """Return a model-B candidate if an LTF confirmation completed, else None."""
    short = parent["direction"] == "SHORT"
    swept = float(parent["swept_level"])
    dol = float(parent["dol"])
    parent_sl = float(parent["sl"])
    bars = [b for b in m5_bars if b.ts > parent["ts"]]
    if len(bars) < 2 * SWING_K + 2:
        return None

    # zone entry: price returns to the swept level from the trade side
    entry_idx = None
    for i, b in enumerate(bars):
        if (short and b.high >= swept) or (not short and b.low <= swept):
            entry_idx = i
            break
    if entry_idx is None:
        return None

    swings = find_swings(bars)
    atr5 = average_true_range(bars)
    opposing = "low" if short else "high"
    for j in range(entry_idx + 1, len(bars)):
        # pullback structure must have formed inside the retest, confirmed before bar j
        levels = [s for s in swings
                  if s.kind == opposing and s.index > entry_idx and s.confirmed_at < j]
        if not levels:
            continue
        level = levels[-1].price
        close = bars[j].close
        triggered = (close < level) if short else (close > level)
        if not triggered:
            continue
        window = bars[entry_idx:j + 1]
        if short:
            ltf_extreme = max(b.high for b in window)
            sl = ltf_extreme + SL_BUFFER_ATR * atr5
            risk, reward = sl - close, close - dol
        else:
            ltf_extreme = min(b.low for b in window)
            sl = ltf_extreme - SL_BUFFER_ATR * atr5
            risk, reward = close - sl, dol - close
        if risk <= 0 or reward <= 0:
            return None  # trigger fired but equation is dead — no valid B entry
        if (short and close >= parent_sl) or (not short and close <= parent_sl):
            return None  # parent idea already invalidated at trigger time
        return {
            "symbol": parent["symbol"], "tf": parent["tf"],
            "direction": parent["direction"], "state": parent["state"],
            "model": "ltf_refine",
            "price": close, "entry_ref": close, "sl": round(sl, 8), "dol": dol,
            "dol_runner": parent.get("dol_runner"),
            "rr": round(reward / risk, 2), "rr_now": round(reward / risk, 2),
            "late": False, "target_crowded": False,
            "swept_level": swept, "mss": parent.get("mss"), "cisd": parent.get("cisd"),
            "reason": f"LTF close-through of pullback structure after POI re-entry (lvl {level})",
            "_trigger_ts": bars[j].ts,
        }
    return None


def refine_pending(router=None, now: int | None = None) -> dict:
    from scanner_service.sources import MarketDataRouter, SourceError

    router = router or MarketDataRouter()
    now = now or int(time.time())
    rows = _load()
    parents = [r for r in rows
               if r.get("outcome") == "pending"
               and r.get("model", "poi_retest") == "poi_retest"
               and r.get("tf") == "M15"
               and not r.get("ltf_refined")
               and r.get("swept_level") is not None
               and now - r["ts"] <= FILL_WINDOW_S]
    emitted, errors = 0, 0
    bar_cache: dict[str, list] = {}
    new_rows: list[dict] = []
    for parent in parents:
        tf, tf_seconds = ltf_tf(parent["symbol"])
        need = min(1000, (now - parent["ts"]) // tf_seconds + 30)
        try:
            if parent["symbol"] not in bar_cache:
                bar_cache[parent["symbol"]] = router.bars(parent["symbol"], tf, int(need))
            cand = detect_ltf_trigger(parent, bar_cache[parent["symbol"]])
        except SourceError:
            errors += 1
            continue
        if cand is None:
            continue
        trigger_ts = cand.pop("_trigger_ts")
        row = {f: cand.get(f) for f in RECORD_FIELDS}
        # a market entry at the trigger close is filled by definition
        row.update({"ts": trigger_ts, "session": session_of(trigger_ts),
                    "model": "ltf_refine", "outcome": "pending", "filled": True,
                    "fill_ts": trigger_ts, "resolve_ts": None, "result_r": None})
        new_rows.append(row)
        parent["ltf_refined"] = True  # one B attempt per parent signal
        emitted += 1
    if new_rows or emitted:
        _write_all(rows + new_rows)
    return {"parents_checked": len(parents), "refined": emitted, "errors": errors}


if __name__ == "__main__":
    print(json.dumps(refine_pending(), ensure_ascii=False), file=sys.stdout)
