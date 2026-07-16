from __future__ import annotations

from scanner_service.improve_fill import attach_improve_fill
from scanner_service.limit_zone import build_limit_zone
from scanner_service.sources import Bar
from scanner_service.structure import (
    average_true_range,
    build_confirm_bar,
    cisd_after_sweep,
    contracting,
    detect_latest_sweep,
    find_swings,
    liquidity_targets,
    mss_after_sweep,
    untaken_swings,
)

MIN_BARS = 20
SL_BUFFER_ATR = 0.25
CROWDED_ATR = 0.8
MIN_RR = 1.0

# A live feed's forming bar is younger than one tf interval; anything past
# two intervals means the market is closed (weekend/holiday) or the feed is
# frozen — the levels are stale and no live entry can be planned on them.
STALE_FACTOR = 2
TF_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "H1": 3600, "H4": 14400, "D1": 86400, "W1": 604800}


def _round_like(price: float | None) -> float | None:
    if price is None:
        return None
    if abs(price) >= 100:
        return round(price, 2)
    if abs(price) >= 1:
        return round(price, 5)
    return round(price, 8)


def _base(symbol: str, tf: str, price: float | None) -> dict:
    return {
        "symbol": symbol.upper(),
        "tf": tf,
        "direction": "WAIT",
        "state": "ARMED",
        "price": _round_like(price),
        "reason": "",
        "sweep": False,
        "mss": False,
        "cisd": False,
        "poi": None,
        "dol": None,
        "dol_runner": None,
        "sl": None,
        "rr": None,
        "rr_now": None,
        "entry_ref": None,
        "late": False,
        "swept_level": None,
        "mss_level": None,
        "cisd_level": None,
        "target_crowded": False,
        "equal_liquidity": False,
        "atr": None,
        "htf_bias": None,
        "counter_htf": False,
        "mgmt": None,
        "contracting": False,
        "contracting_note": None,
        "d1_state": None,
        "d1_bias": None,
        "counter_d1": False,
        "stale_data": False,
        "confirm_bar": None,
        "rr_from_trigger": None,
        "pushable": False,
        "not_pushable_reason": None,
        "ltf_confirm_bar": None,
        "ltf_tf": None,
        "ltf_status": None,
        "entry_confirm_bar": None,
        "limit_zone": None,
        # SMT confirm (desk evidence; not an auto entry gate)
        "smt": False,
        "smt_partner": None,
        "smt_inverse": False,
        "smt_note": None,
    }


def _apply_staleness(out: dict, bars: list[Bar], tf: str, now: float | None) -> None:
    """Flag frozen feeds; a stale READY must not survive as an entry signal."""
    if now is None or not bars:
        return
    secs = TF_SECONDS.get(tf)
    if not secs:
        return
    age = now - bars[-1].ts
    if age <= STALE_FACTOR * secs:
        return
    out["stale_data"] = True
    if out["state"] == "READY":
        out["state"] = "CONDITIONAL_READY"
    hours = age / 3600
    out["reason"] += (f"; stale feed: last bar opened {hours:.1f}h ago (> {STALE_FACTOR}x{tf}) — "
                      "market closed or feed frozen, levels are old bars, no live entries")


