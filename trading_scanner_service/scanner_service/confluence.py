"""Confluence retest setup (scanner v2 §8.1) — 2026-07-14e.

Detects multi-layer HTF/M15 discount|premium confluence zones that were
*swept into* (not ground into), then waits for an M5 signal bar in-zone.

Scanner only labels; desk still runs full pipeline. Never auto-orders.
"""

from __future__ import annotations

from scanner_service.sources import Bar
from scanner_service.drilldown import build_poi_scaled_contract
from scanner_service.structure import (
    average_true_range,
    find_swings,
    htf_bias,
    liquidity_targets,
    signal_bar_quality,
    _fmt_bar_time,
)

# C-tier: do not emit confluence candidates (same desk ban)
C_TIER = frozenset({"ZEC", "EURUSD", "US30", "PEPE"})
MIN_LAYERS = 3
ASIA_HOURS = range(0, 7)       # UTC
LONDON_HOURS = range(7, 12)    # UTC


def _r(price: float) -> float:
    if abs(price) >= 100:
        return round(price, 2)
    if abs(price) >= 1:
        return round(price, 5)
    return round(price, 8)


def _hour_utc(ts: float) -> int:
    import time as _t

    return _t.gmtime(ts).tm_hour


def session_range(bars: list[Bar], hours: range) -> tuple[float, float] | None:
    """High/low of bars whose open hour is in `hours` (last ~2 days of series)."""
    if not bars:
        return None
    # Prefer most recent calendar day that has session bars
    selected: list[Bar] = []
    for b in reversed(bars):
        if _hour_utc(b.ts) in hours:
            selected.append(b)
            if len(selected) >= 24:  # enough for one session
                break
    if len(selected) < 3:
        return None
    return min(b.low for b in selected), max(b.high for b in selected)


def find_active_fvgs(
    bars: list[Bar], direction: str, lookback: int = 40
) -> list[tuple[str, float, float]]:
    """Un-invalidated 3-candle FVGs in trade direction (most recent first)."""
    out: list[tuple[str, float, float]] = []
    if len(bars) < 5:
        return out
    start = max(2, len(bars) - lookback)
    for i in range(len(bars) - 1, start - 1, -1):
        if i < 2:
            break
        first, third = bars[i - 2], bars[i]
        if direction == "LONG" and first.high < third.low:
            lo, hi = first.high, third.low
            if any(b.close < lo for b in bars[i + 1 :]):
                continue  # invalidated by close through
            out.append((f"FVG_bull@{i}", lo, hi))
        elif direction == "SHORT" and first.low > third.high:
            lo, hi = third.high, first.low
            if any(b.close > hi for b in bars[i + 1 :]):
                continue
            out.append((f"FVG_bear@{i}", lo, hi))
        if len(out) >= 4:
            break
    return out


def ote_band(bars: list[Bar], direction: str) -> tuple[float, float] | None:
    """0.618–0.79 retracement of the latest HTF swing leg in trade direction."""
    swings = find_swings(bars)
    if len(swings) < 2:
        return None
    # Walk recent swings for a completed leg
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]
    if not highs or not lows:
        return None
    if direction == "LONG":
        # Impulse up: low then higher high; OTE is pullback from that high toward low
        last_high = highs[-1]
        prior_lows = [s for s in lows if s.index < last_high.index]
        if not prior_lows:
            return None
        leg_low = prior_lows[-1].price
        leg_high = last_high.price
        if leg_high <= leg_low:
            return None
        span = leg_high - leg_low
        # retracement from high: 0.618–0.79 of span down
        hi = leg_high - 0.618 * span
        lo = leg_high - 0.79 * span
        return (lo, hi) if lo < hi else (hi, lo)
    # SHORT: impulse down high→low; OTE pullback up
    last_low = lows[-1]
    prior_highs = [s for s in highs if s.index < last_low.index]
    if not prior_highs:
        return None
    leg_high = prior_highs[-1].price
    leg_low = last_low.price
    if leg_high <= leg_low:
        return None
    span = leg_high - leg_low
    lo = leg_low + 0.618 * span
    hi = leg_low + 0.79 * span
    return (lo, hi) if lo < hi else (hi, lo)


