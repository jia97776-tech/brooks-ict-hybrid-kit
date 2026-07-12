#!/usr/bin/env python3
"""Walk-forward comparison of M5 MSS/CISD entry expressions.

Local-data only. The study keeps the confirmation event separate from the
order expression:

Events:
  - first M5 MSS after the parent-zone retest
  - first M5 CISD after the parent-zone retest
  - double confirm at the later of MSS/CISD

Orders (active from the next M5 bar only):
  - next-bar open
  - confirmation-bar extreme stop
  - active directional FVG CE limit
  - active flipped opposing FVG (iFVG) CE limit

Primary pending-order window is 12 M5 bars; 6/24 are sensitivity checks.
Settlement is 96 M5 bars from the event. Same-bar fill + stop/target is
resolved as stop first. No spread, fees, slippage, or M1 inference.
"""

from __future__ import annotations

import json
import math
import sys
import time
from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scanner_service.sources import Bar
from scanner_service.structure import find_swings

import backtest_trigger_deep as base


PRIMARY_FILL_BARS = 12
FILL_WINDOWS = (6, 12, 24)
SETTLE_BARS = 96
SL_BUFFER_ATR = 0.25
MIN_RISK_ATR = 0.5
MIN_N = 30
NOTABLE_R = 0.15
ORDER_NAMES = (
    "next_open",
    "event_stop",
    "fvg_ce",
    "fvg_ce_soft",
    "ifvg_ce",
    "ifvg_ce_soft",
)
OUT_JSON = ROOT / "data" / "backtest_fvg_ifvg_entries.json"
OUT_REPORT = ROOT / "data" / "backtest_fvg_ifvg_entries.md"


@dataclass(frozen=True)
class ArraySetup:
    kind: str
    formed_idx: int
    zone_low: float
    zone_high: float
    entry: float


@dataclass(frozen=True)
class StructureEvent:
    kind: str
    index: int
    level: float


@dataclass(frozen=True)
class OrderResult:
    filled: bool
    fill_ts: int | None
    outcome: str
    result_r: float
    mfe_r: float
    mae_r: float
    bars_to_fill: int | None
    entry: float | None = None


def find_directional_fvg(
    bars: list[Bar], direction: str, start_idx: int, trigger_idx: int
) -> ArraySetup | None:
    """Latest trade-direction three-candle FVG known at trigger close."""
    want_short = direction == "SHORT"
    for i in range(trigger_idx, max(start_idx + 1, 2) - 1, -1):
        first, third = bars[i - 2], bars[i]
        if want_short and first.low > third.high:
            lo, hi = third.high, first.low
            invalid = any(b.close > hi for b in bars[i + 1:trigger_idx + 1])
            if not invalid:
                return ArraySetup("fvg", i, lo, hi, (lo + hi) / 2.0)
        if not want_short and first.high < third.low:
            lo, hi = first.high, third.low
            invalid = any(b.close < lo for b in bars[i + 1:trigger_idx + 1])
            if not invalid:
                return ArraySetup("fvg", i, lo, hi, (lo + hi) / 2.0)
    return None


def find_ifvg_flip(
    bars: list[Bar], direction: str, start_idx: int, trigger_idx: int
) -> ArraySetup | None:
    """Latest opposing FVG first closed through in trade direction by trigger_idx."""
    want_short = direction == "SHORT"
    candidates: list[ArraySetup] = []
    for i in range(max(start_idx + 2, 2), trigger_idx + 1):
        first, third = bars[i - 2], bars[i]
        if want_short and first.high < third.low:
            lo, hi = first.high, third.low
        elif not want_short and first.low > third.high:
            lo, hi = third.high, first.low
        else:
            continue
        flip_idx = next(
            (
                j
                for j in range(i + 1, trigger_idx + 1)
                if (bars[j].close < lo if want_short else bars[j].close > hi)
            ),
            None,
        )
        if flip_idx is not None:
            invalid = any(
                (
                    bars[j].close > hi
                    if want_short
                    else bars[j].close < lo
                )
                for j in range(flip_idx + 1, trigger_idx + 1)
            )
            if invalid:
                continue
            candidates.append(
                ArraySetup("ifvg", flip_idx, lo, hi, (lo + hi) / 2.0)
            )
    return max(candidates, key=lambda item: item.formed_idx) if candidates else None


