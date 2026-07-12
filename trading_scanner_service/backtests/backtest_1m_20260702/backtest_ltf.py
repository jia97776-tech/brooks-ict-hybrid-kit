"""Model-B (ltf_refine) anti-lookahead backtest, paired against the existing
Model-A (poi_retest) backtest in signals_backtest.jsonl.

Reuses PRODUCTION functions verbatim wherever possible:
  - scanner_service.ltf_refine.ltf_tf            (M1 vs M5 routing)
  - scanner_service.structure.SWING_K / find_swings / average_true_range
  - scanner_service.papertrack._resolve_one / session_of  (settlement)

detect_ltf_trigger_bt() below is a byte-for-byte port of
scanner_service.ltf_refine.detect_ltf_trigger with exactly ONE change:
average_true_range() is recomputed on the bar list TRUNCATED to the
candidate trigger bar (bars[:j+1]) instead of on the full bars list handed
to the function. In production this is not lookahead (production only ever
calls detect_ltf_trigger with bars fetched up to "now", i.e. never past the
trigger bar in practice, since it is checked live every 5 minutes) but in an
offline replay we must not let a wider forward-looking bars array leak
future volatility into the stop-loss calc. Everything else (entry-zone
detection, swing selection via confirmed_at < j, structure-break trigger,
parent-invalidation abort, dead-equation abort) is identical to production
and is provably lookahead-safe already: find_swings() only ever looks at a
swing's own local +/-k window, and the `confirmed_at < j` filter guarantees
a swing used to decide bar j never depends on bars at or after j.

For each M15 parent (row) in signals_backtest.jsonl, at most ONE Model-B
attempt is made (one B row output per parent), matching production's
"one ltf_refine attempt per parent" rule. Settlement of a triggered B entry
reuses papertrack._resolve_one against the SAME M15 bar array used for the
parent (this mirrors production exactly: the B row inherits tf="M15" from
its parent, so papertrack.resolve() settles it with M15 bars regardless of
what LTF the trigger fired on).
"""
from __future__ import annotations

import bisect
import json
import random
import sys
import time
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SERVICE_ROOT))
from scanner_service.sources import Bar  # noqa: E402
from scanner_service.structure import SWING_K, average_true_range, find_swings  # noqa: E402
from scanner_service.ltf_refine import SL_BUFFER_ATR, M1_SYMBOLS, ltf_tf  # noqa: E402
from scanner_service import papertrack as pt  # noqa: E402

HERE = Path(__file__).resolve().parent
BARS_DIR = HERE / "bars"
OUT_REPO_DIR = HERE
IN_JSONL = OUT_REPO_DIR / "signals_backtest.jsonl"
OUT_JSONL = OUT_REPO_DIR / "signals_backtest_ltf.jsonl"
REPORT_MD = OUT_REPO_DIR / "report_ltf.md"
SELFCHECK_JSON = OUT_REPO_DIR / "selfcheck_ltf.json"

FILL_WINDOW_S = pt.FILL_WINDOW_S  # 24h, production window for a parent to still be "active"
TF_SECONDS = {"M1": 60, "M5": 300, "M15": 900}

SYMBOLS = [
    "BTC", "ETH", "SOL", "DOGE",
    "XAUUSD", "XAGUSD", "XTIUSD",
    "NAS100", "US500", "US30",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
]


def load_cached_bars(symbol: str, tf: str) -> list[Bar]:
    path = BARS_DIR / f"{symbol}_{tf}.jsonl"
    bars = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            bars.append(Bar(ts=d["ts"], open=d["open"], high=d["high"], low=d["low"],
                             close=d["close"], volume=d.get("volume", 0.0)))
    bars.sort(key=lambda b: b.ts)
    return bars


# ---------------------------------------------------------------------------
# Model-B trigger detection (anti-lookahead port of ltf_refine.detect_ltf_trigger)
# ---------------------------------------------------------------------------

