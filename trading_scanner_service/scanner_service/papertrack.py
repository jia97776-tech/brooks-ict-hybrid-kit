"""Forward paper-tracking of scanner signals.

Every scan appends new READY/CONDITIONAL_READY candidates to
data/signals.jsonl (deduped against still-pending signals). A resolver run
labels each signal by replaying the bars after signal time with the planned
trade model: limit entry at entry_ref (the POI retest), stop at sl, target
at dol.

Outcomes:
  win        filled, DOL touched before SL           -> R = +rr
  loss       filled, SL touched first (same-bar ties -> loss, conservative) -> R = -1
  no_fill    price ran to DOL without retesting the POI, or fill window expired
  expired    filled but neither SL nor DOL touched within the resolve window
  pending    still open

This measures the expectancy of the mechanical signal AS PLANNED. It is a
sampling tool, not proof of edge.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SIGNALS_FILE = DATA_DIR / "signals.jsonl"

FILL_WINDOW_S = 24 * 3600
RESOLVE_WINDOW_S = 72 * 3600
TF_SECONDS = {"M15": 900, "H4": 14400}
SCALP_R = 2.0  # parallel exit model: same fill, near target at min(2R, DOL)
FLOOR_R = 2.0  # +2R hard-floor variant (2026-07-21 C9): once MFE >= 2R the
               # stop locks to breakeven — floor2r_r = 0.0 instead of -1.0.
               # Measures the desk's +2R hard-floor rule on the machine pool.

RECORD_FIELDS = [
    "symbol", "tf", "direction", "state", "price", "entry_ref", "sl", "dol",
    "dol_runner", "rr", "rr_now", "late", "target_crowded", "swept_level",
    "mss", "cisd", "reason", "news_risk", "news_event", "htf_bias", "counter_htf", "mgmt",
    # environment veto tags (2026-07-21 C10 — record-only, see scanner.py)
    "env_barbwire", "env_climax", "env_micro_ct", "env_sbq", "env_hl",
    # sweep scope + coarse cycle tags (2026-07-21 F2/F3 — record-only)
    "env_sweep_scope", "env_cycle",
]


def _load() -> list[dict]:
    if not SIGNALS_FILE.exists():
        return []
    rows = []
    with SIGNALS_FILE.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def recent_signals(limit: int = 100) -> list[dict]:
    """Return the newest paper signals for the read-only HTTP endpoint."""
    size = max(1, min(int(limit), 1000))
    return _load()[-size:]


def _write_all(rows: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SIGNALS_FILE.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(SIGNALS_FILE)


def _key(row: dict) -> tuple:
    anchor = row.get("swept_level") or row.get("sl") or 0
    return (row["symbol"], row["tf"], row["direction"], round(float(anchor), 4),
            row.get("model", "poi_retest"))


def session_of(ts: int) -> str:
    hour = time.gmtime(ts).tm_hour
    if hour < 7:
        return "asia"
    if hour < 12:
        return "london"
    if hour < 21:
        return "ny"
    return "late"


def record_candidates(candidates: list[dict], now: int | None = None) -> int:
    """Append new trackable candidates; skip keys that are still pending."""
    now = now or int(time.time())
    trackable = [
        c for c in candidates
        if c.get("state") in ("READY", "CONDITIONAL_READY")
        and c.get("sl") is not None and c.get("dol") is not None
        and c.get("entry_ref") is not None
    ]
    if not trackable:
        return 0
    rows = _load()
    pending_keys = {_key(r) for r in rows if r.get("outcome") == "pending"}
    added = 0
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with SIGNALS_FILE.open("a", encoding="utf-8") as fh:
        for c in trackable:
            k = _key(c)
            if k in pending_keys:
                continue
            row = {f: c.get(f) for f in RECORD_FIELDS}
            row.update({"ts": now, "session": session_of(now), "model": c.get("model", "poi_retest"),
                        "outcome": "pending", "filled": False,
                        "fill_ts": None, "resolve_ts": None, "result_r": None,
                        "mfe_r": None, "scalp_r": None, "floor2r_r": None})
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            pending_keys.add(k)
            added += 1
    return added


def _resolve_one(row: dict, bars, now: int) -> None:
    """Mutate row in place if an outcome can be decided from bars after ts."""
    short = row["direction"] == "SHORT"
    entry, sl, dol = float(row["entry_ref"]), float(row["sl"]), float(row["dol"])
    risk = abs(entry - sl)
    after = [b for b in bars if b.ts > row["ts"]]

    def mark_mfe(b):
        # max favorable excursion in R after fill: the management leak a
        # binary SL/DOL outcome hides (e.g. +4R open profit resolved as -1R).
        # Strict accounting (2026-07-10 audit): the fill bar and the stop bar
        # are EXCLUDED by the callers — a limit fills when price falls into the
        # POI, so the fill bar's favorable extreme predates the fill, and the
        # stop bar's extreme may predate the stop (intra-bar order unknowable).
        # Rows resolved before 2026-07-10 carry inflated mfe_r.
        if risk <= 0:
            return
        favorable = (entry - b.low) if short else (b.high - entry)
        mfe = round(max(favorable, 0) / risk, 2)
        if mfe > (row.get("mfe_r") or 0):
            row["mfe_r"] = mfe

    # parallel scalp exit: same fill and stop, target at min(2R, DOL)
    scalp_dist = min(SCALP_R * risk, abs(entry - dol)) if risk > 0 else 0
    scalp_target = (entry - scalp_dist) if short else (entry + scalp_dist)

    def mark_scalp(b, stopped):
        if row.get("scalp_r") is not None or risk <= 0:
            return
        if stopped:  # same-bar ties -> loss, conservative, like the main model
            row["scalp_r"] = -1.0
            return
        hit = (b.low <= scalp_target) if short else (b.high >= scalp_target)
        if hit:
            row["scalp_r"] = round(scalp_dist / risk, 2)

    for b in after:
        if not row["filled"]:
            if b.ts - row["ts"] > FILL_WINDOW_S:
                row.update(outcome="no_fill", resolve_ts=b.ts)
                return
            ran_away = (b.low <= dol) if short else (b.high >= dol)
            touched_entry = (b.high >= entry) if short else (b.low <= entry)
            if ran_away and not touched_entry:
                row.update(outcome="no_fill", resolve_ts=b.ts)
                return
            if touched_entry:
                row["filled"] = True
                row["fill_ts"] = b.ts
                # fill bar excluded from MFE (see mark_mfe)
                # same-bar entry+stop counts as a loss, conservative; a
                # same-bar entry+target is deferred to the next bar
                stopped = (b.high >= sl) if short else (b.low <= sl)
                if stopped:
                    mark_scalp(b, stopped=True)
                    row["floor2r_r"] = -1.0  # same-bar stop: floor never armed
                    row.update(outcome="loss", result_r=-1.0, resolve_ts=b.ts)
                    return
                continue
        else:
            stopped = (b.high >= sl) if short else (b.low <= sl)
            if not stopped:  # stop bar excluded from MFE (see mark_mfe)
                mark_mfe(b)
            target = (b.low <= dol) if short else (b.high >= dol)
            mark_scalp(b, stopped)
            if stopped:  # same-bar SL+DOL -> loss, conservative
                # +2R floor variant: BE instead of -1 once MFE armed the floor
                row["floor2r_r"] = 0.0 if (row.get("mfe_r") or 0) >= FLOOR_R else -1.0
                row.update(outcome="loss", result_r=-1.0, resolve_ts=b.ts)
                return
            if target:
                row["floor2r_r"] = float(row["rr"] or 0)
                row.update(outcome="win", result_r=float(row["rr"] or 0), resolve_ts=b.ts)
                return
            if b.ts - row["fill_ts"] > RESOLVE_WINDOW_S:
                row.update(outcome="expired", resolve_ts=b.ts)
                return
    # no decision from bars; expire on wall clock if far past the windows
    if not row["filled"] and now - row["ts"] > FILL_WINDOW_S + 6 * 3600:
        row.update(outcome="no_fill", resolve_ts=now)
    elif row["filled"] and now - row["fill_ts"] > RESOLVE_WINDOW_S + 6 * 3600:
        row.update(outcome="expired", resolve_ts=now)


def resolve(router=None, now: int | None = None) -> dict:
    from scanner_service.sources import MarketDataRouter, SourceError

    router = router or MarketDataRouter()
    now = now or int(time.time())
    rows = _load()
    pending = [r for r in rows if r.get("outcome") == "pending"]
    resolved, errors = 0, 0
    bar_cache: dict[tuple, list] = {}
    for row in pending:
        tf = row["tf"]
        need = min(1000, (now - row["ts"]) // TF_SECONDS.get(tf, 900) + 10)
        cache_key = (row["symbol"], tf)
        try:
            if cache_key not in bar_cache:
                bar_cache[cache_key] = router.bars(row["symbol"], tf, int(need))
            _resolve_one(row, bar_cache[cache_key], now)
            if row["outcome"] != "pending":
                resolved += 1
        except SourceError:
            errors += 1
    if resolved:
        _write_all(rows)
    return {"pending_before": len(pending), "resolved_now": resolved, "errors": errors}


def stats() -> str:
    rows = _load()
    done = [r for r in rows if r.get("outcome") not in (None, "pending")]
    lines = [f"signals total={len(rows)} resolved={len(done)} pending={len(rows) - len(done)}"]

    def bucket(rs, label):
        fills = [r for r in rs if r["outcome"] in ("win", "loss", "expired")]
        wins = [r for r in rs if r["outcome"] == "win"]
        losses = [r for r in rs if r["outcome"] == "loss"]
        nf = sum(1 for r in rs if r["outcome"] == "no_fill")
        rr_sum = sum(r["result_r"] or 0 for r in fills)
        wr = f"{len(wins)}/{len(wins) + len(losses)}" if (wins or losses) else "0/0"
        exp = f"{rr_sum / len(fills):+.2f}R" if fills else "n/a"
        note = " (small sample!)" if len(fills) < 30 else ""
        lines.append(f"  {label:28} n={len(rs):3} filled={len(fills):3} win/loss={wr:7} "
                     f"no_fill={nf:3} avg={exp}{note}")

    for state in ("READY", "CONDITIONAL_READY"):
        for tf in ("M15", "H4"):
            rs = [r for r in done if r["state"] == state and r["tf"] == tf]
            if rs:
                bucket(rs, f"{state} {tf}")
    for flag in ("late", "target_crowded", "counter_htf"):
        rs = [r for r in done if r.get(flag)]
        if rs:
            bucket(rs, f"flag:{flag}")
    for sess in ("asia", "london", "ny", "late"):
        rs = [r for r in done if r.get("session") == sess]
        if rs:
            bucket(rs, f"session:{sess}")
    for model in sorted({r.get("model", "poi_retest") for r in done}):
        rs = [r for r in done if r.get("model", "poi_retest") == model]
        if rs:
            bucket(rs, f"model:{model}")
    # mfe_r accounting was fixed 2026-07-10 (fill/stop bars excluded); rows
    # resolved before that carry inflated mfe_r and must never enter this stat
    MFE_FIX_TS = 1783987200  # 2026-07-10 00:00 UTC
    strict = [r for r in done if (r.get("resolve_ts") or 0) >= MFE_FIX_TS]
    stale_mfe = len(done) - len(strict)
    leak = [r for r in strict if r["outcome"] == "loss" and (r.get("mfe_r") or 0) >= 2.0]
    losses_with_mfe = [r for r in strict if r["outcome"] == "loss" and r.get("mfe_r") is not None]
    if losses_with_mfe:
        lines.append(f"  losses that saw >=2R open profit first: {len(leak)}/{len(losses_with_mfe)}"
                     " (strict mfe, resolved >= 2026-07-10 only;"
                     f" {stale_mfe} older rows excluded — their mfe_r is inflated)")
    elif stale_mfe:
        lines.append(f"  mfe stat: no strictly-accounted losses yet; {stale_mfe} pre-fix rows excluded (inflated mfe_r)")

    def exit_model_line(rs, label):
        # same fills, two exits: hold to the far DOL vs scalp at min(2R, DOL)
        rs = [r for r in rs if r["outcome"] in ("win", "loss", "expired")]
        if not rs:
            return
        hold = sum(r.get("result_r") or 0 for r in rs) / len(rs)
        scalp = sum(r["scalp_r"] if r.get("scalp_r") is not None else 0 for r in rs) / len(rs)
        lines.append(f"  exit models {label:14} n={len(rs):3}: hold-to-DOL {hold:+.2f}R vs scalp {scalp:+.2f}R")

    exit_model_line(done, "(all fills)")
    exit_model_line([r for r in done if r.get("counter_htf")], "counter_htf")
    exit_model_line([r for r in done if r.get("htf_bias") in ("LONG", "SHORT") and not r.get("counter_htf")], "htf_aligned")
    exit_model_line([r for r in done if r.get("htf_bias") == "NEUTRAL"], "htf_neutral")
    if len(done) < 30:
        lines.append("  样本不足 30，任何比例都只是噪音，先攒数据。")
    return "\n".join(lines)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if cmd == "resolve":
        print(json.dumps(resolve(), ensure_ascii=False))
    elif cmd == "stats":
        print(stats())
    else:
        print("usage: python3 -m scanner_service.papertrack [resolve|stats]", file=sys.stderr)
        sys.exit(2)