def detect_mss_event(
    bars: list[Bar], direction: str, start_idx: int, end_idx: int
) -> StructureEvent | None:
    """First close-through of a confirmed opposing swing after start_idx."""
    segment = bars[:end_idx + 1]
    swings = find_swings(segment)
    want = "low" if direction == "SHORT" else "high"
    for j in range(start_idx + 1, end_idx + 1):
        levels = [
            swing
            for swing in swings
            if swing.kind == want
            and swing.index >= start_idx
            and swing.confirmed_at < j
        ]
        if not levels:
            continue
        level = levels[-1].price
        if (direction == "SHORT" and bars[j].close < level) or (
            direction == "LONG" and bars[j].close > level
        ):
            return StructureEvent("mss", j, level)
    return None


def detect_cisd_event(
    bars: list[Bar], direction: str, start_idx: int, end_idx: int
) -> StructureEvent | None:
    """Close-through of the open of the last opposing delivery run into the extreme."""
    if start_idx >= end_idx:
        return None
    if direction == "SHORT":
        extreme_idx = max(
            range(start_idx, end_idx + 1), key=lambda i: bars[i].high
        )
        is_delivery = lambda b: b.close > b.open
        crossed = lambda close, level: close < level
    else:
        extreme_idx = min(
            range(start_idx, end_idx + 1), key=lambda i: bars[i].low
        )
        is_delivery = lambda b: b.close < b.open
        crossed = lambda close, level: close > level

    idx = extreme_idx
    if not is_delivery(bars[idx]):
        idx -= 1
    series_start = None
    while idx >= start_idx and is_delivery(bars[idx]):
        series_start = idx
        idx -= 1
    if series_start is None:
        return None
    level = bars[series_start].open
    for j in range(extreme_idx + 1, end_idx + 1):
        if crossed(bars[j].close, level):
            return StructureEvent("cisd", j, level)
    return None


def first_mss_event(
    bars: list[Bar], direction: str, start_idx: int
) -> StructureEvent | None:
    """Optimized first MSS; swing visibility is gated by confirmed_at < j."""
    swings = find_swings(bars)
    want = "low" if direction == "SHORT" else "high"
    for j in range(start_idx + 1, len(bars)):
        levels = [
            swing
            for swing in swings
            if swing.kind == want
            and swing.index > start_idx
            and swing.confirmed_at < j
        ]
        if not levels:
            continue
        level = levels[-1].price
        if (direction == "SHORT" and bars[j].close < level) or (
            direction == "LONG" and bars[j].close > level
        ):
            return StructureEvent("mss", j, level)
    return None


def first_cisd_event(
    bars: list[Bar], direction: str, start_idx: int
) -> StructureEvent | None:
    """Walk forward so a later extreme cannot rewrite an earlier CISD."""
    for j in range(start_idx + 1, len(bars)):
        event = detect_cisd_event(bars[: j + 1], direction, start_idx, j)
        if event is not None and event.index == j:
            return event
    return None