def detect_ltf_trigger_bt(parent: dict, window_bars: list[Bar]) -> tuple[dict | None, str]:
    """window_bars must already be bounded to (parent['ts'], parent['ts']+FILL_WINDOW_S].
    Returns (candidate_or_None, reason_code)."""
    short = parent["direction"] == "SHORT"
    swept = float(parent["swept_level"])
    dol = float(parent["dol"])
    parent_sl = float(parent["sl"])
    bars = window_bars
    if len(bars) < 2 * SWING_K + 2:
        return None, "insufficient_bars_in_window"

    entry_idx = None
    for i, b in enumerate(bars):
        if (short and b.high >= swept) or (not short and b.low <= swept):
            entry_idx = i
            break
    if entry_idx is None:
        return None, "no_zone_reentry"

    swings = find_swings(bars)  # local-window property -> safe to precompute over the whole bounded array
    opposing = "low" if short else "high"
    for j in range(entry_idx + 1, len(bars)):
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
        atr_ltf = average_true_range(bars[:j + 1])  # ANTI-LOOKAHEAD FIX: truncate to <=j
        if short:
            ltf_extreme = max(b.high for b in window)
            sl = ltf_extreme + SL_BUFFER_ATR * atr_ltf
            risk, reward = sl - close, close - dol
        else:
            ltf_extreme = min(b.low for b in window)
            sl = ltf_extreme - SL_BUFFER_ATR * atr_ltf
            risk, reward = close - sl, dol - close
        if risk <= 0 or reward <= 0:
            return None, "dead_equation_at_trigger"
        if (short and close >= parent_sl) or (not short and close <= parent_sl):
            return None, "parent_invalidated_at_trigger"

        # ---- B2 variant SL. Pre-registered from the USER'S LIVE PLAYBOOK
        # (stop beyond the last pullback/retrace structure extreme before the
        # trigger, e.g. live ETH short entry ~1635 / SL 1637), NOT mined from
        # this dataset. Production ltf_refine anchors the stop at the extreme
        # of the WHOLE retest episode (entry_idx..j) which is what makes
        # risk_b ~4.5x wider than Model A; B2 anchors at the last CONFIRMED
        # LTF swing before the trigger bar instead.
        # Anti-lookahead: a swing at index i confirms at i+SWING_K. At trigger
        # time the trigger bar j has just closed, so bars <= j are known ->
        # usable swings must satisfy index < j and confirmed_at <= j.
        anchor_kind = "high" if short else "low"
        anchors = [s for s in swings
                   if s.kind == anchor_kind and s.index < j and s.confirmed_at <= j]
        b2_fallback = False
        if anchors:
            anchor_price = anchors[-1].price
        else:
            # fallback: previous bar's extreme (no confirmed swing in window yet)
            b2_fallback = True
            anchor_price = bars[j - 1].high if short else bars[j - 1].low
        if short:
            sl_b2 = anchor_price + SL_BUFFER_ATR * atr_ltf
            risk_b2 = sl_b2 - close
        else:
            sl_b2 = anchor_price - SL_BUFFER_ATR * atr_ltf
            risk_b2 = close - sl_b2
        b2_valid = risk_b2 > 0  # SL on wrong side of entry -> invalid_sl

        return {
            "trigger_ts": bars[j].ts, "entry_b": close, "sl_b": round(sl, 8),
            "dol_b": dol, "rr_b": round(reward / risk, 4),
            "risk_b": round(risk, 8), "reward_b": round(reward, 8),
            "level_used": level, "ltf_extreme": ltf_extreme, "atr_ltf": atr_ltf,
            "entry_idx": entry_idx, "trigger_idx": j,
            "sl_b2": round(sl_b2, 8), "risk_b2": round(risk_b2, 8),
            "rr_b2": round(reward / risk_b2, 4) if b2_valid else None,
            "b2_valid": b2_valid, "b2_fallback": b2_fallback,
        }, "triggered"
    return None, "no_structure_break"


