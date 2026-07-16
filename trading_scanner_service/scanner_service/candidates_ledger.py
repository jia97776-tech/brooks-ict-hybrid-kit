"""Full-candidate ledger for scanner v2 module 8.3 + 14i fields (2026-07-14).

Every scan writes ALL candidates (including non-setup raw signals) to SQLite
so desk verdicts and mechanical outcomes can be compared later.

2026-07-14i: track / model / anomaly columns for dual-rail and multi-desk audit.

Does not place orders. desk_verdict / outcome are filled later by desk tools
or a resolver script — not by auto-trading.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "candidates.db"

# Spec enums (desk fills; machine may pre-suggest only from hard filters)
VERDICTS = frozenset(
    {"trade", "conditional-wait", "do_not_chase", "no_trade", "vetoed"}
)
VETO_REASONS = frozenset(
    {
        "cycle_state",
        "position",
        "session",
        "target_crowded",
        "counter_htf",
        "counter_d1",
        "stale",
        "news",
        "cisd_only",
        "map_tf_not_entry",
        "no_confirm_bar",
        "no_ltf_confirm_bar",
        "chase",
        "c_tier",
        "anomaly",
        "other",
    }
)
TRACKS = frozenset({"cashflow", "asymmetric"})
ANOMALY_CODES = frozenset(
    {
        "none",
        "data_inconsistent",
        "price_jump",
        "cycle_vs_pa",
        "multi_source",
        "visual_dissent",
    }
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scan_id TEXT NOT NULL,
  ts INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  tf TEXT,
  direction TEXT,
  setup_type TEXT NOT NULL DEFAULT 'scanner_map',
  state TEXT,
  pushable INTEGER,
  not_pushable_reason TEXT,
  ltf_status TEXT,
  track TEXT,
  model TEXT,
  anomaly TEXT,
  snapshot TEXT NOT NULL,
  desk_verdict TEXT,
  veto_reason TEXT,
  outcome_r REAL,
  outcome_note TEXT,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cand_scan ON candidates(scan_id);
CREATE INDEX IF NOT EXISTS idx_cand_sym_ts ON candidates(symbol, ts);
CREATE INDEX IF NOT EXISTS idx_cand_verdict ON candidates(desk_verdict);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    """Add 14i columns on existing DBs created before track/model/anomaly."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(candidates)")}
    for col, typ in (
        ("track", "TEXT"),
        ("model", "TEXT"),
        ("anomaly", "TEXT"),
    ):
        if col not in cols:
            conn.execute(f"ALTER TABLE candidates ADD COLUMN {col} {typ}")
    # Index only after columns exist (SCHEMA must not index missing cols)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cand_track ON candidates(track)")


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.commit()
    return conn


def infer_setup_type(c: dict) -> str:
    """Label known types; confluence/drilldown filled when those modules land."""
    if c.get("setup_type"):
        return str(c["setup_type"])
    if c.get("chain") or c.get("setup_type") == "drilldown_chain":
        return "drilldown_chain"
    if c.get("confluence_zone"):
        return "confluence_retest"
    tf = (c.get("tf") or "").upper()
    if tf in {"M1", "M5"}:
        return "scanner_ltf"
    if tf in {"M15", "H4", "H1", "D1"}:
        return "scanner_map"
    return "scanner_map"


def infer_track(c: dict) -> str:
    """Light track prefill — desk may override. Not an auto A-ticket."""
    raw = (c.get("track") or "").strip().lower()
    if raw in TRACKS:
        return raw
    st = infer_setup_type(c)
    if st in {"confluence_retest", "drilldown_chain"}:
        return "asymmetric"
    return "cashflow"


def normalize_anomaly(c: dict) -> str:
    """Machine may only prefill mechanical codes; default none."""
    inconsistent = False
    if c.get("pushable") and not (
        c.get("entry_confirm_bar") or c.get("ltf_confirm_bar") or c.get("confirm_bar")
    ):
        inconsistent = True
    cb = c.get("confirm_bar") or c.get("entry_confirm_bar")
    if isinstance(cb, dict) and cb.get("trigger_price") is not None and c.get("stale_data"):
        inconsistent = True
    direction = str(c.get("direction") or "").upper()
    ref = c.get("entry_ref")
    if ref is None:
        ref = c.get("price")
    try:
        ref_f = float(ref)
    except (TypeError, ValueError):
        ref_f = None
    if ref_f is not None and direction in {"LONG", "SHORT"}:
        for key in ("dol", "dol_runner"):
            target = c.get(key)
            if target is None:
                continue
            try:
                target_f = float(target)
            except (TypeError, ValueError):
                inconsistent = True
                continue
            if direction == "LONG" and target_f <= ref_f:
                inconsistent = True
            if direction == "SHORT" and target_f >= ref_f:
                inconsistent = True

    raw = c.get("anomaly")
    if isinstance(raw, (list, tuple)):
        parts = [str(x).strip() for x in raw if str(x).strip()]
    else:
        s = str(raw or "").strip()
        parts = [x.strip() for x in s.split(",") if x.strip()]
    parts = [x for x in parts if x != "none"]
    if inconsistent and "data_inconsistent" not in parts:
        parts.append("data_inconsistent")
    return ",".join(parts) if parts else "none"