def scan_symbol(
    symbol: str,
    bars: list[Bar],
    tf: str = "M15",
    htf: tuple[str, str] | None = None,
    d1: tuple[str | None, str, str] | None = None,
    now: float | None = None,
) -> dict:
    if len(bars) < MIN_BARS:
        out = _base(symbol, tf, bars[-1].close if bars else None)
        out["reason"] = "not enough bars"
        return out

    swings = find_swings(bars)
    atr = average_true_range(bars)
    price = bars[-1].close
    out = _base(symbol, tf, price)
    out["atr"] = _round_like(atr)
    if d1 is not None:
        out["d1_state"], out["d1_bias"] = d1[0], d1[1]

    is_contracting, contracting_basis = contracting(bars)
    out["contracting"] = is_contracting
    out["contracting_note"] = contracting_basis if is_contracting else None

    sweep = detect_latest_sweep(bars, swings)
    if sweep is None:
        above = untaken_swings(bars, swings, "high")
        below = untaken_swings(bars, swings, "low")
        nearest_above = min((s.price for s in above if s.price > price), default=None)
        nearest_below = max((s.price for s in below if s.price < price), default=None)
        out["reason"] = "no completed sweep trigger; mapped liquidity only"
        out["poi"] = [_round_like(nearest_below), _round_like(nearest_above)]
        if is_contracting:
            out["reason"] += f"; symmetric contraction ({contracting_basis}) — resolution undetermined"
        _apply_staleness(out, bars, tf, now)
        return out

    direction = "SHORT" if sweep.side == "high" else "LONG"
    mss_level, mss_ok = mss_after_sweep(bars, swings, sweep)
    cisd_level, cisd_ok = cisd_after_sweep(bars, sweep)
    dol, runner, equal = liquidity_targets(bars, swings, direction)

    # RR is planned from a retest of the sweep zone (the POI), with the stop
    # beyond the sweep extreme. rr_now is the degraded chase-RR from the
    # current price; the desk uses it to spot do-not-chase situations.
    entry_ref = (sweep.swept_level + sweep.extreme) / 2
    if direction == "SHORT":
        sl = sweep.extreme + SL_BUFFER_ATR * atr
        risk = sl - entry_ref
        reward = (entry_ref - dol) if dol is not None else None
        risk_now, reward_now = sl - price, (price - dol) if dol is not None else None
        poi = [_round_like(sweep.swept_level), _round_like(sweep.extreme)]
    else:
        sl = sweep.extreme - SL_BUFFER_ATR * atr
        risk = entry_ref - sl
        reward = (dol - entry_ref) if dol is not None else None
        risk_now, reward_now = price - sl, (dol - price) if dol is not None else None
        poi = [_round_like(sweep.extreme), _round_like(sweep.swept_level)]

    rr = round(reward / risk, 2) if reward is not None and risk > 0 else None
    rr_now = round(reward_now / risk_now, 2) if reward_now is not None and risk_now > 0 else None
    # mgmt: standard management level at min(2R, DOL) from the POI entry —
    # partial/BE line for HTF-aligned trades, practical target for the rest
    mgmt = None
    if risk > 0:
        mgmt_dist = min(2 * risk, reward) if reward is not None else 2 * risk
        mgmt = (entry_ref - mgmt_dist) if direction == "SHORT" else (entry_ref + mgmt_dist)
    crowded = reward_now is not None and reward_now < CROWDED_ATR * atr
    # late: current price has left the sweep zone, so a fresh market entry
    # here has degraded RR; the plan should be a retest of the POI.
    late = rr_now is not None and rr_now < MIN_RR

    out.update(
        {
            "direction": direction,
            "sweep": True,
            "mss": mss_ok,
            "cisd": cisd_ok,
            "poi": poi,
            "dol": _round_like(dol),
            "dol_runner": _round_like(runner),
            "mgmt": _round_like(mgmt),
            "sl": _round_like(sl),
            "rr": rr,
            "rr_now": rr_now,
            "entry_ref": _round_like(entry_ref),
            "late": late,
            "swept_level": _round_like(sweep.swept_level),
            "mss_level": _round_like(mss_level),
            "cisd_level": _round_like(cisd_level),
            "target_crowded": crowded,
            "equal_liquidity": equal,
        }
    )

    side_word = "high" if sweep.side == "high" else "low"
    confirms = [name for name, ok in (("MSS", mss_ok), ("CISD", cisd_ok)) if ok]
    if dol is None:
        out["state"] = "CONDITIONAL_READY"
        out["reason"] = f"swept prior {side_word} but no untaken liquidity target mapped"
    elif crowded:
        out["state"] = "CONDITIONAL_READY"
        out["target_crowded"] = True
        out["reason"] = f"swept prior {side_word} but price already near target — do not chase"
    elif confirms and rr is not None and rr >= MIN_RR:
        out["state"] = "READY"
        out["reason"] = f"swept prior {side_word} with {'+'.join(confirms)} confirmed on close"
        if late:
            out["reason"] += "; late from current price — plan the POI retest"
    else:
        out["state"] = "CONDITIONAL_READY"
        missing = "MSS/CISD close-through" if not confirms else f"RR {rr} below {MIN_RR}"
        out["reason"] = f"swept prior {side_word}; waiting for {missing}"

    if is_contracting:
        out["reason"] += f"; symmetric contraction ({contracting_basis}) — resolution undetermined, size down"

    # HTF context gate: environment before trigger. An LTF sweep-reversal
    # against confirmed HTF structure can still pay to the NEAR level, but
    # holding it for the far DOL is how open profit becomes -1R.
    if htf is not None:
        bias, basis = htf
        out["htf_bias"] = bias
        if bias in ("LONG", "SHORT") and direction != bias:
            out["counter_htf"] = True
            if out["state"] == "READY":
                out["state"] = "CONDITIONAL_READY"
            out["reason"] += (f"; counter-HTF: H4 bias {bias} ({basis}) — "
                              "scalp to near liquidity only, do not hold for the far DOL")

    # D1 seniority gate: a fresh D1 leg outranks any H4/M15 reversal read —
    # the sweep against it is a pullback in the D1 trend, and the desk default
    # is the with-trend pullback limit plan, not the fade.
    if d1 is not None:
        d1_state, _, d1_basis = d1
        spike_dir = {"spike_up": "LONG", "spike_down": "SHORT"}.get(d1_state)
        if spike_dir and direction != spike_dir:
            out["counter_d1"] = True
            if out["state"] == "READY":
                out["state"] = "CONDITIONAL_READY"
            leg = "bull" if spike_dir == "LONG" else "bear"
            out["reason"] += (f"; counter-D1: fresh D1 {leg} leg ({d1_basis}) — "
                              "this sweep is a pullback in the D1 trend; "
                              "default is the with-trend pullback limit at the structural shelf, not this fade")

    # confirm_bar: mechanical trigger contract for the desk (2026-07-14).
    # Null when MSS/CISD not confirmed on close, TTL expired, or frozen reclaimed.
    # Desk must quote these fields verbatim for any numeric trigger price.
    confirm = build_confirm_bar(
        bars=bars,
        direction=direction,
        atr=atr,
        mss_level=mss_level,
        mss_ok=mss_ok,
        cisd_level=cisd_level,
        cisd_ok=cisd_ok,
        after_index=sweep.extreme_index,
        tf=tf,
        price=price,
        spread_pad=0.0,
    )
    # improve_fill: optional confirm_bar subfield (v2 §六) — entry TF + market_ok only
    confirm = attach_improve_fill(confirm, bars, direction, zone_tf=tf)
    out["confirm_bar"] = confirm
    if confirm is not None and dol is not None:
        trig = confirm["trigger_price"]
        # Desk-stop proxy for RR preview: same scanner SL (sweep extreme ± 0.25 ATR).
        # Real hard SL still re-anchored by desk triple constraint at fill time.
        if direction == "SHORT":
            risk_t = sl - trig
            reward_t = trig - dol
        else:
            risk_t = trig - sl
            reward_t = dol - trig
        out["rr_from_trigger"] = (
            round(reward_t / risk_t, 2) if risk_t > 0 and reward_t is not None else None
        )

    # pushable: desk may actively propose an *executable entry* quoting this
    # confirm_bar's trigger. Map-TF confirms and CISD-only are never pushable.
    cisd_only = bool(cisd_ok and not mss_ok)
    if confirm is None:
        out["pushable"] = False
        out["not_pushable_reason"] = "no_confirm_bar"
    elif "beyond_trigger_extreme" in confirm.get("market_fail", []):
        out["pushable"] = False
        out["not_pushable_reason"] = "chase"
        out["ltf_status"] = "chase"
    elif cisd_only:
        out["pushable"] = False
        out["not_pushable_reason"] = "cisd_only"
    elif confirm.get("role") == "map_confirm":
        out["pushable"] = False
        out["not_pushable_reason"] = "map_tf_not_entry"
    elif out.get("stale_data"):
        out["pushable"] = False
        out["not_pushable_reason"] = "stale_data"
    else:
        # entry_confirm + has MSS (alone or with CISD)
        out["pushable"] = True
        out["not_pushable_reason"] = None
        out["ltf_status"] = "entry_ready" if confirm.get("market_ok") else "entry_pending"

    _apply_staleness(out, bars, tf, now)
    # re-apply pushable after staleness may have flipped state
    if out.get("stale_data") and out.get("pushable"):
        out["pushable"] = False
        out["not_pushable_reason"] = "stale_data"
    # entry_confirm_bar alias when parent itself is entry TF
    if out.get("pushable") and out.get("confirm_bar"):
        out["entry_confirm_bar"] = out["confirm_bar"]

    # limit_zone (v2 §五): deep structure pending-limit arithmetic only.
    # requires_desk_review always — never auto-hang; desk runs full pipeline.
    out["limit_zone"] = build_limit_zone(
        direction=direction,
        bars=bars,
        sweep=sweep,
        atr=atr,
        dol=dol,
        tf=tf,
        htf_bias=out.get("htf_bias"),
        counter_htf=bool(out.get("counter_htf")),
        stale_data=bool(out.get("stale_data")),
        news_risk=bool(out.get("news_risk")),
        spread_pad=0.0,
    )
    return out