# ---------------------------------------------------------------------------
# per-parent processing
# ---------------------------------------------------------------------------

def slice_window(ts_list: list[int], bars: list[Bar], lo_excl: int, hi_incl: int) -> list[Bar]:
    lo = bisect.bisect_right(ts_list, lo_excl)
    hi = bisect.bisect_right(ts_list, hi_incl)
    return bars[lo:hi]


def process_parent(parent: dict, ltf_bars: list[Bar], ltf_ts: list[int],
                    ltf_data_start: int, ltf_data_end: int,
                    m15_bars: list[Bar], global_now: int) -> dict:
    ts = parent["ts"]
    window_end_target = ts + FILL_WINDOW_S
    window_bars = slice_window(ltf_ts, ltf_bars, ts, window_end_target)

    # coverage classification
    if ltf_data_start > window_end_target or ltf_data_end <= ts:
        coverage = "none"
    elif ltf_data_start > ts:
        coverage = "partial_history_gap"
    elif ltf_data_end < window_end_target:
        coverage = "partial_tail_truncated"
    else:
        coverage = "full"

    out = {
        "parent_symbol": parent["symbol"], "parent_ts": parent["ts"], "parent_tf": parent["tf"],
        "direction": parent["direction"], "state": parent["state"], "htf_bias": parent.get("htf_bias"),
        "counter_htf": parent.get("counter_htf", False), "target_crowded": parent.get("target_crowded", False),
        "late": parent.get("late", False), "session": parent.get("session"),
        "swept_level": parent.get("swept_level"), "parent_sl": parent.get("sl"),
        "parent_dol": parent.get("dol"), "parent_entry_ref": parent.get("entry_ref"),
        "poi": parent.get("poi"),
        "outcome_a": parent.get("outcome"), "result_r_a": parent.get("result_r"),
        "mfe_r_a": parent.get("mfe_r"), "scalp_r_a": parent.get("scalp_r"),
        "ltf_tf": ltf_tf(parent["symbol"])[0],
        "ltf_window_coverage": coverage,
        "trigger_found": False, "trigger_ts": None,
        "entry_b": None, "sl_b": None, "dol_b": None, "rr_b": None,
        "reason": None,
        "outcome_b": None, "result_r_b": None, "mgmt_r_b": None, "mfe_r_b": None,
        "resolve_ts_b": None,
        "sl_b2": None, "rr_b2": None, "b2_fallback": None,
        "outcome_b2": None, "result_r_b2": None, "mgmt_r_b2": None, "mfe_r_b2": None,
        "resolve_ts_b2": None,
    }

    if coverage == "none":
        out["outcome_b"] = "insufficient_ltf_data"
        out["reason"] = "no_ltf_bars_in_forward_window"
        return out

    cand, reason = detect_ltf_trigger_bt(parent, window_bars)
    out["reason"] = reason

    if cand is None:
        if coverage == "partial_history_gap":
            # can't rule out a trigger inside the un-fetched pre-history_start slice
            out["outcome_b"] = "insufficient_ltf_data"
        elif coverage == "partial_tail_truncated":
            # window may not have run its full 24h yet at data-collection time (now)
            out["outcome_b"] = "pending"
        else:
            out["outcome_b"] = "no_trigger"
        return out

    out["trigger_found"] = True
    out["trigger_ts"] = cand["trigger_ts"]
    out["entry_b"] = cand["entry_b"]
    out["sl_b"] = cand["sl_b"]
    out["dol_b"] = cand["dol_b"]
    out["rr_b"] = cand["rr_b"]

    # settle exactly like production: row inherits parent tf (M15), resolved
    # against M15 bars via the real papertrack._resolve_one
    row = {
        "direction": parent["direction"], "entry_ref": cand["entry_b"], "sl": cand["sl_b"],
        "dol": cand["dol_b"], "rr": cand["rr_b"], "ts": cand["trigger_ts"],
        "filled": True, "fill_ts": cand["trigger_ts"], "mfe_r": None, "scalp_r": None,
        "outcome": "pending", "resolve_ts": None, "result_r": None,
    }
    pt._resolve_one(row, m15_bars, global_now)
    out["outcome_b"] = row["outcome"]
    out["result_r_b"] = row["result_r"]
    out["mgmt_r_b"] = row["scalp_r"]
    out["mfe_r_b"] = row["mfe_r"]
    out["resolve_ts_b"] = row["resolve_ts"]

    # ---- B2 settlement: same trigger/entry/dol, only the SL anchor differs
    out["b2_fallback"] = cand["b2_fallback"]
    if not cand["b2_valid"]:
        out["outcome_b2"] = "invalid_sl"
        return out
    out["sl_b2"] = cand["sl_b2"]
    out["rr_b2"] = cand["rr_b2"]
    row2 = {
        "direction": parent["direction"], "entry_ref": cand["entry_b"], "sl": cand["sl_b2"],
        "dol": cand["dol_b"], "rr": cand["rr_b2"], "ts": cand["trigger_ts"],
        "filled": True, "fill_ts": cand["trigger_ts"], "mfe_r": None, "scalp_r": None,
        "outcome": "pending", "resolve_ts": None, "result_r": None,
    }
    pt._resolve_one(row2, m15_bars, global_now)
    out["outcome_b2"] = row2["outcome"]
    out["result_r_b2"] = row2["result_r"]
    out["mgmt_r_b2"] = row2["scalp_r"]
    out["mfe_r_b2"] = row2["mfe_r"]
    out["resolve_ts_b2"] = row2["resolve_ts"]
    return out