def prev_day_hl(d1: list[Bar]) -> tuple[float, float] | None:
    if len(d1) < 2:
        return None
    prev = d1[-2]
    return prev.low, prev.high


def _overlap(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float] | None:
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    if lo < hi:
        return lo, hi
    return None


def find_confluence_zones(
    layers: list[tuple[str, float, float]], min_count: int = MIN_LAYERS
) -> list[dict]:
    """Greedy multi-layer overlap. Each layer is (name, low, high)."""
    if len(layers) < min_count:
        return []
    zones: list[dict] = []
    for i, seed in enumerate(layers):
        members = [seed]
        z = (seed[1], seed[2])
        for j, other in enumerate(layers):
            if j == i:
                continue
            o = _overlap(z, (other[1], other[2]))
            if o is None:
                continue
            # Keep only if still non-trivial width vs seed
            z = o
            members.append(other)
        names = []
        seen = set()
        for n, _, _ in members:
            base = n.split("@")[0]
            if base not in seen:
                seen.add(base)
                names.append(base)
        if len(names) >= min_count:
            zones.append(
                {
                    "zone": [_r(z[0]), _r(z[1])],
                    "layers": names,
                    "layer_count": len(names),
                }
            )
    # Dedupe near-identical zones
    zones.sort(key=lambda z: (-z["layer_count"], z["zone"][0]))
    deduped: list[dict] = []
    for z in zones:
        if any(
            abs(z["zone"][0] - d["zone"][0]) < 1e-9
            and abs(z["zone"][1] - d["zone"][1]) < 1e-9
            for d in deduped
        ):
            continue
        # Also skip if fully contained in a stronger zone with same layers
        if any(
            z["zone"][0] >= d["zone"][0]
            and z["zone"][1] <= d["zone"][1]
            and set(z["layers"]).issubset(set(d["layers"]))
            for d in deduped
        ):
            continue
        deduped.append(z)
        if len(deduped) >= 3:
            break
    return deduped


def swept_into_zone(
    bars: list[Bar], zone: tuple[float, float], direction: str, lookback: int = 30
) -> tuple[bool, float | None, str | None]:
    """Sweep-style entry into zone: pierce outside liquidity then close back in/through zone.

    LONG: wick below zone.low then close back above zone.low (buy-side sweep into discount).
    SHORT: wick above zone.high then close back below zone.high.
    """
    if len(bars) < 5:
        return False, None, None
    zlo, zhi = zone
    start = max(0, len(bars) - lookback)
    for i in range(start, len(bars)):
        b = bars[i]
        if direction == "LONG":
            if b.low < zlo and b.close > zlo:
                return True, b.low, _fmt_bar_time(b.ts)
        else:
            if b.high > zhi and b.close < zhi:
                return True, b.high, _fmt_bar_time(b.ts)
    return False, None, None


def m5_signal_in_zone(
    m5: list[Bar],
    zone: tuple[float, float],
    direction: str,
    not_before: str | None = None,
) -> dict | None:
    """Return the first live M5 signal in-zone; never roll the trigger forward."""
    if len(m5) < 5:
        return None
    zlo, zhi = zone
    signal_idx = None
    grade = note = ""
    for idx in range(4, len(m5)):
        b = m5[idx]
        bar_time = _fmt_bar_time(b.ts)
        if not_before is not None and bar_time < not_before:
            continue
        if b.high < zlo or b.low > zhi:
            continue
        grade, note = signal_bar_quality(m5[: idx + 1], direction)
        if grade != "weak":
            signal_idx = idx
            break
    if signal_idx is None:
        return None

    b = m5[signal_idx]
    atr = average_true_range(m5[: signal_idx + 1])
    buf = max(0.25 * atr, 0.0)
    if direction == "LONG":
        trigger = b.high + buf
        side = "buy_stop_above_high"
    else:
        trigger = b.low - buf
        side = "sell_stop_below_low"
    price = m5[-1].close
    fails = []
    if not (zlo <= price <= zhi):
        fails.append("price_outside_zone")
    later_bars = m5[signal_idx + 1 :]
    crossed_trigger = (
        direction == "LONG"
        and (price > trigger or any(x.high > trigger for x in later_bars))
    ) or (
        direction == "SHORT"
        and (price < trigger or any(x.low < trigger for x in later_bars))
    )
    if crossed_trigger:
        fails.append("beyond_trigger_extreme")

    def rr(x: float) -> float:
        return _r(x)

    return {
        "tf": "M5",
        "grade": grade,
        "grade_note": note,
        "bar_time": _fmt_bar_time(b.ts),
        "open": rr(b.open),
        "high": rr(b.high),
        "low": rr(b.low),
        "close": rr(b.close),
        "buffer": rr(buf),
        "buffer_calc": f"max(0.25*ATR={0.25 * atr:.5g}, spread_pad=0.0)",
        "trigger_price": rr(trigger),
        "trigger_side": side,
        "market_ok": not fails,
        "market_fail": fails,
    }


