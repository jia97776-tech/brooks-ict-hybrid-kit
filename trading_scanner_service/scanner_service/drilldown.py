"""Drilldown chain + poi_scaled (scanner v2 §8.2 / §七) — 2026-07-14f.

H4 structure event → M5 same-direction confirm → M1 MSS/CISD entry.
M1 CISD is legal only inside a complete H4+M5 chain (not isolated CISD-only).

poi_scaled: multi-tranche contract metadata; desk must declare before first fill.
Never auto-orders.
"""

from __future__ import annotations

from scanner_service.improve_fill import attach_improve_fill
from scanner_service.sources import Bar
from scanner_service.structure import (
    average_true_range,
    build_confirm_bar,
    cisd_after_sweep,
    detect_latest_sweep,
    find_swings,
    liquidity_targets,
    mss_after_sweep,
    _fmt_bar_time,
    _first_close_through_index,
)

C_TIER = frozenset({"ZEC", "EURUSD", "US30", "PEPE"})
H4_CHAIN_MAX_AGE = 6


def _r(price: float) -> float:
    if abs(price) >= 100:
        return round(price, 2)
    if abs(price) >= 1:
        return round(price, 5)
    return round(price, 8)


def build_poi_scaled_contract(zone: list[float], max_tranches: int = 2) -> dict:
    """Legal multi-tranche metadata — not an order."""
    n = max(1, int(max_tranches))
    return {
        "allowed": True,
        "max_tranches": n,
        "risk_per_tranche_r": round(1.0 / n, 4),
        "total_risk_r": 1.0,
        "window": "in_zone_only",
        "zone": zone,
        "requires_independent_trigger_each": True,
        "shared_invalidate": "entry_tf close through zone",
        "must_declare_before_first": True,
        "forbids_unplanned_add": True,
        "requires_desk_review": True,
        "journal": {
            "setup_id_shared": True,
            "entry_type": "poi_scaled",
            "ticket_r_independent": True,
        },
    }


def _tf_event(bars: list[Bar], tf: str) -> dict | None:
    """Latest sweep + MSS/CISD confirm on this bar set."""
    if len(bars) < 20:
        return None
    swings = find_swings(bars)
    sweep = detect_latest_sweep(bars, swings)
    if sweep is None:
        return None
    direction = "SHORT" if sweep.side == "high" else "LONG"
    mss_level, mss_ok = mss_after_sweep(bars, swings, sweep)
    cisd_level, cisd_ok = cisd_after_sweep(bars, sweep)
    if not (mss_ok or cisd_ok):
        return None

    # Later confirmation wins (same as confirm_bar)
    candidates: list[tuple[int, str, float, str]] = []
    if mss_ok and mss_level is not None:
        idx = _first_close_through_index(bars, mss_level, direction, sweep.extreme_index + 1)
        if idx is not None:
            candidates.append((idx, "MSS", mss_level, "confirmed_swing"))
    if cisd_ok and cisd_level is not None:
        idx = _first_close_through_index(bars, cisd_level, direction, sweep.extreme_index + 1)
        if idx is not None:
            candidates.append((idx, "CISD", cisd_level, "delivery_open"))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    last = candidates[-1]
    kinds = {c[1] for c in candidates}
    if len(kinds) > 1:
        event_type = "MSS+CISD"
    else:
        event_type = last[1]
    # same-bar multi: use last candidate's frozen
    same = [c for c in candidates if c[0] == last[0]]
    frozen = same[-1][2]
    source = same[-1][3]
    cidx = last[0]

    live_confirm = build_confirm_bar(
        bars=bars,
        direction=direction,
        atr=average_true_range(bars),
        mss_level=mss_level,
        mss_ok=mss_ok,
        cisd_level=cisd_level,
        cisd_ok=cisd_ok,
        after_index=sweep.extreme_index,
        tf=tf,
        price=bars[-1].close,
    )
    live_confirm = attach_improve_fill(live_confirm, bars, direction, zone_tf=tf)

    return {
        "type": event_type,
        "level": _r(float(frozen)),
        "bar_time": _fmt_bar_time(bars[cidx].ts),
        "direction": direction,
        "confirm_idx": cidx,
        "confirm_ts": bars[cidx].ts,
        "sweep_extreme": _r(sweep.extreme),
        "swept_level": _r(sweep.swept_level),
        "mss": mss_ok,
        "cisd": cisd_ok,
        "frozen_source": source,
        "live_confirm_bar": live_confirm,
    }


def _h4_still_valid(h4: list[Bar], h4_ev: dict) -> bool:
    direction = h4_ev["direction"]
    frozen = float(h4_ev["level"])
    for b in h4[h4_ev["confirm_idx"] + 1 :]:
        if direction == "LONG" and b.close < frozen:
            return False
        if direction == "SHORT" and b.close > frozen:
            return False
    age = len(h4) - 1 - h4_ev["confirm_idx"]
    return age <= H4_CHAIN_MAX_AGE


def scan_drilldown_chain(
    symbol: str,
    h4: list[Bar],
    m5: list[Bar],
    m1: list[Bar],
) -> list[dict]:
    sym = symbol.upper()
    if sym in C_TIER:
        return []
    h4_ev = _tf_event(h4, "H4")
    if h4_ev is None or not _h4_still_valid(h4, h4_ev):
        return []

    direction = h4_ev["direction"]
    h4_age = len(h4) - 1 - h4_ev["confirm_idx"]
    h4_ts = h4_ev["confirm_ts"]

    m5_ev = _tf_event(m5, "M5")
    if m5_ev is None or m5_ev["direction"] != direction or m5_ev["confirm_ts"] < h4_ts:
        packed = _pack(sym, direction, h4, h4_ev, h4_age, None, None, "awaiting_m5")
        return [packed] if packed is not None else []

    m5_ts = m5_ev["confirm_ts"]
    m1_ev = _tf_event(m1, "M1") if len(m1) >= 20 else None
    if m1_ev is None or m1_ev["direction"] != direction or m1_ev["confirm_ts"] < m5_ts:
        packed = _pack(sym, direction, h4, h4_ev, h4_age, m5_ev, None, "awaiting_m1")
        return [packed] if packed is not None else []

    # Complete chain — M1 CISD-only OK because H4+M5 upstream exist
    status = "chain_complete" if m1_ev.get("live_confirm_bar") else "m1_confirm_stale"
    packed = _pack(sym, direction, h4, h4_ev, h4_age, m5_ev, m1_ev, status)
    return [packed] if packed is not None else []