# ---------------------------------------------------------------------------
# self-checks
# ---------------------------------------------------------------------------

def selfcheck_truncation_invariance(results: list[dict], all_ltf: dict, samples: int = 10, seed: int = 13) -> dict:
    """For 10 random triggered B rows, recompute the trigger using a bars
    window that is NOT bounded to the 24h cutoff (i.e. extended with extra
    future bars beyond the true trigger). If detect_ltf_trigger_bt is
    lookahead-safe, trigger_ts/entry_b/sl_b must be identical either way."""
    rng = random.Random(seed)
    triggered = [r for r in results if r["trigger_found"]]
    picks = rng.sample(triggered, min(samples, len(triggered)))
    out = []
    all_ok = True
    for r in picks:
        symbol = r["parent_symbol"]
        tf, bars, ts_list, data_start, data_end = all_ltf[symbol]
        ts = r["parent_ts"]
        # extended window: same start, but stretch the end far past the 24h cutoff
        # (up to the full available data) to prove extra future bars don't change the result
        wide = slice_window(ts_list, bars, ts, min(ts + FILL_WINDOW_S * 3, data_end))
        parent_stub = {
            "direction": r["direction"], "swept_level": r["swept_level"],
            "dol": r["parent_dol"], "sl": r["parent_sl"],
        }
        cand_wide, _ = detect_ltf_trigger_bt(parent_stub, wide)
        # B2 rows may be invalid_sl (sl_b2 None) -- compare accordingly
        sl_b2_wide = (cand_wide["sl_b2"] if (cand_wide and cand_wide["b2_valid"]) else None) if cand_wide else None
        match = (cand_wide is not None and cand_wide["trigger_ts"] == r["trigger_ts"]
                 and cand_wide["entry_b"] == r["entry_b"] and cand_wide["sl_b"] == r["sl_b"]
                 and sl_b2_wide == r["sl_b2"]
                 and (cand_wide["b2_fallback"] if cand_wide else None) == r["b2_fallback"])
        all_ok = all_ok and match
        out.append({
            "symbol": symbol, "parent_ts": ts, "trigger_ts_bounded": r["trigger_ts"],
            "trigger_ts_wide": cand_wide["trigger_ts"] if cand_wide else None,
            "sl_b_bounded": r["sl_b"], "sl_b_wide": cand_wide["sl_b"] if cand_wide else None,
            "sl_b2_bounded": r["sl_b2"], "sl_b2_wide": sl_b2_wide,
            "match": match,
        })
    return {"all_ok": all_ok, "n": len(out), "results": out}