def simulate_limit_order(
    future_bars: list[Bar],
    direction: str,
    entry: float,
    sl: float,
    target: float,
    invalidation_close: float,
    valid_bars: int,
    settle_bars: int | None = None,
    soft_exit_after_fill: bool = False,
) -> OrderResult:
    """Resting limit from the first future bar; same-bar fill+SL is a loss."""
    sign = 1.0 if direction == "LONG" else -1.0
    risk = sign * (entry - sl)
    if risk <= 0:
        return OrderResult(False, None, "invalid", 0.0, 0.0, 0.0, None, entry)
    target_r = sign * (target - entry) / risk
    if target_r <= 0:
        return OrderResult(False, None, "invalid", 0.0, 0.0, 0.0, None, entry)

    filled = False
    fill_ts = None
    fill_index = None
    mfe_r = 0.0
    mae_r = 0.0
    horizon = future_bars[: settle_bars or valid_bars]
    for i, b in enumerate(horizon):
        if not filled:
            if i >= valid_bars:
                break
            target_touched = b.high >= target if sign > 0 else b.low <= target
            entry_touched = b.low <= entry if sign > 0 else b.high >= entry
            invalidated = (
                b.close < invalidation_close
                if sign > 0
                else b.close > invalidation_close
            )
            if target_touched and not entry_touched:
                return OrderResult(
                    False, None, "missed_alpha", 0.0, 0.0, 0.0, None, entry
                )
            if invalidated and not entry_touched:
                return OrderResult(
                    False, None, "cancelled", 0.0, 0.0, 0.0, None, entry
                )
            if not entry_touched:
                continue
            filled = True
            fill_ts = b.ts
            fill_index = i

        favorable = sign * ((b.high if sign > 0 else b.low) - entry) / risk
        adverse = -sign * ((b.low if sign > 0 else b.high) - entry) / risk
        mfe_r = max(mfe_r, favorable)
        mae_r = max(mae_r, adverse)
        stop_touched = b.low <= sl if sign > 0 else b.high >= sl
        target_touched = b.high >= target if sign > 0 else b.low <= target
        if stop_touched:
            return OrderResult(
                True, fill_ts, "sl", -1.0, mfe_r, mae_r, fill_index, entry
            )
        if target_touched:
            return OrderResult(
                True, fill_ts, "tp", target_r, mfe_r, mae_r, fill_index, entry
            )
        invalidated = (
            b.close < invalidation_close
            if sign > 0
            else b.close > invalidation_close
        )
        if soft_exit_after_fill and invalidated:
            exit_r = sign * (b.close - entry) / risk
            return OrderResult(
                True,
                fill_ts,
                "soft_exit",
                max(exit_r, -1.0),
                mfe_r,
                mae_r,
                fill_index,
                entry,
            )

    if not filled:
        return OrderResult(False, None, "no_fill", 0.0, 0.0, 0.0, None, entry)
    last = horizon[-1]
    mark = sign * (((last.high + last.low) / 2.0) - entry) / risk
    return OrderResult(
        True, fill_ts, "expired", mark, mfe_r, mae_r, fill_index, entry
    )


def simulate_stop_order(
    future_bars: list[Bar],
    direction: str,
    entry: float,
    sl: float,
    target: float,
    valid_bars: int,
    settle_bars: int | None = None,
) -> OrderResult:
    """Resting breakout stop from the first future bar."""
    sign = 1.0 if direction == "LONG" else -1.0
    risk = sign * (entry - sl)
    if risk <= 0:
        return OrderResult(False, None, "invalid", 0.0, 0.0, 0.0, None, entry)
    target_r = sign * (target - entry) / risk
    if target_r <= 0:
        return OrderResult(False, None, "invalid", 0.0, 0.0, 0.0, None, entry)
    filled = False
    fill_ts = None
    fill_index = None
    mfe_r = 0.0
    mae_r = 0.0
    horizon = future_bars[: settle_bars or valid_bars]
    for i, b in enumerate(horizon):
        if not filled:
            if i >= valid_bars:
                break
            target_touched = b.high >= target if sign > 0 else b.low <= target
            entry_touched = b.high >= entry if sign > 0 else b.low <= entry
            if target_touched and not entry_touched:
                return OrderResult(
                    False, None, "missed_alpha", 0.0, 0.0, 0.0, None, entry
                )
            if not entry_touched:
                continue
            filled = True
            fill_ts = b.ts
            fill_index = i
        favorable = sign * ((b.high if sign > 0 else b.low) - entry) / risk
        adverse = -sign * ((b.low if sign > 0 else b.high) - entry) / risk
        mfe_r = max(mfe_r, favorable)
        mae_r = max(mae_r, adverse)
        stop_touched = b.low <= sl if sign > 0 else b.high >= sl
        target_touched = b.high >= target if sign > 0 else b.low <= target
        if stop_touched:
            return OrderResult(
                True, fill_ts, "sl", -1.0, mfe_r, mae_r, fill_index, entry
            )
        if target_touched:
            return OrderResult(
                True, fill_ts, "tp", target_r, mfe_r, mae_r, fill_index, entry
            )
    if not filled:
        return OrderResult(
            False, None, "no_fill", 0.0, 0.0, 0.0, None, entry
        )
    last = horizon[-1]
    mark = sign * (((last.high + last.low) / 2.0) - entry) / risk
    return OrderResult(
        True, fill_ts, "expired", mark, mfe_r, mae_r, fill_index, entry
    )


