"""Mechanical market-structure layer.

Definitions follow the smc-mechanical-definitions used by the desk skill:
swings confirm only after k bars on both sides, breaks count on closes
(wicks alone are sweeps, not breaks), and targets are real untaken swing
liquidity rather than arithmetic projections.
"""

from __future__ import annotations

from dataclasses import dataclass

from scanner_service.sources import Bar

SWING_K = 2


@dataclass(frozen=True)
class Swing:
    index: int
    price: float
    kind: str  # "high" | "low"

    @property
    def confirmed_at(self) -> int:
        return self.index + SWING_K


@dataclass(frozen=True)
class Sweep:
    side: str  # "high" | "low"
    swept_level: float
    extreme: float
    extreme_index: int


def find_swings(bars: list[Bar], k: int = SWING_K) -> list[Swing]:
    swings: list[Swing] = []
    for i in range(k, len(bars) - k):
        high = bars[i].high
        if all(high > bars[j].high for j in range(i - k, i + k + 1) if j != i):
            swings.append(Swing(i, high, "high"))
        low = bars[i].low
        if all(low < bars[j].low for j in range(i - k, i + k + 1) if j != i):
            swings.append(Swing(i, low, "low"))
    return swings


def average_true_range(bars: list[Bar], period: int = 14) -> float:
    if len(bars) < 2:
        return max(abs(bars[-1].close) * 0.001, 1e-9) if bars else 1e-9
    window = bars[-(period + 1):]
    ranges = []
    for prev, cur in zip(window, window[1:]):
        ranges.append(max(cur.high - cur.low, abs(cur.high - prev.close), abs(cur.low - prev.close)))
    atr = sum(ranges) / len(ranges)
    return max(atr, abs(bars[-1].close) * 1e-6, 1e-9)


def _broken_by_close(bars: list[Bar], level: float, side: str, start: int, end: int) -> bool:
    """True if any close in bars[start:end] traded through the level."""
    for j in range(start, end):
        close = bars[j].close
        if side == "high" and close > level:
            return True
        if side == "low" and close < level:
            return True
    return False


def untaken_swings(bars: list[Bar], swings: list[Swing], kind: str) -> list[Swing]:
    """Swings whose level has not been traded through (by wick) since confirmation."""
    result = []
    for swing in swings:
        if swing.kind != kind:
            continue
        taken = False
        for j in range(swing.confirmed_at + 1, len(bars)):
            if kind == "high" and bars[j].high > swing.price:
                taken = True
                break
            if kind == "low" and bars[j].low < swing.price:
                taken = True
                break
        if not taken:
            result.append(swing)
    return result


def _side_sweep(bars: list[Bar], swings: list[Swing], side: str, lookback: int = 16) -> Sweep | None:
    """Still-active liquidity sweep on one side of the recent window.

    A sweep-high: the recent extreme wicked above a swing high that was
    confirmed earlier and never closed above before, and price currently
    closes back below that level with no acceptance above it since the
    extreme. Mirror for sweep-low.
    """
    if len(bars) < lookback + SWING_K + 1:
        return None
    start = len(bars) - lookback
    last_close = bars[-1].close

    if side == "high":
        idx = max(range(start, len(bars)), key=lambda i: bars[i].high)
        extreme = bars[idx].high
        swept = [
            s.price
            for s in swings
            if s.kind == "high"
            and s.confirmed_at < idx
            and s.price < extreme
            and not _broken_by_close(bars, s.price, "high", s.confirmed_at + 1, idx)
        ]
        if swept:
            level = max(swept)
            if last_close < level and not _broken_by_close(bars, level, "high", idx + 1, len(bars)):
                return Sweep("high", level, extreme, idx)
        return None

    idx = min(range(start, len(bars)), key=lambda i: bars[i].low)
    extreme = bars[idx].low
    swept = [
        s.price
        for s in swings
        if s.kind == "low"
        and s.confirmed_at < idx
        and s.price > extreme
        and not _broken_by_close(bars, s.price, "low", s.confirmed_at + 1, idx)
    ]
    if swept:
        level = min(swept)
        if last_close > level and not _broken_by_close(bars, level, "low", idx + 1, len(bars)):
            return Sweep("low", level, extreme, idx)
    return None


