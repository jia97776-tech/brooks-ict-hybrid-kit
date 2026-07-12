from __future__ import annotations

from scanner_service.sources import Bar
from scanner_service.structure import (
    average_true_range,
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

    _apply_staleness(out, bars, tf, now)
    return out