def simulate_market_entry(
    future_bars: list[Bar],
    direction: str,
    sl: float,
    target: float,
    valid_bars: int,
) -> OrderResult:
    """Enter at the next bar open after the close-confirmed event."""
    if not future_bars:
        return OrderResult(False, None, "no_fill", 0.0, 0.0, 0.0, None, None)
    entry = future_bars[0].open
    sign = 1.0 if direction == "LONG" else -1.0
    risk = sign * (entry - sl)
    if risk <= 0 or sign * (target - entry) <= 0:
        return OrderResult(False, None, "invalid", 0.0, 0.0, 0.0, None, entry)
    result = simulate_limit_order(
        future_bars=future_bars,
        direction=direction,
        entry=entry,
        sl=sl,
        target=target,
        invalidation_close=sl,
        valid_bars=valid_bars,
        settle_bars=valid_bars,
    )
    return OrderResult(
        True,
        future_bars[0].ts,
        result.outcome,
        result.result_r,
        result.mfe_r,
        result.mae_r,
        0,
        entry,
    )


def _zone_entry_idx(parent: dict, bars: list[Bar]) -> int | None:
    short = parent["direction"] == "SHORT"
    swept = float(parent["swept_level"])
    for i, b in enumerate(bars):
        if (short and b.high >= swept) or (not short and b.low <= swept):
            return i
    return None


def _atr_at(atr: list[float], index: int) -> float:
    return max(atr[index], 1e-9)


def _stop_for_entry(
    direction: str,
    entry: float,
    sequence_bars: list[Bar],
    atr: float,
) -> float:
    if direction == "SHORT":
        structural = max(b.high for b in sequence_bars) + SL_BUFFER_ATR * atr
        return max(structural, entry + MIN_RISK_ATR * atr)
    structural = min(b.low for b in sequence_bars) - SL_BUFFER_ATR * atr
    return min(structural, entry - MIN_RISK_ATR * atr)


def _event_orders(
    parent: dict,
    window: list[Bar],
    global_bars: list[Bar],
    global_ts: list[int],
    global_atr: list[float],
    zone_idx: int,
    event: StructureEvent,
    event_name: str,
    fill_bars: int,
) -> list[dict]:
    event_bar = window[event.index]
    gi = bisect_left(global_ts, event_bar.ts)
    if gi >= len(global_bars) or global_bars[gi].ts != event_bar.ts:
        return []
    future = global_bars[gi + 1: gi + 1 + SETTLE_BARS]
    if not future:
        return []
    direction = parent["direction"]
    target = float(parent["dol"])
    atr = _atr_at(global_atr, gi)
    sequence = window[zone_idx: event.index + 1]
    fvg = find_directional_fvg(window, direction, zone_idx, event.index)
    ifvg = find_ifvg_flip(window, direction, zone_idx, event.index)
    setups = []

    next_open = future[0].open
    sl = _stop_for_entry(direction, next_open, sequence, atr)
    setups.append(
        (
            "next_open",
            next_open,
            sl,
            simulate_market_entry(future, direction, sl, target, SETTLE_BARS),
        )
    )

    stop_entry = event_bar.low if direction == "SHORT" else event_bar.high
    sl = _stop_for_entry(direction, stop_entry, sequence, atr)
    setups.append(
        (
            "event_stop",
            stop_entry,
            sl,
            simulate_stop_order(
                future,
                direction,
                stop_entry,
                sl,
                target,
                fill_bars,
                SETTLE_BARS,
            ),
        )
    )

    for name, array in (("fvg_ce", fvg), ("ifvg_ce", ifvg)):
        if array is None:
            continue
        entry = array.entry
        sl = _stop_for_entry(direction, entry, sequence, atr)
        invalidation = (
            array.zone_high if direction == "SHORT" else array.zone_low
        )
        result = simulate_limit_order(
            future,
            direction,
            entry,
            sl,
            target,
            invalidation,
            fill_bars,
            SETTLE_BARS,
        )
        setups.append((name, entry, sl, result))
        soft_result = simulate_limit_order(
            future,
            direction,
            entry,
            sl,
            target,
            invalidation,
            fill_bars,
            SETTLE_BARS,
            soft_exit_after_fill=True,
        )
        setups.append((f"{name}_soft", entry, sl, soft_result))

    rows = []
    sign = 1.0 if direction == "LONG" else -1.0
    for order_name, entry, sl, result in setups:
        risk = sign * (entry - sl)
        reward = sign * (target - entry)
        if risk <= 0 or reward <= 0:
            continue
        rows.append(
            {
                "symbol": parent["symbol"],
                "direction": direction,
                "event": event_name,
                "event_ts": event_bar.ts,
                "order": order_name,
                "fill_window": fill_bars,
                "entry": entry,
                "sl": sl,
                "target": target,
                "planned_rr": reward / risk,
                "filled": result.filled,
                "outcome": result.outcome,
                "result_r": result.result_r,
                "mfe_r": result.mfe_r,
                "mae_r": result.mae_r,
                "bars_to_fill": result.bars_to_fill,
                "crypto": parent["symbol"] in base.CRYPTO,
                "month": time.strftime("%Y-%m", time.gmtime(event_bar.ts)),
            }
        )
    return rows