def detect_latest_sweep(bars: list[Bar], swings: list[Swing], lookback: int = 16) -> Sweep | None:
    """Latest still-active liquidity sweep in the recent window (either side)."""
    high_sweep = _side_sweep(bars, swings, "high", lookback)
    low_sweep = _side_sweep(bars, swings, "low", lookback)
    if high_sweep and low_sweep:
        return high_sweep if high_sweep.extreme_index > low_sweep.extreme_index else low_sweep
    return high_sweep or low_sweep


def mss_after_sweep(bars: list[Bar], swings: list[Swing], sweep: Sweep) -> tuple[float | None, bool]:
    """Market structure shift confirmation after a sweep.

    Sweep-high -> bearish MSS: a close below the last swing low confirmed
    before the sweep extreme. Mirror for sweep-low.
    """
    opposing = "low" if sweep.side == "high" else "high"
    prior = [s for s in swings if s.kind == opposing and s.confirmed_at < sweep.extreme_index]
    if not prior:
        return None, False
    level = prior[-1].price
    confirmed = _broken_by_close(bars, level, opposing, sweep.extreme_index + 1, len(bars))
    return level, confirmed


def cisd_after_sweep(bars: list[Bar], sweep: Sweep) -> tuple[float | None, bool]:
    """Change in state of delivery: close through the open of the last
    same-direction delivery series that ran into the sweep extreme."""
    if sweep.side == "high":
        is_leg_bar = lambda b: b.close > b.open
        side = "low"
    else:
        is_leg_bar = lambda b: b.close < b.open
        side = "high"

    idx = sweep.extreme_index
    if not is_leg_bar(bars[idx]):
        idx -= 1
    series_start = None
    while idx >= 0 and is_leg_bar(bars[idx]):
        series_start = idx
        idx -= 1
    if series_start is None:
        return None, False
    level = bars[series_start].open
    confirmed = _broken_by_close(bars, level, side, sweep.extreme_index + 1, len(bars))
    return level, confirmed


def _ema(values: list[float], period: int = 20) -> list[float]:
    k = 2.0 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def contracting(bars: list[Bar], swing_count: int = 4) -> tuple[bool, str]:
    """Detect a symmetric contraction: the most recent confirmed swing lows
    rising while the most recent confirmed swing highs are falling, over the
    same window. This is a distinct read from a trending channel or a flat
    trading range — direction of resolution is genuinely undetermined, so the
    desk should treat it as a coin-flip squeeze, not a continuation or a fade.

    Compares the first vs. last swing in the window rather than requiring every
    consecutive step to be monotonic — real swing sequences have single-point
    noise (e.g. a marginal new high inside an otherwise falling ceiling), and a
    strict step-by-step check breaks on that noise. swing_count=4 is the
    smallest window that reproduced the live WLD 07-04 case this was built from
    (n=3 misses it on ceiling noise, n=5 pulls in an older unrelated swing).

    Returns (is_contracting, basis).
    """
    swings = find_swings(bars)
    highs = [s for s in swings if s.kind == "high"][-swing_count:]
    lows = [s for s in swings if s.kind == "low"][-swing_count:]
    if len(highs) < swing_count or len(lows) < swing_count:
        return False, "not enough confirmed swings"

    highs_falling = highs[-1].price < highs[0].price
    lows_rising = lows[-1].price > lows[0].price
    if highs_falling and lows_rising:
        basis = (
            f"lows {lows[0].price:g}->{lows[-1].price:g} rising, "
            f"highs {highs[0].price:g}->{highs[-1].price:g} falling"
        )
        return True, basis
    return False, "no symmetric contraction"