def attach_protocol_fields(candidates: list[dict], model: str | None = None) -> list[dict]:
    """Mutate candidates with track (+ optional model). Returns same list."""
    for c in candidates:
        c["track"] = infer_track(c)
        if model and not c.get("model"):
            c["model"] = model
        c["anomaly"] = normalize_anomaly(c)
    return candidates


def machine_hint_verdict(c: dict) -> tuple[str | None, str | None]:
    """Optional pre-tag from hard machine filters only — desk may override.

    Never emits trade. Only vetoed/no_trade hints for filters already in skill.
    """
    if c.get("symbol", "").upper() in {"ZEC", "EURUSD", "US30", "PEPE"}:
        return "vetoed", "c_tier"
    if c.get("stale_data"):
        return "vetoed", "stale"
    if c.get("news_risk"):
        return "vetoed", "news"
    if c.get("not_pushable_reason") == "chase":
        return "do_not_chase", "chase"
    if c.get("target_crowded"):
        return "do_not_chase", "target_crowded"
    if c.get("counter_d1"):
        return "conditional-wait", "counter_d1"
    if c.get("counter_htf"):
        return "conditional-wait", "counter_htf"
    anom = normalize_anomaly(c)
    if anom and anom != "none":
        return "conditional-wait", "anomaly"
    reason = c.get("not_pushable_reason")
    if reason == "cisd_only":
        return "vetoed", "cisd_only"
    if reason in VETO_REASONS:
        return "conditional-wait", reason
    return None, None


def record_scan_candidates(
    candidates: list[dict],
    scan_id: str,
    now: int | None = None,
    apply_machine_hint: bool = True,
    model: str | None = "scanner",
) -> int:
    """Insert one row per candidate for this scan. Returns rows written."""
    if not candidates:
        return 0
    attach_protocol_fields(candidates, model=model)
    ts = int(now or time.time())
    rows = []
    for c in candidates:
        snap = json.dumps(c, ensure_ascii=False, default=str)
        verdict, veto = (None, None)
        if apply_machine_hint:
            verdict, veto = machine_hint_verdict(c)
        rows.append(
            (
                scan_id,
                ts,
                str(c.get("symbol", "")).upper(),
                c.get("tf"),
                c.get("direction"),
                infer_setup_type(c),
                c.get("state"),
                1 if c.get("pushable") else 0,
                c.get("not_pushable_reason"),
                c.get("ltf_status"),
                infer_track(c),
                c.get("model") or model,
                normalize_anomaly(c),
                snap,
                verdict,
                veto,
                None,
                None,
                ts,
            )
        )
    conn = _connect()
    try:
        conn.executemany(
            """
            INSERT INTO candidates (
              scan_id, ts, symbol, tf, direction, setup_type, state,
              pushable, not_pushable_reason, ltf_status,
              track, model, anomaly, snapshot,
              desk_verdict, veto_reason, outcome_r, outcome_note, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def update_desk_verdict(
    row_id: int,
    desk_verdict: str,
    veto_reason: str | None = None,
    anomaly: str | None = None,
    track: str | None = None,
    model: str | None = None,
) -> None:
    if desk_verdict not in VERDICTS:
        raise ValueError(f"invalid desk_verdict: {desk_verdict}")
    if veto_reason is not None and veto_reason not in VETO_REASONS:
        raise ValueError(f"invalid veto_reason: {veto_reason}")
    if track is not None and track not in TRACKS:
        raise ValueError(f"invalid track: {track}")
    conn = _connect()
    try:
        conn.execute(
            """
            UPDATE candidates SET desk_verdict=?, veto_reason=?,
              anomaly=COALESCE(?, anomaly),
              track=COALESCE(?, track),
              model=COALESCE(?, model)
            WHERE id=?
            """,
            (desk_verdict, veto_reason, anomaly, track, model, row_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_outcome(row_id: int, outcome_r: float, note: str | None = None) -> None:
    conn = _connect()
    try:
        conn.execute(
            "UPDATE candidates SET outcome_r=?, outcome_note=? WHERE id=?",
            (outcome_r, note, row_id),
        )
        conn.commit()
    finally:
        conn.close()


def stats_summary(limit_scans: int = 50) -> dict:
    """Quick counts for ops — not statistical significance."""
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM candidates")
        total = cur.fetchone()[0]
        cur.execute(
            "SELECT desk_verdict, COUNT(*) FROM candidates GROUP BY desk_verdict"
        )
        by_verdict = {k or "null": v for k, v in cur.fetchall()}
        cur.execute(
            "SELECT veto_reason, COUNT(*) FROM candidates "
            "WHERE veto_reason IS NOT NULL GROUP BY veto_reason"
        )
        by_veto = dict(cur.fetchall())
        cur.execute("SELECT track, COUNT(*) FROM candidates GROUP BY track")
        by_track = {k or "null": v for k, v in cur.fetchall()}
        cur.execute(
            "SELECT anomaly, COUNT(*) FROM candidates "
            "WHERE anomaly IS NOT NULL AND anomaly != 'none' GROUP BY anomaly"
        )
        by_anomaly = dict(cur.fetchall())
        cur.execute("SELECT COUNT(DISTINCT scan_id) FROM candidates")
        n_scans = cur.fetchone()[0]
        return {
            "db": str(DB_PATH),
            "n_rows": total,
            "n_scans": n_scans,
            "by_verdict": by_verdict,
            "by_veto": by_veto,
            "by_track": by_track,
            "by_anomaly": by_anomaly,
        }
    finally:
        conn.close()