def run_symbol(symbol: str) -> tuple[list[dict], dict]:
    m15 = base.load(symbol, "M15")
    m5 = base.load(symbol, "M5")
    if len(m15) < 200 or len(m5) < 500:
        return [], {"symbol": symbol, "parents": 0, "events": 0}
    parents = base.gen_parents(symbol, m15)
    m5_ts = [b.ts for b in m5]
    atr = base.rolling_atr(m5)
    rows = []
    seen_events = set()
    # Latest parent owns a duplicated LTF event; older overlapping plans must not
    # multiply one confirmation bar into several nominally independent samples.
    for parent in reversed(parents):
        lo = bisect_right(m5_ts, parent["ts"])
        hi = bisect_right(m5_ts, parent["ts"] + base.FILL_WINDOW_S)
        window = m5[lo:hi]
        if len(window) < 10:
            continue
        zone_idx = _zone_entry_idx(parent, window)
        if zone_idx is None:
            continue
        mss = first_mss_event(window, parent["direction"], zone_idx)
        cisd = first_cisd_event(window, parent["direction"], zone_idx)
        events = []
        if mss is not None:
            events.append(("mss", mss))
        if cisd is not None:
            events.append(("cisd", cisd))
        if mss is not None and cisd is not None:
            both_idx = max(mss.index, cisd.index)
            both_level = mss.level if mss.index >= cisd.index else cisd.level
            events.append(("mss+cisd", StructureEvent("both", both_idx, both_level)))
        for event_name, event in events:
            key = (symbol, parent["direction"], event_name, window[event.index].ts)
            if key in seen_events:
                continue
            seen_events.add(key)
            for fill_bars in FILL_WINDOWS:
                rows.extend(
                    _event_orders(
                        parent,
                        window,
                        m5,
                        m5_ts,
                        atr,
                        zone_idx,
                        event,
                        event_name,
                        fill_bars,
                    )
                )
    return rows, {
        "symbol": symbol,
        "parents": len(parents),
        "events": len(seen_events),
        "m5_bars": len(m5),
        "start": m5[0].ts,
        "end": m5[-1].ts,
    }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    mid = len(vals) // 2
    if len(vals) % 2:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2.0


def _bootstrap_ci(
    values: list[float], iterations: int = 1000
) -> tuple[float, float]:
    """Deterministic cluster-free bootstrap is avoided; use normal CI as a warning."""
    n = len(values)
    if n < 2:
        return (0.0, 0.0)
    mean = _mean(values)
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    margin = 1.96 * math.sqrt(variance / n)
    return mean - margin, mean + margin


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    filled = [row for row in rows if row["filled"]]
    rs_all = [row["result_r"] for row in rows]
    rs_fill = [row["result_r"] for row in filled]
    ci = _bootstrap_ci(rs_all)
    return {
        "signals": n,
        "filled": len(filled),
        "fill_rate": len(filled) / n if n else 0.0,
        "win_rate_filled": (
            sum(1 for row in filled if row["result_r"] > 0) / len(filled)
            if filled
            else 0.0
        ),
        "avg_r_per_signal": _mean(rs_all),
        "avg_r_per_fill": _mean(rs_fill),
        "median_planned_rr": _median([row["planned_rr"] for row in rows]),
        "median_mfe_r": _median([row["mfe_r"] for row in filled]),
        "median_mae_r": _median([row["mae_r"] for row in filled]),
        "missed_alpha_rate": (
            sum(1 for row in rows if row["outcome"] == "missed_alpha") / n
            if n
            else 0.0
        ),
        "cancel_rate": (
            sum(1 for row in rows if row["outcome"] == "cancelled") / n
            if n
            else 0.0
        ),
        "ci95_naive": ci,
    }