def d1_spike(bars: list[Bar], n: int = 5, lookback: int = 20) -> tuple[str | None, str]:
    """Fresh strong D1 leg — the layer the H4-derived htf_bias cannot see.

    A reversal candidate fired against this state is a pullback in the D1
    trend, not a reversal (SOL 07-04: H4 SHORT READY against five straight D1
    bull closes out of a six-week base). Mechanical read on COMPLETED bars
    only (the last bar is usually still forming): at least n-1 of the last n
    completed bars close directionally, the net close-to-close move over the
    window is at least 1.2x ATR, and the last completed close is the extreme
    close of the lookback window (fresh ground, not a mid-range wiggle).

    Returns (state, basis) where state is "spike_up" | "spike_down" | None.
    """
    completed = bars[:-1] if len(bars) >= 2 else list(bars)
    if len(completed) < max(lookback, n + 1):
        return None, "not enough completed D1 bars"
    window = completed[-n:]
    closes = [b.close for b in completed]
    atr = average_true_range(completed)
    bull = sum(1 for b in window if b.close > b.open)
    bear = sum(1 for b in window if b.close < b.open)
    net = closes[-1] - closes[-n - 1]
    if bull >= n - 1 and net >= 1.2 * atr and closes[-1] == max(closes[-lookback:]):
        return "spike_up", f"{bull}/{n} bull closes, net +{net:g} >= 1.2xATR({atr:g}), highest close of {lookback}"
    if bear >= n - 1 and -net >= 1.2 * atr and closes[-1] == min(closes[-lookback:]):
        return "spike_down", f"{bear}/{n} bear closes, net {net:g} >= 1.2xATR({atr:g}), lowest close of {lookback}"
    return None, "no fresh D1 leg"


def htf_bias(bars: list[Bar], lookback: int = 16) -> tuple[str, str]:
    """Directional bias of a higher timeframe, for gating LTF countertrend signals.

    Priority 1: a still-active sweep whose reversal is already confirmed by an
    MSS or CISD close-through — the most recent confirmed one sets the bias
    (sweep of lows -> LONG, sweep of highs -> SHORT).
    Priority 2: EMA20 always-in proxy — 8 of the last 10 closes on one side of
    the EMA with the last close agreeing.
    Returns (bias, basis) where bias is "LONG" | "SHORT" | "NEUTRAL".
    """
    if len(bars) < lookback + SWING_K + 1:
        return "NEUTRAL", "not enough HTF bars"
    swings = find_swings(bars)
    confirmed: list[tuple[int, str, Sweep]] = []
    for side, direction in (("high", "SHORT"), ("low", "LONG")):
        sweep = _side_sweep(bars, swings, side, lookback)
        if sweep is None:
            continue
        _, mss_ok = mss_after_sweep(bars, swings, sweep)
        _, cisd_ok = cisd_after_sweep(bars, sweep)
        if mss_ok or cisd_ok:
            confirmed.append((sweep.extreme_index, direction, sweep))
    if confirmed:
        confirmed.sort()
        _, direction, sweep = confirmed[-1]
        return direction, f"confirmed {sweep.side}-sweep reversal off {sweep.swept_level:g}"

    closes = [b.close for b in bars]
    ema = _ema(closes)
    above = sum(1 for c, e in zip(closes[-10:], ema[-10:]) if c > e)
    if above >= 8 and closes[-1] > ema[-1]:
        return "LONG", "price holding above EMA20"
    if above <= 2 and closes[-1] < ema[-1]:
        return "SHORT", "price holding below EMA20"
    return "NEUTRAL", "no confirmed structure, mixed EMA"


