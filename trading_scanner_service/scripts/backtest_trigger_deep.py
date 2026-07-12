"""Full-chain deep backtest: M15 sweep-reversal parent -> M5 three-step trigger -> settle.

Data: data/history/{SYMBOL}_{TF}.jsonl produced by scripts/fetch_history.py (real
exchange klines, no simulation). Strictly walk-forward: parents are detected at the
M15 bar close where the reclaim prints; M5 triggers only use bars after that close.

Chain
  1. Parent (M15): a pre-confirmed swing extreme (SWING_K=2) gets pierced by a wick,
     and within RECLAIM_N bars a close prints back across the level -> READY parent
     (direction, swept_level, DOL = nearest untaken opposite swing liquidity, ATR15).
  2. Trigger (M5): reuses scanner_service.ltf_refine.detect_ltf_trigger (three-step:
     POI re-entry -> pullback structure -> close-through) and
     scanner_service.a_watch.detect_continuation_triggers (with-trend local sweep ->
     reclaim -> close-break). Entry = trigger bar close, SL = trigger-window extreme
     +/- 0.25*ATR(M5); |entry-SL| >= 0.5*ATR(M5) enforced on both models.
  3. Settlement on M5, 96-bar horizon, three managements:
       hold  : hold to DOL, stop at SL.
       1rbe  : +1R take half, stop to BE.
       2r    : +2R take half, stop to BE from +1R (approximation, see below).
     Conservatism: same-bar SL+TP double-touch counts as loss first. Approximation
     declared: stop moves (BE arming) take effect from the NEXT bar after the
     triggering touch (intrabar sequence unknowable from OHLC).
     Unresolved after 96 bars -> 'expired', marked to the last bar's (H+L)/2.

Quality gates (per trigger, independent booleans)
  G1 with-D1 : last 60 completed D1 bars' range; close in lower half -> longs are
               with-D1, upper half -> shorts are with-D1.
  G2 HTF POI : parent zone [swept_level, sweep extreme] overlaps an H4 array active
               at parent time: (a) H4 confirmed swing level (same side as the trade:
               swing high for SHORT / swing low for LONG) +/- 0.25*ATR(H4), not
               closed through since confirmation; or (b) H4 3-bar FVG in the trade
               direction (bear FVG above for SHORT: bar1.low > bar3.high; mirror for
               LONG), not closed through its far edge. H4 is resampled from M15 (UTC).
  G3 session : trigger bar UTC hour in London 08-11 or NY 13-17. Crypto counts as
               PASS by convention (24h market); a crypto-only session split is
               reported separately.
  G4 RR>=2   : planned RR = |entry-DOL| / |entry-SL| >= 2. RR>=3 also sliced.
  G5 fresh   : trigger bar within 24 M15 bars (6h) of the parent bar.

Grades: B = all valid triggers; A = G1&G4; S = G1&G2&G4. G3/G5 reported as
separate slices only, not folded into the default grade definitions.

Run:  python3 scripts/backtest_trigger_deep.py
"""

from __future__ import annotations

import json
import sys
import time
from bisect import bisect_left, bisect_right
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scanner_service.sources import Bar  # noqa: E402
from scanner_service.structure import (  # noqa: E402
    SWING_K, barbwire, climax_risk, find_swings, hl_count, micro_channel,
    signal_bar_quality, trigger_failed_early)
from scanner_service.ltf_refine import detect_ltf_trigger  # noqa: E402
from scanner_service.a_watch import detect_continuation_triggers  # noqa: E402

HIST = ROOT / "data" / "history"

CRYPTO = {"BTC", "ETH", "SOL", "DOGE", "XRP", "SUI", "HYPE", "PEPE", "ZEC", "TAO", "WLD"}
NONCRYPTO = ["XAUUSD", "XAGUSD", "XTIUSD", "NAS100", "US500", "US30",
             "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD"]
SYMBOLS = sorted(CRYPTO) + NONCRYPTO

TIER_A = {"XAUUSD", "XTIUSD", "US500"}
TIER_C = {"ZEC", "EURUSD", "US30", "PEPE"}

