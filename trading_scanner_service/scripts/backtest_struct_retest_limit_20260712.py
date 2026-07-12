#!/usr/bin/env python3
"""方案B回测：MSS/CISD 破位结构价回测限价 vs 确认K极值 stop（2026-07-12）。

同一事件引擎与数据（backtest_fvg_ifvg_entries / backtest_trigger_deep 本地缓存），
只换订单表达：

  struct_limit      = 事件收盘确认后，在刚被破的 MSS/CISD 结构价挂回测限价；
                      成交前收盘穿回错误方向 → cancelled；目标先到未成交 → missed_alpha 记 0R；
                      成交后只认硬损/目标（无软出场）。
  struct_limit_soft = 同上，但成交后结构价被反向收盘穿回 → 收盘价软出场（对照组）。
  基线              = next_open / event_stop（与前次回测同定义，同一批事件直接可比）。

窗口/结算/止损/口径全部沿用上一份回测（12 根主窗口、6/24 敏感性、96 根结算、
同 bar 先止损、0.25ATR buffer、|entry-SL|>=0.5ATR、unfilled=0R/signal）。
参数零新增、零扫描。只读本地缓存，不拉网。

用法: python3 scripts/backtest_struct_retest_limit_20260712.py
"""
from __future__ import annotations

import sys
import time
from bisect import bisect_left, bisect_right
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import backtest_trigger_deep as base
import backtest_fvg_ifvg_entries as fv

PRIMARY = fv.PRIMARY_FILL_BARS
WINDOWS = fv.FILL_WINDOWS
SETTLE = fv.SETTLE_BARS
MIN_N = fv.MIN_N
NOTABLE_R = fv.NOTABLE_R
ORDERS = ("next_open", "event_stop", "struct_limit", "struct_limit_soft")


def _event_orders(parent, window, m5, m5_ts, atr_series, zone_idx, event, event_name, fill_bars):
    event_bar = window[event.index]
    gi = bisect_left(m5_ts, event_bar.ts)
    if gi >= len(m5) or m5[gi].ts != event_bar.ts:
        return []
    future = m5[gi + 1: gi + 1 + SETTLE]
    if not future:
        return []
    direction = parent["direction"]
    target = float(parent["dol"])
    atr = fv._atr_at(atr_series, gi)
    sequence = window[zone_idx: event.index + 1]
    setups = []

    next_open = future[0].open
    sl = fv._stop_for_entry(direction, next_open, sequence, atr)
    setups.append(("next_open", next_open, sl,
                   fv.simulate_market_entry(future, direction, sl, target, SETTLE)))

    stop_entry = event_bar.low if direction == "SHORT" else event_bar.high
    sl = fv._stop_for_entry(direction, stop_entry, sequence, atr)
    setups.append(("event_stop", stop_entry, sl,
                   fv.simulate_stop_order(future, direction, stop_entry, sl, target,
                                          fill_bars, SETTLE)))

    # 方案B：刚被破的结构价 = event.level（MSS 摆动价 / CISD delivery open，单一数字）
    entry = float(event.level)
    sl = fv._stop_for_entry(direction, entry, sequence, atr)
    for name, soft in (("struct_limit", False), ("struct_limit_soft", True)):
        setups.append((name, entry, sl,
                       fv.simulate_limit_order(future, direction, entry, sl, target,
                                               invalidation_close=entry,
                                               valid_bars=fill_bars, settle_bars=SETTLE,
                                               soft_exit_after_fill=soft)))

    rows = []
    sign = 1.0 if direction == "LONG" else -1.0
    for order_name, e, s, result in setups:
        risk = sign * (e - s)
        reward = sign * (target - e)
        if risk <= 0 or reward <= 0:
            continue
        rows.append({
            "symbol": parent["symbol"], "direction": direction, "event": event_name,
            "event_ts": event_bar.ts, "order": order_name, "fill_window": fill_bars,
            "entry": e, "sl": s, "target": target, "planned_rr": reward / risk,
            "filled": result.filled, "outcome": result.outcome, "result_r": result.result_r,
            "crypto": parent["symbol"] in base.CRYPTO,
            "month": time.strftime("%Y-%m", time.gmtime(event_bar.ts)),
        })
    return rows


def run_symbol(symbol):
    m15 = base.load(symbol, "M15")
    m5 = base.load(symbol, "M5")
    if len(m15) < 200 or len(m5) < 500:
        return []
    parents = base.gen_parents(symbol, m15)
    m5_ts = [b.ts for b in m5]
    atr = base.rolling_atr(m5)
    rows, seen = [], set()
    for parent in reversed(parents):
        lo = bisect_right(m5_ts, parent["ts"])
        hi = bisect_right(m5_ts, parent["ts"] + base.FILL_WINDOW_S)
        window = m5[lo:hi]
        if len(window) < 10:
            continue
        zone_idx = fv._zone_entry_idx(parent, window)
        if zone_idx is None:
            continue
        mss = fv.first_mss_event(window, parent["direction"], zone_idx)
        cisd = fv.first_cisd_event(window, parent["direction"], zone_idx)
        events = []
        if mss is not None:
            events.append(("mss", mss))
        if cisd is not None:
            events.append(("cisd", cisd))
        if mss is not None and cisd is not None:
            both_idx = max(mss.index, cisd.index)
            both_level = mss.level if mss.index >= cisd.index else cisd.level
            events.append(("mss+cisd", fv.StructureEvent("both", both_idx, both_level)))
        for event_name, event in events:
            key = (symbol, parent["direction"], event_name, window[event.index].ts)
            if key in seen:
                continue
            seen.add(key)
            for fill_bars in WINDOWS:
                rows.extend(_event_orders(parent, window, m5, m5_ts, atr,
                                          zone_idx, event, event_name, fill_bars))
    return rows