def liquidity_targets(bars: list[Bar], swings: list[Swing], direction: str) -> tuple[float | None, float | None, bool]:
    """(nearest target, runner target, equal-cluster flag) from untaken swing liquidity.

    direction "SHORT": untaken swing lows below current close, nearest first.
    direction "LONG": untaken swing highs above current close.
    """
    last_close = bars[-1].close
    atr = average_true_range(bars)
    if direction == "SHORT":
        levels = sorted((s.price for s in untaken_swings(bars, swings, "low") if s.price < last_close), reverse=True)
    else:
        levels = sorted(s.price for s in untaken_swings(bars, swings, "high") if s.price > last_close)
    nearest = levels[0] if levels else None
    runner = levels[1] if len(levels) > 1 else None
    equal = bool(levels[1:] and abs(levels[1] - levels[0]) <= 0.15 * atr)
    return nearest, runner, equal


# --- PA_Agent backfill: environment-quality vetoes (2026-07-11) -------------
# Mechanised from Brooks via PA_Agent's binary decision tree. These are VETO
# candidates for LTF triggers — validate on replayed history before wiring
# into a_watch/scanner (textbook rules are hypotheses, not edges).


def barbwire(bars: list[Bar], lookback: int = 12) -> tuple[bool, str]:
    """Sideways chop: heavy bar overlap + doji-ish bodies + no net progress.

    Brooks barbwire = tight trading range of overlapping small-body bars where
    breakout entries are traps. Mechanical proxy over the last `lookback` bars:
      1. net progress |last close - first open| < 0.8 x ATR
      2. mean body/range < 0.45 (doji-ish)
      3. window range < 2.5 x mean bar range (bars pile on each other)
    All three -> barbwire.
    """
    if len(bars) < lookback:
        return False, "insufficient bars"
    w = bars[-lookback:]
    atr = average_true_range(bars)
    if atr <= 0:
        return False, "flat data"
    ranges = [b.high - b.low for b in w]
    mean_range = sum(ranges) / len(ranges)
    if mean_range <= 0:
        return True, "zero-range bars"
    net = abs(w[-1].close - w[0].open)
    bodies = [abs(b.close - b.open) / (b.high - b.low) for b in w if b.high > b.low]
    mean_body = sum(bodies) / len(bodies) if bodies else 0.0
    window_range = max(b.high for b in w) - min(b.low for b in w)
    hit = net < 0.8 * atr and mean_body < 0.45 and window_range < 2.5 * mean_range
    return hit, (f"net={net / atr:.2f}atr body={mean_body:.2f} "
                 f"span={window_range / mean_range:.2f}x")


def _strong_bar(b: Bar, direction: str) -> bool:
    rng = b.high - b.low
    if rng <= 0:
        return False
    body = abs(b.close - b.open)
    if direction == "LONG":
        return b.close > b.open and body >= 0.6 * rng and (b.high - b.close) <= 0.3 * rng
    return b.close < b.open and body >= 0.6 * rng and (b.close - b.low) <= 0.3 * rng


def climax_risk(bars: list[Bar], direction: str, min_run: int = 4) -> tuple[bool, str]:
    """Don't chase `direction` right after a buy/sell climax.

    Mechanical: within the last min_run+2 bars there is a run of >= min_run
    consecutive strong same-direction bars whose cumulative move >= 2 x ATR,
    and the run ended within the last 2 bars. That leg is climactic — a fresh
    trigger in the same direction is a chase, not an entry.
    """
    if len(bars) < min_run + 2:
        return False, "insufficient bars"
    atr = average_true_range(bars)
    if atr <= 0:
        return False, "flat data"
    tail = bars[-(min_run + 2):]
    run, run_end = 0, None
    best_run, best_end = 0, None
    for i, b in enumerate(tail):
        if _strong_bar(b, direction):
            run += 1
            run_end = i
            if run > best_run:
                best_run, best_end = run, run_end
        else:
            run = 0
    if best_run < min_run or best_end is None or best_end < len(tail) - 3:
        return False, "no fresh climactic run"
    seg = tail[best_end - best_run + 1:best_end + 1]
    move = abs(seg[-1].close - seg[0].open)
    if move >= 2.0 * atr:
        return True, f"{best_run} strong bars, {move / atr:.1f}atr leg just ended"
    return False, f"run too small ({move / atr:.1f}atr)"