RECLAIM_N = 3            # closes back across the level within this many M15 bars of the pierce
SWEEP_LOOKBACK = 16      # window in which the pierce extreme must be the local extreme
SWING_SCOPE = 120        # how far back swings are considered (mirrors live 120-bar scans)
FILL_WINDOW_S = 24 * 3600
SETTLE_BARS = 96
MIN_RISK_ATR5 = 0.5
SL_BUF = 0.25
ATR_P = 14
MIN_N = 20
NOTABLE_R = 0.15


def load(sym: str, tf: str) -> list[Bar]:
    path = HIST / f"{sym}_{tf}.jsonl"
    if not path.exists():
        return []
    bars = []
    with path.open() as fh:
        for line in fh:
            d = json.loads(line)
            bars.append(Bar(ts=int(d["ts"]), open=d["open"], high=d["high"],
                            low=d["low"], close=d["close"]))
    return bars


def rolling_atr(bars: list[Bar], period: int = ATR_P) -> list[float]:
    """atr[i] = mean TR of the last `period` TRs ending at bar i (walk-forward safe)."""
    n = len(bars)
    tr = [0.0] * n
    for i in range(1, n):
        p, c = bars[i - 1], bars[i]
        tr[i] = max(c.high - c.low, abs(c.high - p.close), abs(c.low - p.close))
    atr = [0.0] * n
    s = 0.0
    for i in range(1, n):
        s += tr[i]
        if i > period:
            s -= tr[i - period]
        atr[i] = s / min(i, period)
        atr[i] = max(atr[i], abs(bars[i].close) * 1e-6, 1e-9)
    return atr


# ---------------- parent generation (M15, walk-forward) ----------------

def gen_parents(sym: str, m15: list[Bar]) -> list[dict]:
    n = len(m15)
    if n < 60:
        return []
    swings = find_swings(m15)
    atr = rolling_atr(m15)
    highs = [b.high for b in m15]
    lows = [b.low for b in m15]
    closes = [b.close for b in m15]
    sw_high = [s for s in swings if s.kind == "high"]
    sw_low = [s for s in swings if s.kind == "low"]

    level_cache: dict[tuple[str, int], float | None] = {}

    def swept_level(side: str, idx: int) -> float | None:
        """Highest (lowest) pre-confirmed intact swing level pierced by the extreme at idx."""
        key = (side, idx)
        if key in level_cache:
            return level_cache[key]
        lo_scope = idx - SWING_SCOPE
        best = None
        pool = sw_high if side == "high" else sw_low
        ext = highs[idx] if side == "high" else lows[idx]
        for s in pool:
            if s.index < lo_scope or s.confirmed_at >= idx:
                continue
            if side == "high":
                if not (s.price < ext):
                    continue
                if any(closes[j] > s.price for j in range(s.confirmed_at + 1, idx)):
                    continue  # already broken by close before the pierce -> not liquidity
                best = s.price if best is None else max(best, s.price)
            else:
                if not (s.price > ext):
                    continue
                if any(closes[j] < s.price for j in range(s.confirmed_at + 1, idx)):
                    continue
                best = s.price if best is None else min(best, s.price)
        level_cache[key] = best
        return best

    def dol_for(i: int, direction: str) -> tuple[float | None, float | None]:
        """Nearest + runner untaken opposite swing liquidity as of bar i."""
        px = closes[i]
        levels = []
        pool = sw_low if direction == "SHORT" else sw_high
        for s in pool:
            if s.confirmed_at > i or s.index < i - SWING_SCOPE:
                continue
            taken = False
            for j in range(s.confirmed_at + 1, i + 1):
                if (direction == "SHORT" and lows[j] < s.price) or \
                   (direction == "LONG" and highs[j] > s.price):
                    taken = True
                    break
            if taken:
                continue
            if direction == "SHORT" and s.price < px:
                levels.append(s.price)
            elif direction == "LONG" and s.price > px:
                levels.append(s.price)
        levels.sort(reverse=(direction == "SHORT"))
        return (levels[0] if levels else None, levels[1] if len(levels) > 1 else None)

    parents = []
    seen = set()
    for i in range(40, n):
        for side in ("high", "low"):
            w0 = i - SWEEP_LOOKBACK + 1
            if side == "high":
                idx = max(range(w0, i + 1), key=lambda j: highs[j])
            else:
                idx = min(range(w0, i + 1), key=lambda j: lows[j])
            if i - idx > RECLAIM_N:
                continue
            level = swept_level(side, idx)
            if level is None:
                continue
            # reclaim: bar i is the FIRST close back across the level since the pierce
            if side == "high":
                if not (closes[i] < level):
                    continue
                if any(closes[j] < level for j in range(idx, i)):
                    continue
            else:
                if not (closes[i] > level):
                    continue
                if any(closes[j] > level for j in range(idx, i)):
                    continue
            key = (side, m15[idx].ts, round(level, 10))
            if key in seen:
                continue
            seen.add(key)
            direction = "SHORT" if side == "high" else "LONG"
            dol, runner = dol_for(i, direction)
            if dol is None:
                continue
            ext = highs[idx] if side == "high" else lows[idx]
            a = atr[i]
            sl = ext + SL_BUF * a if side == "high" else ext - SL_BUF * a
            parents.append({
                "symbol": sym, "tf": "M15", "direction": direction, "state": "READY",
                "swept_level": level, "extreme": ext, "dol": dol, "dol_runner": runner,
                "sl": sl, "atr15": a, "mss": None, "cisd": None,
                "parent_bar_ts": m15[i].ts,
                "ts": m15[i].ts + 900 - 1,  # parent known at M15 close; M5 uses bars strictly after
            })
    return parents


