"""Backfill mechanical outcomes into candidates.db (2026-07-21 batch B, C4).

The ledger's stated goal ("compare desk verdicts vs mechanical outcomes",
candidates_ledger.py docstring) was never implemented: 20k+ rows written with
outcome_r 100% NULL. This resolver replays each READY/CONDITIONAL_READY row
with the SAME conventions as papertrack._resolve_one: limit fill at entry_ref
within 24h, then SL-vs-DOL race (same-bar ties -> loss, conservative), 72h
resolve window after fill.

Column semantics written back:
  outcome_r     win -> +rr (reward/risk from geometry), loss -> -1.0
  outcome_note  'win' / 'loss', or terminal non-R states with outcome_r NULL:
                'no_fill' / 'expired' / 'no_geometry' / 'bars_out_of_range'
                (note set => row is never rescanned)
Undecided rows keep (NULL, NULL) and are retried next run.

Cron (hourly, offset from papertrack's :17):
  47 * * * * cd ~/trading_scanner_service && python3 scripts/backfill_candidates_outcome.py --batch 600 >> data/backfill_outcome.log 2>&1
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scanner_service.candidates_ledger import DB_PATH  # noqa: E402
from scanner_service.papertrack import (  # noqa: E402
    FILL_WINDOW_S,
    RESOLVE_WINDOW_S,
    TF_SECONDS,
)

RESOLVABLE_STATES = ("READY", "CONDITIONAL_READY")


def _geometry(row: dict) -> tuple | None:
    """Extract (entry, sl, dol, short, rr) from the snapshot; None if unusable."""
    try:
        snap = json.loads(row["snapshot"])
    except (TypeError, json.JSONDecodeError):
        return None
    entry, sl, dol = snap.get("entry_ref"), snap.get("sl"), snap.get("dol")
    direction = row.get("direction") or snap.get("direction")
    if entry is None or sl is None or dol is None or direction not in ("LONG", "SHORT"):
        return None
    entry, sl, dol = float(entry), float(sl), float(dol)
    short = direction == "SHORT"
    risk, reward = abs(entry - sl), abs(dol - entry)
    if risk <= 0 or reward <= 0:
        return None
    return entry, sl, dol, short, round(reward / risk, 2)


def _replay(row: dict, bars, now: int) -> tuple:
    """Return (outcome_r, note) — (None, None) means undecided, retry later."""
    geo = _geometry(row)
    if geo is None:
        return None, "no_geometry"
    entry, sl, dol, short, rr = geo
    ts = int(row["ts"])
    after = [b for b in bars if b.ts > ts]
    if bars and bars[0].ts > ts + 2 * TF_SECONDS.get(row.get("tf"), 900):
        # the 1000-bar window no longer reaches back to signal time — this row
        # can never be resolved honestly; mark terminal so it is not rescanned
        return None, "bars_out_of_range"

    filled, fill_ts = False, None
    for b in after:
        if not filled:
            if b.ts - ts > FILL_WINDOW_S:
                return None, "no_fill"
            ran_away = (b.low <= dol) if short else (b.high >= dol)
            touched_entry = (b.high >= entry) if short else (b.low <= entry)
            if ran_away and not touched_entry:
                return None, "no_fill"
            if touched_entry:
                filled, fill_ts = True, b.ts
                stopped = (b.high >= sl) if short else (b.low <= sl)
                if stopped:  # same-bar entry+stop -> loss, conservative
                    return -1.0, "loss"
                continue
        else:
            stopped = (b.high >= sl) if short else (b.low <= sl)
            target = (b.low <= dol) if short else (b.high >= dol)
            if stopped:  # same-bar SL+DOL -> loss, conservative
                return -1.0, "loss"
            if target:
                return rr, "win"
            if b.ts - fill_ts > RESOLVE_WINDOW_S:
                return None, "expired"
    if not filled and now - ts > FILL_WINDOW_S + 6 * 3600:
        return None, "no_fill"
    if filled and now - fill_ts > RESOLVE_WINDOW_S + 6 * 3600:
        return None, "expired"
    return None, None  # undecided — retry next run


def run(batch: int) -> dict:
    from scanner_service.sources import MarketDataRouter, SourceError

    router = MarketDataRouter()
    now = int(time.time())
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """SELECT id, ts, symbol, tf, direction, state, snapshot FROM candidates
           WHERE outcome_r IS NULL AND outcome_note IS NULL
             AND state IN (?, ?) AND ts <= ?
           ORDER BY ts LIMIT ?""",
        (*RESOLVABLE_STATES, now - 900, batch),
    ).fetchall()

    bar_cache: dict[tuple, list] = {}
    counts = {"win": 0, "loss": 0, "no_fill": 0, "expired": 0,
              "no_geometry": 0, "bars_out_of_range": 0, "undecided": 0, "errors": 0}
    updates = []
    for r in rows:
        row = dict(r)
        key = (row["symbol"], row["tf"] or "M15")
        if key not in bar_cache:
            try:
                bar_cache[key] = router.bars(key[0], key[1], 1000)
                time.sleep(0.25)  # throttle burst fetches (Gate rate limit)
            except SourceError:
                # negative-cache the failure: without this every row of a
                # failing symbol re-fetched and amplified the rate limit
                bar_cache[key] = None
        if bar_cache[key] is None:
            counts["errors"] += 1
            continue
        outcome_r, note = _replay(row, bar_cache[key], now)
        if note is None:
            counts["undecided"] += 1
            continue
        counts[note] = counts.get(note, 0) + 1
        updates.append((outcome_r, note, row["id"]))
    if updates:
        con.executemany(
            "UPDATE candidates SET outcome_r=?, outcome_note=? WHERE id=?", updates)
        con.commit()
    con.close()
    return {"scanned": len(rows), "written": len(updates), **counts}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=600)
    args = ap.parse_args()
    print(json.dumps({"ts": int(time.time()), **run(args.batch)}, ensure_ascii=False))