def micro_channel(bars: list[Bar], lookback: int = 8, min_len: int = 4) -> tuple[str | None, str]:
    """Detect an active micro channel; veto countertrend triggers inside it.

    Bull micro channel: >= min_len consecutive bars with lows >= prior low and
    closes never below prior low, ending at the last bar. Bear mirrored.
    Returns ("LONG"|"SHORT"|None, note) — the channel's own direction.
    """
    if len(bars) < min_len + 1:
        return None, "insufficient bars"
    w = bars[-lookback:]
    for side in ("LONG", "SHORT"):
        length = 0
        for i in range(len(w) - 1, 0, -1):
            cur, prev = w[i], w[i - 1]
            if side == "LONG" and cur.low >= prev.low and cur.close >= prev.low:
                length += 1
            elif side == "SHORT" and cur.high <= prev.high and cur.close <= prev.high:
                length += 1
            else:
                break
        if length >= min_len:
            return side, f"{length}-bar micro channel"
    return None, "none"


def signal_bar_quality(bars: list[Bar], direction: str) -> tuple[str, str]:
    """Grade the last bar as a Brooks signal/trigger bar for `direction`.

    "strong": body >= 55% of range, close in the directional 30% extreme,
              adverse tail <= 30% of range, and range <= 2.0 x ATR (an
              oversized bar has already spent the move and pushes the stop far).
    "weak":   body < 35% of range, or close in the wrong half, or adverse
              tail > 50%, or range > 2.5 x ATR.
    "ok":     everything in between.
    """
    b = bars[-1]
    rng = b.high - b.low
    atr = average_true_range(bars)
    if rng <= 0 or atr <= 0:
        return "weak", "flat bar/data"
    body = abs(b.close - b.open) / rng
    close_pos = (b.close - b.low) / rng          # 0=low, 1=high
    if direction == "LONG":
        directional_close, adverse_tail = close_pos, (b.high - max(b.close, b.open)) / rng
    else:
        directional_close, adverse_tail = 1 - close_pos, (min(b.close, b.open) - b.low) / rng
    size = rng / atr
    note = f"body={body:.2f} close_pos={directional_close:.2f} tail={adverse_tail:.2f} size={size:.1f}atr"
    right_side = (b.close > b.open) if direction == "LONG" else (b.close < b.open)
    if body < 0.35 or directional_close < 0.5 or adverse_tail > 0.5 or size > 2.5 or not right_side:
        return "weak", note
    if body >= 0.55 and directional_close >= 0.7 and adverse_tail <= 0.3 and size <= 2.0:
        return "strong", note
    return "ok", note


def hl_count(bars: list[Bar], direction: str) -> int:
    """Brooks H1/H2/... (or L1/L2/...) count over recent bars.

    Bull count: +1 each bar whose high exceeds the prior bar's high; reset
    when a bar closes below the prior bar's low with range >= 1.2 x ATR
    (strong opposite bar kills the count). Bear mirrored. Returns the current
    count for `direction` ("LONG" -> H-count, "SHORT" -> L-count); a trigger
    landing on count==2 is a Brooks second entry.
    """
    if len(bars) < 2:
        return 0
    atr = average_true_range(bars)
    reset_range = 1.2 * atr
    count = 0
    for prev, cur in zip(bars[:-1], bars[1:]):
        rng = cur.high - cur.low
        if direction == "LONG":
            if cur.high > prev.high:
                count += 1
            elif cur.close < prev.low and rng >= reset_range > 0:
                count = 0
        else:
            if cur.low < prev.low:
                count += 1
            elif cur.close > prev.high and rng >= reset_range > 0:
                count = 0
    return count