# ---------------- settlement ----------------

def settle(bars: list[Bar], direction: str, entry: float, sl: float, tp: float) -> dict:
    s = 1.0 if direction == "LONG" else -1.0
    risk = (entry - sl) * s
    tp_r = (tp - entry) * s / risk

    def adverse(b: Bar, level: float) -> bool:
        return b.low <= level if s > 0 else b.high >= level

    def fav(b: Bar, level: float) -> bool:
        return b.high >= level if s > 0 else b.low <= level

    one_r = entry + s * risk
    two_r = entry + s * 2 * risk

    out = {}
    horizon = bars[:SETTLE_BARS]
    if not horizon:
        return {"hold": 0.0, "r1be": 0.0, "r2": 0.0, "outcome": "expired"}
    mid = (horizon[-1].high + horizon[-1].low) / 2
    mid_r = (mid - entry) * s / risk

    # --- hold to DOL ---
    res = None
    for b in horizon:
        if adverse(b, sl):          # conservative: loss first on double-touch
            res, out["outcome"] = -1.0, "loss"
            break
        if fav(b, tp):
            res, out["outcome"] = tp_r, "win"
            break
    if res is None:
        res, out["outcome"] = mid_r, "expired"
    out["hold"] = res

    # --- +1R half + BE (stop move effective next bar) ---
    stop, banked, frac, armed = sl, 0.0, 1.0, False
    res = None
    for b in horizon:
        if adverse(b, stop):
            res = banked + frac * ((stop - entry) * s / risk)
            break
        if not armed and tp_r > 1 and fav(b, one_r):
            banked += 0.5
            frac, armed = 0.5, True
            stop = entry  # effective from next bar
        if fav(b, tp):
            res = banked + frac * tp_r
            break
    if res is None:
        res = banked + frac * mid_r
    out["r1be"] = res

    # --- +2R half, BE from +1R (both stop moves effective next bar) ---
    stop, banked, frac, be, half = sl, 0.0, 1.0, False, False
    res = None
    for b in horizon:
        if adverse(b, stop):
            res = banked + frac * ((stop - entry) * s / risk)
            break
        if not be and tp_r > 1 and fav(b, one_r):
            be = True
            stop = entry
        if not half and tp_r > 2 and fav(b, two_r):
            banked += 0.5 * 2
            frac, half = 0.5, True
        if fav(b, tp):
            res = banked + frac * tp_r
            break
    if res is None:
        res = banked + frac * mid_r
    out["r2"] = res
    return out


# ---------------- H4 / D1 context ----------------