def selfcheck_settlement_prints(results: list[dict], m15_cache: dict, k: int = 5, seed: int = 17) -> list[dict]:
    rng = random.Random(seed)
    settled = [r for r in results if r["outcome_b"] in ("win", "loss", "expired")]
    picks = rng.sample(settled, min(k, len(settled)))
    out = []
    for r in picks:
        bars = m15_cache[r["parent_symbol"]]
        after = [b for b in bars if r["trigger_ts"] < b.ts <= (r["resolve_ts_b"] or bars[-1].ts) + TF_SECONDS["M15"]]
        seq = [{"ts": b.ts, "iso": time.strftime("%Y-%m-%d %H:%M", time.gmtime(b.ts)),
                "o": b.open, "h": b.high, "l": b.low, "c": b.close} for b in after[:40]]
        out.append({
            "symbol": r["parent_symbol"], "direction": r["direction"],
            "trigger_ts": r["trigger_ts"], "entry_b": r["entry_b"], "sl_b": r["sl_b"], "dol_b": r["dol_b"],
            "outcome_b": r["outcome_b"], "result_r_b": r["result_r_b"], "mgmt_r_b": r["mgmt_r_b"],
            "mfe_r_b": r["mfe_r_b"], "resolve_ts_b": r["resolve_ts_b"],
            "bar_sequence": seq,
        })
    return out


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    fetch_report = json.loads((HERE / "fetch_report.json").read_text())
    GLOBAL_NOW = fetch_report["now"]
    ltf_report = json.loads((HERE / "fetch_ltf_report.json").read_text())
    print(f"GLOBAL_NOW = {GLOBAL_NOW} ({time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(GLOBAL_NOW))})")

    m15_cache: dict[str, list[Bar]] = {}
    all_ltf: dict[str, tuple[str, list[Bar], list[int], int, int]] = {}
    for symbol in SYMBOLS:
        m15_cache[symbol] = load_cached_bars(symbol, "M15")
        tf, _ = ltf_tf(symbol)
        bars = load_cached_bars(symbol, tf)
        ts_list = [b.ts for b in bars]
        data_start = bars[0].ts if bars else None
        data_end = bars[-1].ts if bars else None
        all_ltf[symbol] = (tf, bars, ts_list, data_start, data_end)

    parents = [json.loads(l) for l in IN_JSONL.open("r", encoding="utf-8")]
    parents = [r for r in parents if r["tf"] == "M15"]
    print(f"M15 parents to process: {len(parents)}")

    results = []
    t0 = time.time()
    for parent in parents:
        symbol = parent["symbol"]
        tf, bars, ts_list, data_start, data_end = all_ltf[symbol]
        r = process_parent(parent, bars, ts_list, data_start, data_end, m15_cache[symbol], GLOBAL_NOW)
        results.append(r)
    print(f"processed {len(results)} parents in {time.time()-t0:.1f}s")

    with OUT_JSONL.open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {OUT_JSONL}")

    print("running self-check: truncation invariance (10 triggered B rows) ...")
    trunc_check = selfcheck_truncation_invariance(results, all_ltf)
    print(f"  all_ok={trunc_check['all_ok']} n={trunc_check['n']}")

    print("running self-check: settlement spot prints (5 settled B rows) ...")
    settle_check = selfcheck_settlement_prints(results, m15_cache)

    with SELFCHECK_JSON.open("w", encoding="utf-8") as fh:
        json.dump({"truncation_invariance": trunc_check, "settlement_prints": settle_check}, fh,
                   ensure_ascii=False, indent=2)
    print(f"wrote {SELFCHECK_JSON}")

    return results, ltf_report, trunc_check, settle_check, GLOBAL_NOW


if __name__ == "__main__":
    main()