def trigger_failed_early(trigger_bar: Bar, later_bars: list[Bar], direction: str) -> bool:
    """Failed-trigger early exit: within the 1-2 bars after the trigger bar,
    a close beyond the trigger bar's OPEN against the trade = the breakout
    lost its whole bar — exit/cancel, don't wait for the stop.
    """
    for b in later_bars[:2]:
        if direction == "LONG" and b.close < trigger_bar.open:
            return True
        if direction == "SHORT" and b.close > trigger_bar.open:
            return True
    return False


# Positive-correlation SMT partners (move together).
CORRELATED_PAIRS = {
    "BTC": "ETH", "ETH": "BTC",
    "NAS100": "US500", "US500": "NAS100",
    "EURUSD": "GBPUSD", "GBPUSD": "EURUSD",
    "XAUUSD": "XAGUSD", "XAGUSD": "XAUUSD",
    # Dollar index (same direction as USD-base FX).
    "USDJPY": "DXY",
    "USDCAD": "DXY",
    "USDCHF": "DXY",
}

# Inverse-correlation SMT partners (e.g. EURUSD vs DXY).
# When A sweeps a low for LONG, inverse B should fail to make a new high.
# Metals stay in CORRELATED_PAIRS (XAU↔XAG), not here — ICT metal SMT is
# gold/silver same-complex, not silver vs DXY as primary.
INVERSE_SMT_PAIRS = {
    "EURUSD": "DXY",
    "GBPUSD": "DXY",
    "AUDUSD": "DXY",
    "NZDUSD": "DXY",
    "DXY": "EURUSD",
}


def smt_partner(symbol: str) -> tuple[str | None, bool]:
    """Return (partner_symbol, inverse).

    Prefer same-complex correlated pairs first (XAU↔XAG, EUR↔GBP, …),
    then inverse DXY map for USD-quote FX legs.
    """
    s = symbol.upper()
    if s in CORRELATED_PAIRS:
        return CORRELATED_PAIRS[s], False
    if s in INVERSE_SMT_PAIRS:
        return INVERSE_SMT_PAIRS[s], True
    return None, False


def smt_divergence(bars_a: list[Bar], bars_b: list[Bar], direction: str,
                   lookback: int = 16, *, inverse: bool = False) -> tuple[bool, str]:
    """ICT SMT: symbol A swept its prior extreme while partner B failed to
    confirm — divergence supports the reversal `direction`.

    Positive correlation (default):
      LONG: A swept prior low; B did NOT break its prior low.
      SHORT: A swept prior high; B did NOT break its prior high.

    Inverse correlation (e.g. EURUSD vs DXY):
      LONG on A: A swept prior low; B failed to make a new high.
      SHORT on A: A swept prior high; B failed to make a new low.

    Uses only closed bars; both series must cover the same window.
    """
    if len(bars_a) < lookback + 4 or len(bars_b) < lookback + 4:
        return False, "insufficient bars"
    recent_a, prior_a = bars_a[-4:], bars_a[-lookback - 4:-4]
    recent_b, prior_b = bars_b[-4:], bars_b[-lookback - 4:-4]
    if direction == "LONG":
        a_swept = min(b.low for b in recent_a) < min(b.low for b in prior_a)
        if inverse:
            b_held = max(b.high for b in recent_b) <= max(b.high for b in prior_b)
        else:
            b_held = min(b.low for b in recent_b) >= min(b.low for b in prior_b)
    else:
        a_swept = max(b.high for b in recent_a) > max(b.high for b in prior_a)
        if inverse:
            b_held = min(b.low for b in recent_b) >= min(b.low for b in prior_b)
        else:
            b_held = max(b.high for b in recent_b) <= max(b.high for b in prior_b)
    if a_swept and b_held:
        kind = "inverse" if inverse else "correlated"
        return True, f"SMT({kind}): A swept, partner held"
    return False, ("no sweep on A" if not a_swept else "partner swept too")