def resample_h4(m15: list[Bar]) -> list[Bar]:
    out = []
    cur_key, o, h, l, c = None, 0.0, 0.0, 0.0, 0.0
    for b in m15:
        key = b.ts // 14400 * 14400
        if key != cur_key:
            if cur_key is not None:
                out.append(Bar(ts=cur_key, open=o, high=h, low=l, close=c))
            cur_key, o, h, l, c = key, b.open, b.high, b.low, b.close
        else:
            h, l, c = max(h, b.high), min(l, b.low), b.close
    if cur_key is not None:
        out.append(Bar(ts=cur_key, open=o, high=h, low=l, close=c))
    return out


class H4Context:
    def __init__(self, m15: list[Bar]):
        self.bars = resample_h4(m15)
        self.ts = [b.ts for b in self.bars]
        self.swings = find_swings(self.bars)
        self.atr = rolling_atr(self.bars)
        # FVGs: (formed_idx=i+2, kind, near_edge, far_edge)
        self.fvgs = []
        bb = self.bars
        for i in range(len(bb) - 2):
            if bb[i].low > bb[i + 2].high:   # bear FVG (gap down)
                self.fvgs.append((i + 2, "bear", bb[i + 2].high, bb[i].low))
            if bb[i].high < bb[i + 2].low:   # bull FVG (gap up)
                self.fvgs.append((i + 2, "bull", bb[i + 2].low, bb[i].high))

    def g2(self, parent: dict) -> bool:
        """Parent zone overlaps an H4 array active at parent time."""
        pts = parent["parent_bar_ts"]
        k = bisect_right(self.ts, pts) - 1  # last H4 bar STARTED at/before parent
        k -= 1                              # use only COMPLETED H4 bars
        if k < 5:
            return False
        zlo = min(parent["swept_level"], parent["extreme"])
        zhi = max(parent["swept_level"], parent["extreme"])
        short = parent["direction"] == "SHORT"
        bb = self.bars
        # (a) same-side H4 swing level +/- 0.25*ATR(H4), not closed through since confirm
        want = "high" if short else "low"
        for sw in self.swings:
            if sw.kind != want or sw.confirmed_at > k or sw.index < k - SWING_SCOPE:
                continue
            broken = False
            for j in range(sw.confirmed_at + 1, k + 1):
                if (short and bb[j].close > sw.price) or (not short and bb[j].close < sw.price):
                    broken = True
                    break
            if broken:
                continue
            tol = 0.25 * self.atr[min(sw.confirmed_at, len(self.atr) - 1)]
            if zlo <= sw.price + tol and zhi >= sw.price - tol:
                return True
        # (b) H4 FVG in trade direction, far edge not closed through
        want_fvg = "bear" if short else "bull"
        for formed, kind, lo, hi in self.fvgs:
            if kind != want_fvg or formed > k or formed < k - SWING_SCOPE:
                continue
            invalid = False
            for j in range(formed + 1, k + 1):
                if (short and bb[j].close > hi) or (not short and bb[j].close < lo):
                    invalid = True
                    break
            if invalid:
                continue
            if zlo <= hi and zhi >= lo:
                return True
        return False


class D1Context:
    def __init__(self, d1: list[Bar]):
        self.bars = d1
        self.close_ts = [b.ts + 86400 for b in d1]  # completion time of each D1 bar

    def with_d1(self, ts: int, direction: str) -> bool | None:
        k = bisect_right(self.close_ts, ts)  # bars completed at/before ts
        if k < 20:
            return None
        w = self.bars[max(0, k - 60):k]
        hi, lo = max(b.high for b in w), min(b.low for b in w)
        if hi <= lo:
            return None
        pos = (w[-1].close - lo) / (hi - lo)
        return (direction == "LONG" and pos < 0.5) or (direction == "SHORT" and pos >= 0.5)


# ---------------- per-symbol pipeline ----------------