def build_layers(
    direction: str,
    m15: list[Bar],
    h4: list[Bar],
    d1: list[Bar],
) -> list[tuple[str, float, float]]:
    """Assemble named intervals for confluence search."""
    layers: list[tuple[str, float, float]] = []
    atr15 = average_true_range(m15) if m15 else 1.0
    pad = 0.15 * atr15

    asia = session_range(m15, ASIA_HOURS)
    if asia:
        lo, hi = asia
        if direction == "LONG":
            layers.append(("asia_range_low", lo - pad, lo + pad))
        else:
            layers.append(("asia_range_high", hi - pad, hi + pad))

    lon = session_range(m15, LONDON_HOURS)
    if lon:
        lo, hi = lon
        if direction == "LONG":
            layers.append(("london_range_low", lo - pad, lo + pad))
        else:
            layers.append(("london_range_high", hi - pad, hi + pad))

    for name, lo, hi in find_active_fvgs(m15, direction):
        layers.append((f"M15_{name.split('@')[0]}", lo, hi))
    for name, lo, hi in find_active_fvgs(h4, direction):
        layers.append((f"H4_{name.split('@')[0]}", lo, hi))

    ote = ote_band(h4 if len(h4) >= 20 else m15, direction)
    if ote:
        layers.append(("OTE_618_79", ote[0], ote[1]))

    pd = prev_day_hl(d1)
    if pd:
        plo, phi = pd
        if direction == "LONG":
            layers.append(("prev_day_low", plo - pad, plo + pad))
        else:
            layers.append(("prev_day_high", phi - pad, phi + pad))

    return layers