def first_event_per_symbol_day(rows: list[dict]) -> list[dict]:
    """Keep every order variant for the first event of each type/symbol/UTC day."""
    first_ts = {}
    for row in rows:
        day = time.strftime("%Y-%m-%d", time.gmtime(row["event_ts"]))
        key = (row["symbol"], row["event"], day)
        first_ts[key] = min(first_ts.get(key, row["event_ts"]), row["event_ts"])
    selected = []
    for row in rows:
        day = time.strftime("%Y-%m-%d", time.gmtime(row["event_ts"]))
        key = (row["symbol"], row["event"], day)
        if row["event_ts"] == first_ts[key]:
            selected.append(row)
    return selected


def _append_result_table(
    lines: list[str],
    summary: dict,
    rows: list[dict],
    key_prefix: str,
) -> None:
    lines.append(
        "| Event | Order | n | Fill | Win/fill | AvgR/signal | AvgR/fill | Median RR |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for event in ("mss", "cisd", "mss+cisd"):
        for order in ORDER_NAMES:
            sub = [
                row
                for row in rows
                if row["event"] == event and row["order"] == order
            ]
            if not sub:
                continue
            stats = summarize(sub)
            summary[f"{key_prefix}:{event}:{order}"] = stats
            lines.append(
                f"| {event} | {order} | {stats['signals']} | "
                f"{stats['fill_rate']:.1%} | {stats['win_rate_filled']:.1%} | "
                f"{stats['avg_r_per_signal']:+.3f} | "
                f"{stats['avg_r_per_fill']:+.3f} | "
                f"{stats['median_planned_rr']:.2f} |"
            )


def build_report(rows: list[dict], metas: list[dict]) -> tuple[str, dict]:
    lines = [
        "# M5 MSS/CISD + FVG/iFVG entry backtest",
        "",
        "Local cached data only; strictly walk-forward. M1 is not covered because "
        "long-history M1 raw bars are not present locally.",
        "",
        "Primary pending window: 12 M5 bars. Sensitivity: 6 and 24 bars. "
        "Same-bar ambiguity is resolved stop-first. Unfilled/missed/cancelled orders "
        "count as 0R per signal.",
        "",
        "## Data",
        "",
    ]
    for meta in metas:
        if not meta.get("m5_bars"):
            continue
        lines.append(
            f"- {meta['symbol']}: {meta['m5_bars']} M5 bars, "
            f"{time.strftime('%Y-%m-%d', time.gmtime(meta['start']))} to "
            f"{time.strftime('%Y-%m-%d', time.gmtime(meta['end']))}, "
            f"parents={meta['parents']}, events={meta['events']}"
        )
    lines.extend(
        [
            "",
            "## Primary results (12 bars)",
            "",
        ]
    )
    summary = {}
    primary = [row for row in rows if row["fill_window"] == PRIMARY_FILL_BARS]
    _append_result_table(lines, summary, primary, "primary")

    daily_first = first_event_per_symbol_day(primary)
    lines.extend(
        [
            "",
            "## First event per symbol/day",
            "",
            "This slice reduces repeated intraday confirmations while preserving "
            "paired order variants for the same event.",
            "",
        ]
    )
    _append_result_table(lines, summary, daily_first, "daily_first")

    lines.extend(["", "## Fill-window sensitivity", ""])
    lines.append("| Event | Order | Window | n | Fill | AvgR/signal |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for event in ("mss", "cisd", "mss+cisd"):
        for order in ORDER_NAMES[1:]:
            for window in FILL_WINDOWS:
                sub = [
                    row
                    for row in rows
                    if row["event"] == event
                    and row["order"] == order
                    and row["fill_window"] == window
                ]
                if not sub:
                    continue
                stats = summarize(sub)
                summary[f"{event}:{order}:{window}"] = stats
                lines.append(
                    f"| {event} | {order} | {window} | {stats['signals']} | "
                    f"{stats['fill_rate']:.1%} | "
                    f"{stats['avg_r_per_signal']:+.3f} |"
                )

    lines.extend(["", "## Asset-class split (12 bars)", ""])
    lines.append("| Asset | Event | Order | n | AvgR/signal |")
    lines.append("|---|---|---|---:|---:|")
    for asset_name, crypto in (("crypto", True), ("non-crypto", False)):
        for event in ("mss", "cisd", "mss+cisd"):
            for order in ORDER_NAMES:
                sub = [
                    row
                    for row in primary
                    if row["crypto"] == crypto
                    and row["event"] == event
                    and row["order"] == order
                ]
                if not sub:
                    continue
                stats = summarize(sub)
                summary[f"asset:{asset_name}:{event}:{order}"] = stats
                lines.append(
                    f"| {asset_name} | {event} | {order} | "
                    f"{stats['signals']} | {stats['avg_r_per_signal']:+.3f} |"
                )

    lines.extend(["", "## Monthly stability (12 bars)", ""])
    lines.append("| Event | Order | Months n>=30 | Positive | Min AvgR | Max AvgR |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for event in ("mss", "cisd", "mss+cisd"):
        for order in ORDER_NAMES:
            monthly = []
            for month in sorted({row["month"] for row in primary}):
                sub = [
                    row
                    for row in primary
                    if row["month"] == month
                    and row["event"] == event
                    and row["order"] == order
                ]
                if len(sub) >= MIN_N:
                    stats = summarize(sub)
                    monthly.append((month, stats["avg_r_per_signal"], len(sub)))
                    summary[f"month:{month}:{event}:{order}"] = stats
            if not monthly:
                continue
            values = [item[1] for item in monthly]
            lines.append(
                f"| {event} | {order} | {len(monthly)} | "
                f"{sum(value > 0 for value in values)} | "
                f"{min(values):+.3f} | {max(values):+.3f} |"
            )

    rr2 = [row for row in primary if row["planned_rr"] >= 2.0]
    lines.extend(["", "## Planned RR >= 2 slice (12 bars)", ""])
    _append_result_table(lines, summary, rr2, "rr2")

    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- These are mechanical legality samples, not proof of durable edge.",
            "- Naive confidence intervals overstate certainty because events cluster "
            "by symbol and day.",
            "- Stop-side HTF liquidity pools, fees, spread, slippage, and order latency "
            "are not modeled.",
            "- M5 results must not be generalized to M1 without a separate M1 dataset.",
            f"- A difference smaller than {NOTABLE_R:.2f}R/signal is treated as "
            "operationally weak evidence, not a rule-changing edge.",
            "",
        ]
    )
    return "\n".join(lines), summary


def main() -> None:
    rows = []
    metas = []
    for symbol in base.SYMBOLS:
        started = time.time()
        symbol_rows, meta = run_symbol(symbol)
        rows.extend(symbol_rows)
        metas.append(meta)
        print(
            f"[{symbol}] parents={meta['parents']} events={meta['events']} "
            f"rows={len(symbol_rows)} ({time.time() - started:.1f}s)",
            file=sys.stderr,
            flush=True,
        )
    report, summary = build_report(rows, metas)
    payload = {
        "generated_at": int(time.time()),
        "definitions": {
            "timeframe": "M5",
            "fill_windows": FILL_WINDOWS,
            "primary_fill_bars": PRIMARY_FILL_BARS,
            "settle_bars": SETTLE_BARS,
            "sl_buffer_atr": SL_BUFFER_ATR,
            "min_risk_atr": MIN_RISK_ATR,
        },
        "metas": metas,
        "summary": summary,
        "row_count": len(rows),
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    OUT_REPORT.write_text(report + "\n", encoding="utf-8")
    print(report)
    print(f"\nWrote {OUT_JSON} and {OUT_REPORT}", file=sys.stderr)


if __name__ == "__main__":
    main()