def run_symbol(sym: str) -> tuple[list[dict], dict]:
    m15 = load(sym, "M15")
    m5 = load(sym, "M5")
    d1 = load(sym, "D1")
    meta = {"symbol": sym, "m15_bars": len(m15), "m5_bars": len(m5),
            "m15_span": None, "m5_span": None, "parents": 0}
    if m15:
        meta["m15_span"] = (m15[0].ts, m15[-1].ts)
    if m5:
        meta["m5_span"] = (m5[0].ts, m5[-1].ts)
    if len(m15) < 200 or len(m5) < 500:
        return [], meta

    parents = gen_parents(sym, m15)
    meta["parents"] = len(parents)
    h4ctx = H4Context(m15)
    d1ctx = D1Context(d1)
    m5_ts = [b.ts for b in m5]
    atr5 = rolling_atr(m5)

    trades = []
    seen = set()
    for p in parents:
        lo = bisect_right(m5_ts, p["ts"])
        hi = bisect_right(m5_ts, p["ts"] + FILL_WINDOW_S)
        window = m5[lo:hi]
        if len(window) < 10:
            continue
        cands = []
        c = detect_ltf_trigger(p, window)
        if c is not None:
            cands.append(("三步走", c))
        cont = detect_continuation_triggers(p, window)
        if cont:
            cont.sort(key=lambda x: x["_trigger_ts"])
            cands.append(("顺势延续", cont[0]))
        for model, c in cands:
            trig_ts = c["_trigger_ts"]
            key = (sym, model, c["direction"], trig_ts)
            if key in seen:
                continue
            gi = bisect_left(m5_ts, trig_ts)
            if gi >= len(m5) or m5_ts[gi] != trig_ts:
                continue
            entry, sl, dol = float(c["price"]), float(c["sl"]), float(c["dol"])
            risk = abs(entry - sl)
            a5 = atr5[gi]
            if risk < MIN_RISK_ATR5 * a5:
                continue  # |entry-SL| >= 0.5*ATR(M5) gate on BOTH models
            reward = (dol - entry) if c["direction"] == "LONG" else (entry - dol)
            if reward <= 0 or risk <= 0:
                continue
            seen.add(key)
            fut = m5[gi + 1: gi + 1 + SETTLE_BARS]
            if not fut:
                continue
            res = settle(fut, c["direction"], entry, sl, dol)
            rr = reward / risk
            fresh_bars = (trig_ts - p["parent_bar_ts"]) / 900.0
            hour = time.gmtime(trig_ts).tm_hour
            in_session = (8 <= hour < 11) or (13 <= hour < 17)
            g1 = d1ctx.with_d1(trig_ts, c["direction"])
            # veto gates G6-G8: only closed M5 bars up to and incl. the trigger bar
            ctx5 = m5[max(0, gi - 60): gi + 1]
            g6, _ = barbwire(ctx5)
            g7, _ = climax_risk(ctx5, c["direction"])
            mc_dir, _ = micro_channel(ctx5)
            g8 = mc_dir is not None and mc_dir != c["direction"]
            g9, _ = signal_bar_quality(ctx5, c["direction"])  # last bar = trigger bar (closed)
            g10 = hl_count(ctx5[-10:], c["direction"])  # H/L count at trigger, 10-bar window
            # G11 uses POST-trigger info -> exit rule, NOT a filter gate
            later = m5[gi + 1: gi + 3]
            g11_failed = trigger_failed_early(m5[gi], later, c["direction"])
            g11_exit_r = None
            if g11_failed:
                sgn = 1.0 if c["direction"] == "LONG" else -1.0
                for b in later:
                    if (c["direction"] == "LONG" and b.close < m5[gi].open) or \
                       (c["direction"] == "SHORT" and b.close > m5[gi].open):
                        g11_exit_r = max((b.close - entry) * sgn / risk, -1.0)
                        break
            trades.append({
                "symbol": sym, "model": model, "direction": c["direction"],
                "ts": trig_ts, "month": time.strftime("%Y-%m", time.gmtime(trig_ts)),
                "day": time.strftime("%Y-%m-%d", time.gmtime(trig_ts)),
                "crypto": sym in CRYPTO,
                "rr": rr, "hold": res["hold"], "r1be": res["r1be"], "r2": res["r2"],
                "outcome": res["outcome"],
                "g1": g1, "g2": h4ctx.g2(p),
                "g3": True if sym in CRYPTO else in_session,
                "g3_raw": in_session,
                "g4": rr >= 2.0, "rr3": rr >= 3.0,
                "g5": fresh_bars <= 24,
                "g6": g6, "g7": g7, "g8": g8, "g9": g9, "g10": g10,
                "g11_failed": g11_failed, "g11_exit_r": g11_exit_r,
            })
    return trades, meta