def agg(rows):
    n = len(rows)
    if n == 0:
        return None
    fills = [r for r in rows if r["filled"]]
    fill_rate = len(fills) / n
    avg_sig = sum(r["result_r"] for r in rows) / n
    avg_fill = sum(r["result_r"] for r in fills) / len(fills) if fills else 0.0
    win_fill = sum(1 for r in fills if r["result_r"] > 0) / len(fills) if fills else 0.0
    missed = sum(1 for r in rows if r["outcome"] == "missed_alpha") / n
    cancelled = sum(1 for r in rows if r["outcome"] == "cancelled") / n
    return n, fill_rate, win_fill, avg_sig, avg_fill, missed, cancelled


def table(P, rows, title):
    P(f"\n## {title}\n")
    P("| Event | Order | n | Fill | Win/fill | AvgR/signal | AvgR/fill | missed | cancelled |")
    P("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for ev in ("mss", "cisd", "mss+cisd"):
        for od in ORDERS:
            sub = [r for r in rows if r["event"] == ev and r["order"] == od]
            a = agg(sub)
            if a is None:
                continue
            n, fr, wf, s, f, ms, cc = a
            P(f"| {ev} | {od} | {n} | {fr:.1%} | {wf:.1%} | {s:+.3f} | {f:+.3f} | {ms:.1%} | {cc:.1%} |")


def main():
    out = []
    P = out.append
    P("# 方案B: MSS/CISD 破位结构价回测限价 (struct_limit) — 2026-07-12")
    P("")
    P("同事件同数据对打 next_open / event_stop 基线；unfilled=0R/signal；口径同前次回测。")
    all_rows = []
    for sym in base.SYMBOLS:
        rows = run_symbol(sym)
        all_rows.extend(rows)
        print(f"{sym}: rows={len(rows)}", file=sys.stderr)
    prim = [r for r in all_rows if r["fill_window"] == PRIMARY]
    table(P, prim, f"Primary results ({PRIMARY} bars)")

    # first event per symbol/day: keep rows whose event_ts == min ts of (symbol, day, event) group
    firsts = {}
    for r in prim:
        day = time.strftime("%Y-%m-%d", time.gmtime(r["event_ts"]))
        k = (r["symbol"], day, r["event"])
        firsts.setdefault(k, r["event_ts"])
        firsts[k] = min(firsts[k], r["event_ts"])
    fed = [r for r in prim
           if firsts[(r["symbol"], time.strftime("%Y-%m-%d", time.gmtime(r["event_ts"])), r["event"])] == r["event_ts"]]
    table(P, fed, "First event per symbol/day")

    # asset split
    for label, flag in (("crypto", True), ("non-crypto", False)):
        table(P, [r for r in prim if r["crypto"] == flag], f"Asset split: {label}")

    # window sensitivity for struct_limit only
    P("\n## Fill-window sensitivity (struct_limit)\n")
    P("| Event | Window | n | Fill | AvgR/signal |")
    P("|---|---:|---:|---:|---:|")
    for ev in ("mss", "cisd", "mss+cisd"):
        for w in WINDOWS:
            sub = [r for r in all_rows
                   if r["order"] == "struct_limit" and r["event"] == ev and r["fill_window"] == w]
            a = agg(sub)
            if a is None:
                continue
            n, fr, _, s, _, _, _ = a
            P(f"| {ev} | {w} | {n} | {fr:.1%} | {s:+.3f} |")

    # monthly stability struct_limit vs event_stop
    P("\n## Monthly stability (12 bars)\n")
    P("| Event | Order | Months n>=30 | Positive | Min | Max |")
    P("|---|---|---:|---:|---:|---:|")
    for ev in ("mss", "cisd", "mss+cisd"):
        for od in ("event_stop", "struct_limit"):
            by_m = defaultdict(list)
            for r in prim:
                if r["event"] == ev and r["order"] == od:
                    by_m[r["month"]].append(r["result_r"])
            ms = {m: v for m, v in by_m.items() if len(v) >= 30}
            if not ms:
                continue
            avgs = [sum(v) / len(v) for v in ms.values()]
            P(f"| {ev} | {od} | {len(ms)} | {sum(1 for a in avgs if a > 0)} | {min(avgs):+.3f} | {max(avgs):+.3f} |")

    P("")
    P("## Guardrails")
    P("")
    P("- 口径同 backtest_fvg_ifvg_entries.md：机械合法性样本，非 edge 证明；事件按品种/日聚簇非独立。")
    P(f"- |Δ| < {NOTABLE_R}R/signal = 操作上弱证据；单侧 n<{MIN_N} 不下结论。")
    P("- 未建模：点差/手续费/滑点/延迟；止损侧 HTF 流动性未检；M5 结论不得外推 M1。")
    report = "\n".join(out)
    print(report)
    (ROOT / "data" / "backtest_struct_retest_limit.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