def scan_confluence_retest(
    symbol: str,
    m15: list[Bar],
    h4: list[Bar],
    d1: list[Bar],
    m5: list[Bar],
) -> list[dict]:
    """Return 0..N confluence_retest candidates for one symbol."""
    sym = symbol.upper()
    if sym in C_TIER:
        return []
    if len(m15) < 30 or len(h4) < 20:
        return []

    bias, bias_basis = htf_bias(h4)
    # Only with-trend confluence (against HTF is not this setup)
    if bias not in ("LONG", "SHORT"):
        return []

    direction = bias
    layers = build_layers(direction, m15, h4, d1)
    if len(layers) < MIN_LAYERS:
        return []

    zones = find_confluence_zones(layers, MIN_LAYERS)
    if not zones:
        return []

    price = m15[-1].close
    atr = average_true_range(m15)
    swings = find_swings(m15)
    dol_near, dol_far, _ = liquidity_targets(m15, swings, direction)

    out: list[dict] = []
    for z in zones:
        zlo, zhi = z["zone"]
        # Prefer zones near price (within 3 ATR) — not ancient levels far away
        mid = 0.5 * (zlo + zhi)
        if abs(price - mid) > 3.0 * atr:
            continue
        swept, sweep_ext, sweep_time = swept_into_zone(m15, (zlo, zhi), direction)
        if not swept:
            continue

        sig = (
            m5_signal_in_zone(m5, (zlo, zhi), direction, not_before=sweep_time)
            if m5
            else None
        )
        # State machine
        chase = bool(
            sig is not None
            and "beyond_trigger_extreme" in sig.get("market_fail", [])
        )
        if sig is None:
            state = "CONDITIONAL_READY"
            reason = (
                f"confluence_retest {direction}: {z['layer_count']} layers, "
                f"swept into zone; waiting M5 signal bar in zone"
            )
            pushable = False
            npr = "awaiting_signal_bar"
        elif chase:
            state = "CONDITIONAL_READY"
            reason = (
                f"confluence_retest {direction}: M5 signal bar confirmed but price "
                "already crossed the trigger; do not chase"
            )
            pushable = False
            npr = "chase"
        elif sig["grade"] == "weak":
            state = "CONDITIONAL_READY"
            reason = (
                f"confluence_retest {direction}: zone ready but M5 signal_bar weak"
            )
            pushable = False
            npr = "signal_bar_weak_or_chase"
        else:
            state = "READY"
            reason = (
                f"confluence_retest {direction}: {z['layer_count']} layers + "
                f"M5 signal_bar {sig['grade']}"
            )
            # Quotable numbers only — not auto A-ticket
            pushable = True
            npr = None

        # SL anchor: beyond sweep extreme of the zone entry
        if direction == "LONG":
            sl_anchor = sweep_ext if sweep_ext is not None else zlo
            sl = sl_anchor - 0.25 * atr
        else:
            sl_anchor = sweep_ext if sweep_ext is not None else zhi
            sl = sl_anchor + 0.25 * atr

        entry_ref = mid
        if dol_near is not None:
            if direction == "LONG":
                risk = entry_ref - sl
                reward = dol_near - entry_ref
            else:
                risk = sl - entry_ref
                reward = entry_ref - dol_near
            rr = round(reward / risk, 2) if risk > 0 else None
        else:
            rr = None

        cand = {
            "symbol": sym,
            "tf": "M15",
            "direction": direction,
            "state": state,
            "price": _r(price),
            "setup_type": "confluence_retest",
            "sweep": True,
            "mss": False,
            "cisd": False,
            "reason": reason + f"; htf={bias_basis}",
            "poi": [_r(zlo), _r(zhi)],
            "entry_ref": _r(entry_ref),
            "sl": _r(sl),
            "dol": _r(dol_near) if dol_near is not None else None,
            "dol_runner": _r(dol_far) if dol_far is not None else None,
            "rr": rr,
            "rr_now": None,
            "late": False,
            "target_crowded": False,
            "swept_level": _r(zlo if direction == "LONG" else zhi),
            "atr": _r(atr),
            "htf_bias": bias,
            "counter_htf": False,
            "confirm_bar": None,
            "ltf_confirm_bar": None,
            "entry_confirm_bar": sig if pushable else None,
            "pushable": bool(pushable and sig is not None),
            "not_pushable_reason": npr if not (pushable and sig is not None) else None,
            "ltf_status": "chase" if chase else ("signal_bar" if sig else "awaiting_signal_bar"),
            "confluence_zone": {
                "zone": [_r(zlo), _r(zhi)],
                "layers": z["layers"],
                "layer_count": z["layer_count"],
                "swept_into_zone": True,
                "sweep_time": sweep_time,
                "sweep_extreme": _r(sweep_ext) if sweep_ext is not None else None,
                "htf_structure": bias_basis,
                "trigger_condition": "M5_signal_bar_close_in_zone",
                "signal_bar": sig,
                "dol_near": _r(dol_near) if dol_near is not None else None,
                "dol_far": _r(dol_far) if dol_far is not None else None,
                "requires_desk_review": True,
            },
            "stale_data": False,
            "news_risk": False,
            "requires_desk_review": True,
            # §七: multi-tranche only inside confluence zone; desk must declare first
            "poi_scaled": build_poi_scaled_contract([_r(zlo), _r(zhi)], max_tranches=2),
        }
        # If signal_bar present, also expose trigger via confirm-like alias for desk
        if sig is not None:
            cand["rr_from_trigger"] = None
            if dol_near is not None and sig.get("trigger_price") is not None:
                tp = sig["trigger_price"]
                if direction == "LONG":
                    risk_t = tp - sl
                    reward_t = dol_near - tp
                else:
                    risk_t = sl - tp
                    reward_t = tp - dol_near
                if risk_t > 0:
                    cand["rr_from_trigger"] = round(reward_t / risk_t, 2)

        out.append(cand)
    return out