# ---------------- reporting ----------------

def cell(trades: list[dict]) -> str:
    n = len(trades)
    if n == 0:
        return "n=0 -"
    avg_h = sum(t["hold"] for t in trades) / n
    avg_1 = sum(t["r1be"] for t in trades) / n
    avg_2 = sum(t["r2"] for t in trades) / n
    wr = sum(1 for t in trades if t["hold"] > 0) / n
    flag = " [n<20不可用]" if n < MIN_N else ""
    return f"n={n} hold={avg_h:+.2f}R 1rbe={avg_1:+.2f}R 2r={avg_2:+.2f}R 胜率{wr:.0%}{flag}"


def gate_verdict(passed: list[dict], failed: list[dict]) -> str:
    if len(passed) < 30 or len(failed) < 30:
        return "分不清(样本不足)"
    d = sum(t["hold"] for t in passed) / len(passed) - sum(t["hold"] for t in failed) / len(failed)
    if d >= NOTABLE_R:
        return f"支持保留(Δhold={d:+.2f}R)"
    if d <= -NOTABLE_R:
        return f"数据反对(Δhold={d:+.2f}R)，建议不进A/S定义"
    return f"分不清(Δhold={d:+.2f}R，<0.15R属噪音)"


def tier_of(sym: str) -> str:
    if sym in TIER_A:
        return "A层"
    if sym in TIER_C:
        return "C层"
    return "B层"