def _pack(
    sym: str,
    direction: str,
    h4: list[Bar],
    h4_ev: dict,
    h4_age: int,
    m5_ev: dict | None,
    m1_ev: dict | None,
    status: str,
) -> dict | None:
    price = h4[-1].close
    atr_h4 = average_true_range(h4)
    swings = find_swings(h4)
    dol, dol_far, _ = liquidity_targets(h4, swings, direction)

    sl_anchor = float(
        m1_ev["sweep_extreme"] if m1_ev else (m5_ev["sweep_extreme"] if m5_ev else h4_ev["sweep_extreme"])
    )
    # Tighter buffer when M1 present (asymmetric stop)
    buf = atr_h4 * (0.08 if m1_ev else 0.15 if m5_ev else 0.25)
    sl = sl_anchor - buf if direction == "LONG" else sl_anchor + buf

    m1_confirm = m1_ev.get("live_confirm_bar") if m1_ev else None
    entry = float(m1_confirm["trigger_price"]) if m1_confirm else price
    if dol is None:
        return None
    if direction == "LONG":
        risk, reward = entry - sl, dol - entry
    else:
        risk, reward = sl - entry, entry - dol
    if reward <= 0:
        return None
    rr_chain = round(reward / risk, 2) if risk > 0 else None

    z1, z2 = float(h4_ev["swept_level"]), float(h4_ev["sweep_extreme"])
    zone = [_r(min(z1, z2)), _r(max(z1, z2))]
    complete = status == "chain_complete" and m1_confirm is not None
    chase = bool(
        complete
        and "beyond_trigger_extreme" in m1_confirm.get("market_fail", [])
    )
    ltf_status = status

    if chase:
        state, pushable, npr = "CONDITIONAL_READY", False, "chase"
        ltf_status = "chase"
        reason = (
            f"drilldown_chain {direction}: H4→M5→M1 complete but price "
            "already crossed the M1 trigger; do not chase"
        )
    elif complete:
        state, pushable, npr = "READY", True, None
        reason = (
            f"drilldown_chain {direction}: H4→M5→M1 complete; "
            f"expect high stop-out rate, R from H4 target asymmetry"
        )
    elif m5_ev is not None:
        state, pushable, npr = "CONDITIONAL_READY", False, "awaiting_m1"
        reason = f"drilldown_chain {direction}: H4+M5 armed; waiting M1 MSS/CISD"
    else:
        state, pushable, npr = "CONDITIONAL_READY", False, "awaiting_m5"
        reason = f"drilldown_chain {direction}: H4 event live; waiting M5 same-direction confirm"

    chain = {
        "h4_event": {
            "type": h4_ev["type"],
            "level": h4_ev["level"],
            "bar_time": h4_ev["bar_time"],
            "direction": direction,
            "frozen_source": h4_ev.get("frozen_source"),
        },
        "m5_event": (
            {"type": m5_ev["type"], "level": m5_ev["level"], "bar_time": m5_ev["bar_time"]}
            if m5_ev
            else None
        ),
        "m1_event": (
            {"type": m1_ev["type"], "level": m1_ev["level"], "bar_time": m1_ev["bar_time"]}
            if m1_ev
            else None
        ),
        "chain_complete": complete,
        "chain_age_h4_bars": h4_age,
        "chain_status": status,
        "sl_anchor": _r(sl_anchor),
        "dol": _r(dol) if dol is not None else None,
        "dol_source": "H4_untaken_liquidity",
        "rr_chain": rr_chain,
        "risk_disclosure": (
            "高失败率×高单笔R：M1 损被扫是常态成本；"
            "journal 未满 30 笔前仓位不高于常规 2/3"
        ),
        "m1_cisd_ok_in_chain": True,
    }

    return {
        "symbol": sym,
        "tf": "H4",
        "direction": direction,
        "state": state,
        "price": _r(price),
        "setup_type": "drilldown_chain",
        "sweep": True,
        "mss": bool(h4_ev.get("mss")),
        "cisd": bool(h4_ev.get("cisd")),
        "reason": reason,
        "poi": zone,
        "entry_ref": _r(entry),
        "sl": _r(sl),
        "dol": _r(dol) if dol is not None else None,
        "dol_runner": _r(dol) if dol is not None else None,
        "rr": rr_chain,
        "rr_now": rr_chain,
        "rr_from_trigger": rr_chain,
        "late": False,
        "target_crowded": False,
        "swept_level": h4_ev["swept_level"],
        "atr": _r(atr_h4),
        "htf_bias": direction,
        "counter_htf": False,
        "confirm_bar": m1_confirm,
        "ltf_confirm_bar": m1_confirm,
        "entry_confirm_bar": m1_confirm if pushable else None,
        "pushable": pushable,
        "not_pushable_reason": npr,
        "ltf_status": ltf_status,
        "chain": chain,
        "poi_scaled": build_poi_scaled_contract(zone, 2),
        "stale_data": False,
        "news_risk": False,
        "requires_desk_review": True,
    }