def sweep_depth_atr(bars: list[Bar], swept_level: float, direction: str,
                    lookback: int = 6) -> float:
    """Penetration depth of the sweep beyond the swept level, in ATR.

    ICT inducement doctrine prefers SHALLOW sweeps (barely tagging the level).
    direction "LONG" = sell-side sweep below `swept_level`: depth = how far
    the recent extreme pierced below it. Mirrored for SHORT.
    """
    atr = average_true_range(bars)
    if atr <= 0:
        return 0.0
    w = bars[-lookback:]
    if direction == "LONG":
        pierce = swept_level - min(b.low for b in w)
    else:
        pierce = max(b.high for b in w) - swept_level
    return round(max(0.0, pierce) / atr, 3)


# --- confirm_bar (desk trigger contract, 2026-07-14) ---
# Moves "which confirm K / trigger price / cancel" into scanner code.
# Desk may only quote these fields; must not invent trigger prices.

CONFIRM_TTL_BARS = 6
# TFs that may host an executable entry confirm_bar (Tier 2).
ENTRY_TFS = frozenset({"M1", "M5"})
# Parent/map TFs: MSS/CISD here is direction/management map, not entry trigger.
MAP_TFS = frozenset({"M15", "H1", "H4", "D1", "W1"})


def confirm_tf_role(tf: str) -> tuple[str, str, str]:
    """Return (role, map_tf, entry_tf_hint).

    role:
      entry_confirm — confirm_bar may supply Tier-2 trigger prices
      map_confirm   — map/management only; desk must not use trigger as entry
    """
    tf_u = (tf or "").upper()
    if tf_u in ENTRY_TFS:
        return "entry_confirm", tf_u, tf_u
    # Default: treat unknown as map for safety (no invented entry triggers).
    hint = "M5"
    return "map_confirm", tf_u or "M15", hint


def _first_close_through_index(
    bars: list[Bar], level: float, direction: str, start: int
) -> int | None:
    """Index of first bar that *closes* through level in trade direction.

    SHORT: close < level. LONG: close > level.
    """
    for j in range(start, len(bars)):
        c = bars[j].close
        if direction == "SHORT" and c < level:
            return j
        if direction == "LONG" and c > level:
            return j
    return None


def _closed_back_through(
    bars: list[Bar], level: float, direction: str, start: int
) -> bool:
    """True if any close after start reclaims the wrong side of frozen level."""
    for j in range(start, len(bars)):
        c = bars[j].close
        if direction == "SHORT" and c > level:
            return True
        if direction == "LONG" and c < level:
            return True
    return False


def _fmt_bar_time(ts: float | int) -> str:
    from datetime import datetime, timezone

    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, OSError, OverflowError):
        return str(ts)


def _market_ok_and_fails(
    price: float,
    cb: Bar,
    frozen: float,
    trigger: float,
    direction: str,
) -> tuple[bool, list[str]]:
    fails: list[str] = []
    if not (cb.low <= price <= cb.high):
        fails.append("price_outside_confirm_range")
    if direction == "SHORT":
        if price >= frozen:
            fails.append("wrong_side_of_frozen")
        if price < trigger:
            fails.append("beyond_trigger_extreme")
    else:
        if price <= frozen:
            fails.append("wrong_side_of_frozen")
        if price > trigger:
            fails.append("beyond_trigger_extreme")
    return (len(fails) == 0), fails