def main() -> None:
    all_trades: list[dict] = []
    metas = []
    for sym in SYMBOLS:
        t0 = time.time()
        trades, meta = run_symbol(sym)
        all_trades.extend(trades)
        metas.append(meta)
        print(f"[{sym}] parents={meta['parents']} trades={len(trades)} ({time.time()-t0:.1f}s)",
              file=sys.stderr, flush=True)

    T = all_trades
    print("=" * 78)
    print("深历史全链路回测：M15扫荡反转parent -> M5三步走/顺势延续触发")
    print("=" * 78)

    print("\n## 数据深度（真实K线，无模拟）")
    for m in metas:
        def fmt(span):
            if not span:
                return "缺失"
            return (f"{time.strftime('%Y-%m-%d', time.gmtime(span[0]))}~"
                    f"{time.strftime('%Y-%m-%d', time.gmtime(span[1]))}"
                    f"({(span[1]-span[0])/86400:.0f}d)")
        print(f"  {m['symbol']:<8} M15 {fmt(m['m15_span'])} {m['m15_bars']}根 | "
              f"M5 {fmt(m['m5_span'])} {m['m5_bars']}根 | parents={m['parents']}")

    if not T:
        print("\n无触发。")
        return

    days = len({t["day"] for t in T})
    sym_days = len({(t["symbol"], t["day"]) for t in T})
    span_days = (max(t["ts"] for t in T) - min(t["ts"] for t in T)) / 86400
    print(f"\n## 总量：触发 {len(T)} 笔；独立样本粗估(symbol-day去重)={sym_days}；"
          f"覆盖 {span_days:.0f} 天，约 {len(T)/max(span_days,1):.1f} 笔/天(全{len(SYMBOLS)}品种合计)")
    print("同bar双触保守先损；BE/减半的止损移动次bar生效(近似，声明偏差)；"
          "96根M5未决按最后bar中价折算expired。")

    print("\n## 三套管理对比（整体）")
    print(f"  整体: {cell(T)}")
    exp = sum(1 for t in T if t["outcome"] == "expired")
    print(f"  expired占比 {exp/len(T):.0%}")

    print("\n## 分触发模型（parent全部来自M15，tf来源维度退化为模型维度）")
    for mdl in ("三步走", "顺势延续"):
        print(f"  {mdl}: {cell([t for t in T if t['model'] == mdl])}")

    print("\n## 分品种")
    for sym in SYMBOLS:
        sub = [t for t in T if t["symbol"] == sym]
        if sub:
            print(f"  {sym:<8} {cell(sub)}")

    print("\n## 分层级（A层=XAUUSD/XTIUSD/US500，C层=ZEC/EURUSD/US30/PEPE，其余B层）")
    for tier in ("A层", "B层", "C层"):
        print(f"  {tier}: {cell([t for t in T if tier_of(t['symbol']) == tier])}")

    print("\n## 顺D1 vs 逆D1（近60根D1区间上下半近似；触发时点判定）")
    w = [t for t in T if t["g1"] is True]
    a = [t for t in T if t["g1"] is False]
    u = [t for t in T if t["g1"] is None]
    print(f"  顺D1: {cell(w)}")
    print(f"  逆D1: {cell(a)}")
    if u:
        print(f"  D1数据不足未判定: n={len(u)}")

    print("\n## 按月稳定性（整体，hold管理）")
    months = sorted({t["month"] for t in T})
    for mo in months:
        print(f"  {mo}: {cell([t for t in T if t['month'] == mo])}")

    # ---------------- quality gates ----------------
    print("\n" + "=" * 78)
    print("## 质量门贡献分析（各门独立布尔；hold管理R为主判据）")
    gates = [
        ("G1 顺D1", lambda t: t["g1"] is True, lambda t: t["g1"] is False),
        ("G2 HTF重合(H4摆动±0.25ATR或H4FVG)", lambda t: t["g2"], lambda t: not t["g2"]),
        ("G3 时段(非加密伦敦8-11/纽约13-17UTC，加密视为通过)",
         lambda t: t["g3"], lambda t: not t["g3"]),
        ("G4 计划RR>=2", lambda t: t["g4"], lambda t: not t["g4"]),
        ("G5 触发新鲜<=24根M15", lambda t: t["g5"], lambda t: not t["g5"]),
    ]
    for name, fp, ff in gates:
        p = [t for t in T if fp(t)]
        f = [t for t in T if ff(t)]
        print(f"\n  {name}")
        print(f"    通过  : {cell(p)}")
        print(f"    不通过: {cell(f)}")
        print(f"    判定  : {gate_verdict(p, f)}")

    print("\n## 否决门 G6-G8（假设：被标中的触发更差；标中率过高=代价过高）")
    vetoes = [
        ("G6 barbwire绞肉区", "g6"),
        ("G7 climax同向追高", "g7"),
        ("G8 微通道逆势", "g8"),
    ]
    for name, key in vetoes:
        hit = [t for t in T if t[key]]
        miss = [t for t in T if not t[key]]
        rate = len(hit) / len(T)
        print(f"\n  {name}（标中率 {rate:.0%}{'，>40%代价过高' if rate > 0.4 else ''}）")
        print(f"    标中  : {cell(hit)}")
        print(f"    未标中: {cell(miss)}")
        if len(hit) < 30 or len(miss) < 30:
            v = "分不清(样本不足)，不建议接入a_watch"
        else:
            d = (sum(t['hold'] for t in hit) / len(hit)
                 - sum(t['hold'] for t in miss) / len(miss))
            if d <= -NOTABLE_R:
                v = f"支持否决(标中更差Δ={d:+.2f}R)"
            elif d >= NOTABLE_R:
                v = f"数据反对(标中反而更好Δ={d:+.2f}R)，不建议接入a_watch"
            else:
                v = f"分不清(Δ={d:+.2f}R，<0.15R属噪音)，不建议接入a_watch"
        print(f"    判定  : {v}")

    print("\n## G9 信号棒质量（触发bar三档，假设 strong > ok > weak）")
    q_subs = {q: [t for t in T if t["g9"] == q] for q in ("strong", "ok", "weak")}
    for q, sub in q_subs.items():
        print(f"  {q:<6} 占比{len(sub)/len(T):>4.0%}: {cell(sub)}")
    sN, wN = q_subs["strong"], q_subs["weak"]
    if len(sN) < 30 or len(wN) < 30:
        print("  判定  : 分不清(样本不足)")
    else:
        d = (sum(t["hold"] for t in sN) / len(sN)
             - sum(t["hold"] for t in wN) / len(wN))
        if d >= NOTABLE_R:
            print(f"  判定  : 支持保留(strong-weak Δhold={d:+.2f}R)")
        elif d <= -NOTABLE_R:
            print(f"  判定  : 数据反对(strong反而更差Δ={d:+.2f}R)")
        else:
            print(f"  判定  : 分不清(Δ={d:+.2f}R，<0.15R属噪音)")

    print("\n## G10 二次入场计数（触发时刻H/L计数，10根M5窗口；假设 count==2 更好）")
    def g10_bucket(t):
        c = t["g10"]
        return "0" if c == 0 else "1" if c == 1 else "2(二次入场)" if c == 2 else ">=3"
    for bk in ("0", "1", "2(二次入场)", ">=3"):
        sub = [t for t in T if g10_bucket(t) == bk]
        print(f"  count={bk:<9} 占比{len(sub)/len(T):>4.0%}: {cell(sub)}")
    two = [t for t in T if g10_bucket(t) == "2(二次入场)"]
    rest = [t for t in T if g10_bucket(t) != "2(二次入场)"]
    print(f"  判定  : {gate_verdict(two, rest)}")

    print("\n## G11 失败触发早退（出场规则，用触发后1-2根信息，非过滤门）")
    fl = [t for t in T if t["g11_failed"] and t["g11_exit_r"] is not None]
    print(f"  失败触发占比: {len(fl)}/{len(T)} = {len(fl)/len(T):.0%}")
    if fl:
        base = sum(t["hold"] for t in fl) / len(fl)
        early = sum(t["g11_exit_r"] for t in fl) / len(fl)
        rescued = sum(1 for t in fl if t["outcome"] == "win")
        print(f"  失败组基线(等-1R或DOL): avg {base:+.2f}R | 早退(失败根收盘离场): avg {early:+.2f}R"
              f" | 早退净省 {early-base:+.2f}R/笔")
        print(f"  误杀率(判失败但后来仍到DOL): {rescued}/{len(fl)} = {rescued/len(fl):.0%}")
        print("  口径: 若失败根收盘已越过SL，早退价按-1R计(实际两种路径都已被SL带走)。")
        if len(fl) < 30:
            print("  判定  : 分不清(样本不足)")
        elif early - base >= NOTABLE_R:
            print(f"  判定  : 支持接入为出场规则(每笔省{early-base:+.2f}R)")
        elif early - base <= -NOTABLE_R:
            print(f"  判定  : 数据反对(早退反而亏{early-base:+.2f}R)")
        else:
            print(f"  判定  : 分不清(Δ={early-base:+.2f}R，<0.15R属噪音)")

    r3 = [t for t in T if t["rr3"]]
    print(f"\n  附加切片 RR>=3: {cell(r3)}")
    nc = [t for t in T if not t["crypto"]]
    cr = [t for t in T if t["crypto"]]
    print(f"  附加切片 加密在高参与时段内: {cell([t for t in cr if t['g3_raw']])}")
    print(f"  附加切片 加密在高参与时段外: {cell([t for t in cr if not t['g3_raw']])}")
    print(f"  附加切片 非加密时段内: {cell([t for t in nc if t['g3_raw']])}")
    print(f"  附加切片 非加密时段外: {cell([t for t in nc if not t['g3_raw']])}")

    print("\n## 叠加分级：B=全部触发；A=G1&G4；S=G1&G2&G4（G3/G5仅附加切片）")
    grades = {
        "B": T,
        "A": [t for t in T if t["g1"] is True and t["g4"]],
        "S": [t for t in T if t["g1"] is True and t["g2"] and t["g4"]],
    }
    for g, sub in grades.items():
        print(f"\n  {g}级: {cell(sub)}")
        sdays = len({(t['symbol'], t['day']) for t in sub})
        print(f"    独立样本(symbol-day)={sdays}；信号量 {len(sub)/max(span_days,1):.2f} 笔/天")
        for mo in months:
            ms = [t for t in sub if t["month"] == mo]
            if ms:
                print(f"    {mo}: {cell(ms)}")

    print("\n## 信号量漏斗（笔/天，全品种合计）")
    for g, sub in grades.items():
        print(f"  {g}: {len(sub)}笔 = {len(sub)/max(span_days,1):.2f}/天")

    out = ROOT / "data" / "backtest_trigger_deep_trades.jsonl"
    with out.open("w") as fh:
        for t in T:
            fh.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"\n明细已写 {out}")


if __name__ == "__main__":
    main()