# C-tier: machine signals not pushed (papertrack / skill). No LTF spend.
C_TIER_SYMBOLS = frozenset({"ZEC", "EURUSD", "US30", "PEPE"})
# Map TFs that may receive an LTF confirm attach.
MAP_PARENT_TFS = frozenset({"M15", "H4", "H1", "D1"})


def wants_ltf_confirm(parent: dict) -> bool:
    """Whether this map parent is worth an M1/M5 confirm_bar fetch."""
    if not parent:
        return False
    if parent.get("direction") in (None, "WAIT"):
        return False
    if not parent.get("sweep"):
        return False
    if parent.get("symbol", "").upper() in C_TIER_SYMBOLS:
        return False
    if parent.get("stale_data"):
        return False
    if parent.get("target_crowded"):
        return False
    # CISD-only map: never push; skip LTF cost
    if parent.get("cisd") and not parent.get("mss"):
        return False
    tf = (parent.get("tf") or "").upper()
    if tf not in MAP_PARENT_TFS:
        return False  # already entry TF or unknown
    if parent.get("state") not in ("READY", "CONDITIONAL_READY"):
        return False
    return True


def apply_ltf_confirm_bar(
    parent: dict,
    ltf_bars: list[Bar],
    ltf_tf: str = "M5",
    now: float | None = None,
) -> dict:
    """Attach M1/M5 confirm_bar to a map parent and recompute pushable.

    Parent map `confirm_bar` is preserved. Executable entry numbers come from
    `ltf_confirm_bar` / `entry_confirm_bar` when pushable.
    """
    parent = dict(parent)
    parent["ltf_tf"] = ltf_tf
    parent["ltf_confirm_bar"] = None
    parent["entry_confirm_bar"] = None

    if not ltf_bars or len(ltf_bars) < MIN_BARS:
        parent["ltf_status"] = "bars_short"
        parent["pushable"] = False
        parent["not_pushable_reason"] = "no_ltf_confirm_bar"
        return parent

    ltf = scan_symbol(
        parent["symbol"],
        ltf_bars,
        tf=ltf_tf,
        now=now,
    )
    parent["ltf_direction"] = ltf.get("direction")
    parent["ltf_state"] = ltf.get("state")
    parent["ltf_mss"] = ltf.get("mss")
    parent["ltf_cisd"] = ltf.get("cisd")
    parent["ltf_rr_from_trigger"] = ltf.get("rr_from_trigger")

    # No active LTF sweep yet → still waiting, not a direction fight
    if ltf.get("direction") in (None, "WAIT") or not ltf.get("sweep"):
        parent["ltf_status"] = "awaiting_ltf_confirm"
        parent["pushable"] = False
        parent["not_pushable_reason"] = "no_ltf_confirm_bar"
        return parent

    if ltf.get("direction") != parent.get("direction"):
        parent["ltf_status"] = "direction_mismatch"
        parent["pushable"] = False
        parent["not_pushable_reason"] = "no_ltf_confirm_bar"
        return parent

    cb = ltf.get("confirm_bar")
    parent["ltf_confirm_bar"] = cb

    cisd_only = bool(ltf.get("cisd") and not ltf.get("mss"))
    if cb is None:
        parent["pushable"] = False
        parent["not_pushable_reason"] = "no_ltf_confirm_bar"
        parent["ltf_status"] = "awaiting_ltf_confirm"
    elif "beyond_trigger_extreme" in cb.get("market_fail", []):
        parent["pushable"] = False
        parent["not_pushable_reason"] = "chase"
        parent["ltf_status"] = "chase"
    elif cisd_only:
        parent["pushable"] = False
        parent["not_pushable_reason"] = "cisd_only"
        parent["ltf_status"] = "ltf_cisd_only"
    elif cb.get("role") != "entry_confirm":
        parent["pushable"] = False
        parent["not_pushable_reason"] = "map_tf_not_entry"
        parent["ltf_status"] = "ltf_not_entry_role"
    elif ltf.get("stale_data"):
        parent["pushable"] = False
        parent["not_pushable_reason"] = "stale_data"
        parent["ltf_status"] = "ltf_stale"
    else:
        parent["pushable"] = True
        parent["not_pushable_reason"] = None
        parent["entry_confirm_bar"] = cb
        parent["ltf_status"] = "entry_ready" if cb.get("market_ok") else "entry_pending"
        # Prefer LTF proxy RR when available
        if ltf.get("rr_from_trigger") is not None:
            parent["rr_from_trigger"] = ltf.get("rr_from_trigger")

    return parent