def build_confirm_bar(
    bars: list[Bar],
    direction: str,
    atr: float,
    mss_level: float | None,
    mss_ok: bool,
    cisd_level: float | None,
    cisd_ok: bool,
    after_index: int,
    tf: str,
    price: float,
    spread_pad: float = 0.0,
) -> dict | None:
    """Build confirm_bar for a sweep-reversal candidate.

    Returns None if no MSS/CISD close confirmation, TTL expired, or frozen
    level was reclaimed by a later close (old confirm must not resurrect).

    Event selection when both MSS and CISD confirm: the *later* close-through
    event and its frozen level (skill: MSS+CISD uses the later confirmation).
    """
    if direction not in ("SHORT", "LONG"):
        return None

    candidates: list[tuple[int, str, float, str]] = []
    # (confirm_idx, event_kind, frozen_level, frozen_source)
    if mss_ok and mss_level is not None:
        idx = _first_close_through_index(bars, mss_level, direction, after_index + 1)
        if idx is not None:
            candidates.append((idx, "MSS", mss_level, "confirmed_swing"))
    if cisd_ok and cisd_level is not None:
        idx = _first_close_through_index(bars, cisd_level, direction, after_index + 1)
        if idx is not None:
            candidates.append((idx, "CISD", cisd_level, "delivery_open"))

    if not candidates:
        return None

    # Later confirmation wins; if same bar, prefer combined label
    candidates.sort(key=lambda x: x[0])
    last_idx = candidates[-1][0]
    same_bar = [c for c in candidates if c[0] == last_idx]
    if len(same_bar) > 1:
        # both on same bar — use later-defined frozen: prefer the event with
        # larger index order CISD after MSS if both; for frozen use the level
        # that was broken on this bar for the combined event. Spec: MSS+CISD
        # uses the later event's price — same bar → tag MSS+CISD and use
        # the frozen level of the second listed in same_bar after sort by source
        # priority: if both, frozen = the one whose level was the "decisive"
        # later in skill text = last in candidates list among same bar.
        frozen = same_bar[-1][2]
        source = same_bar[-1][3]
        kinds = {c[1] for c in same_bar}
        event = "MSS+CISD" if kinds == {"MSS", "CISD"} else same_bar[-1][1]
    elif len(candidates) > 1:
        # different bars: last one is later
        event = "MSS+CISD" if {c[1] for c in candidates} == {"MSS", "CISD"} else candidates[-1][1]
        # frozen from the later event only
        frozen = candidates[-1][2]
        source = candidates[-1][3]
        # if both events, label MSS+CISD but frozen from later
        if {c[1] for c in candidates} == {"MSS", "CISD"}:
            event = "MSS+CISD"
    else:
        event = candidates[-1][1]
        frozen = candidates[-1][2]
        source = candidates[-1][3]

    cb_idx = last_idx
    cb = bars[cb_idx]
    age = len(bars) - 1 - cb_idx
    if age >= CONFIRM_TTL_BARS:
        return None
    # invalidate if any close after confirm bar reclaims frozen
    if _closed_back_through(bars, frozen, direction, cb_idx + 1):
        return None

    buf = max(0.25 * atr, spread_pad)
    if direction == "SHORT":
        trigger = cb.low - buf
        side = "sell_stop_below_low"
    else:
        trigger = cb.high + buf
        side = "buy_stop_above_high"

    market_ok, market_fail = _market_ok_and_fails(price, cb, frozen, trigger, direction)
    role, map_tf, entry_tf_hint = confirm_tf_role(tf)

    def _r(x: float) -> float:
        if abs(x) >= 100:
            return round(x, 2)
        if abs(x) >= 1:
            return round(x, 5)
        return round(x, 8)

    return {
        "tf": tf,
        "role": role,
        "map_tf": map_tf,
        "entry_tf_hint": entry_tf_hint,
        "event": event,
        "frozen_level": _r(frozen),
        "frozen_source": source,
        "bar_time": _fmt_bar_time(cb.ts),
        "bar_age": age,
        "open": _r(cb.open),
        "high": _r(cb.high),
        "low": _r(cb.low),
        "close": _r(cb.close),
        "buffer": _r(buf),
        "buffer_calc": f"max(0.25*ATR={0.25 * atr:.5g}, spread_pad={spread_pad})",
        "trigger_price": _r(trigger),
        "trigger_side": side,
        "market_ok": market_ok,
        "market_fail": market_fail,
        "expiry_bars": CONFIRM_TTL_BARS,
        "bars_since_confirm": age,
        "cancel_level": _r(frozen),
    }
