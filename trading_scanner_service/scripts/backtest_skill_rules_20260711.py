#!/usr/bin/env python3
"""H4/D1 尺度回测：验证交易 skill 的结构层规则（2026-07-11）。

统一信号引擎：H4 扫荡-反转三步走（sweep -> reclaim -> 首个收盘破近端回调结构），
逐 bar 前推严格无前视。六个假设（H1-H6）在同一批信号上分桶统计。

只读：只从交易所 API 拉真实 K 线，不写任何数据文件。幂等可重跑
（结果随最新行情窗口漂移属数据本身性质，非脚本随机性；脚本内无随机数）。

用法: python3 scripts/backtest_skill_rules_20260711.py
"""
from __future__ import annotations

import bisect
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scanner_service.sources import Bar, MarketDataRouter, SourceError
from scanner_service.structure import average_true_range, find_swings

# ---------------- 生成参数（全部写进报告） ----------------
UNIVERSE = [
    "BTC", "ETH", "SOL", "DOGE", "XRP", "SUI", "HYPE", "PEPE", "ZEC", "TAO", "WLD",
    "XAUUSD", "XAGUSD", "XTIUSD",
    "NAS100", "US500", "US30",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
]
H4_LIMIT = 1000          # ~5.5 个月
D1_LIMIT = 400
SWING_K = 2              # 与 structure.py 一致
WARMUP = 60              # 前 60 根 H4 只做结构累积不出信号
RECLAIM_N = 6            # sweep 后 N 根内必须收回，否则视为 acceptance 作废
TRIGGER_N = 12           # reclaim 后 N 根内必须触发，否则作废
FRESH_W = 5              # sweep 前 5 根内该位未被 wick 刺穿（保证是"新"扫荡）
ATR_PERIOD = 14
BASE_BUFFER = 0.5        # 基线止损 buffer（×ATR H4）
BUFFERS = [0.25, 0.5, 0.75, 1.0]
HORIZON = 60             # 60 根 H4 未决 -> expired，按该 bar 中价折算
RR_MIN = 0.2             # 目标/风险 < 0.2 的退化信号剔除（计数报告）
MIN_SIM_BARS = 10        # 触发后剩余数据不足 10 根的信号剔除（计数报告）
D1_RANGE_N = 60          # H1: D1 近 60 根高低区间折价/溢价
D1_ARRAY_LOOKBACK = 100  # H2: D1 array 检索窗口
D1_SWING_PAD = 0.25      # H2: D1 swing 极值回踩区 = 极值 ± 0.25×ATR(D1)
NOTABLE_DIFF = 0.15      # 多重比较门槛：|avgR差|>=0.15R 且两侧 n>=30 才"值得注意"
MIN_N = 20               # n<20 的格标"不可用"

TIER_A = {"XAUUSD", "XTIUSD", "US500"}
TIER_C = {"ZEC", "EURUSD", "US30", "PEPE"}


# ---------------- 数据 ----------------
def fetch_all():
    router = MarketDataRouter()
    data, failed = {}, []
    for sym in UNIVERSE:
        try:
            h4 = router.bars(sym, "H4", H4_LIMIT)
            time.sleep(0.25)
            d1 = router.bars(sym, "D1", D1_LIMIT)
            time.sleep(0.25)
        except (SourceError, Exception) as exc:  # noqa: BLE001
            failed.append((sym, str(exc)[:80]))
            continue
        h4 = _dedupe(h4)
        d1 = _dedupe(d1)
        if len(h4) < WARMUP + 50 or len(d1) < 40:
            failed.append((sym, f"bars too few h4={len(h4)} d1={len(d1)}"))
            continue
        data[sym] = (h4, d1)
    return data, failed


def _dedupe(bars: list[Bar]) -> list[Bar]:
    seen, out = set(), []
    for b in sorted(bars, key=lambda x: x.ts):
        if b.ts not in seen:
            seen.add(b.ts)
            out.append(b)
    return out


# ---------------- 信号引擎（v-空间：把多头镜像成空头逻辑统一处理） ----------------
# v = +1 (SHORT, 扫高) / v = -1 (LONG, 扫低)。v*price 后，扫荡一律"向上刺穿、收回向下、
# 目标在下方"。AV[i]=bar 在 v 空间的向上极值，FV[i]=向下极值，CV=收盘，MIDV=中价。

class Sig:
    __slots__ = ("symbol", "dir", "v", "t", "ts", "entry", "extreme", "level",
                 "atr", "target", "v_entry", "v_extreme", "v_level", "v_target")

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def scan_symbol(symbol: str, bars: list[Bar]):
    """返回 (signals, skip_counts)。严格前推：bar i 的判定只用 <=i 的已收盘 bar，
    swing 只在 confirmed_at(=index+K) <= i 后可见。"""
    n = len(bars)
    swings = find_swings(bars, SWING_K)  # swing 本身只依赖局部窗口，confirmed_at 控制可见性
    skips = defaultdict(int)
    signals = []

    for v, side, opp in ((1.0, "high", "low"), (-1.0, "low", "high")):
        AV = [max(v * b.high, v * b.low) for b in bars]
        FV = [min(v * b.high, v * b.low) for b in bars]
        CV = [v * b.close for b in bars]
        side_sw = [s for s in swings if s.kind == side]   # 被扫荡的同侧 swing
        opp_sw = [s for s in swings if s.kind == opp]     # 回调结构 & 目标(DOL)所在侧
        # 预计算：同侧 swing 首次被收盘突破的 bar（v 空间向上收破 = 失效为流动性）
        fcb = {}
        for s in side_sw:
            vp = v * s.price
            fcb[id(s)] = next((j for j in range(s.confirmed_at + 1, n) if CV[j] > vp), None)
        # 预计算：对侧 swing 首次被 wick 拿走的 bar（v 空间向下刺穿 = 流动性已取）
        fwb = {}
        for s in opp_sw:
            vp = v * s.price
            fwb[id(s)] = next((j for j in range(s.confirmed_at + 1, n) if FV[j] < vp), None)

        state = None
        for i in range(WARMUP, n):
            if state is None:
                cands = []
                lo_w = max(0, i - FRESH_W)
                for s in side_sw:
                    if s.confirmed_at >= i:
                        continue
                    vp = v * s.price
                    if AV[i] <= vp:
                        continue                      # 本 bar 未刺穿
                    b = fcb[id(s)]
                    if b is not None and b < i:
                        continue                      # 早已被收盘突破，非流动性
                    if max(AV[lo_w:i], default=-1e18) > vp:
                        continue                      # 不新鲜：近 FRESH_W 根已刺穿过
                    cands.append(vp)
                if not cands:
                    continue
                state = {"lvl": max(cands), "pierce": i, "ext": AV[i], "ext_i": i, "rec": None}
            else:
                if AV[i] > state["ext"]:
                    state["ext"], state["ext_i"] = AV[i], i
                if state["rec"] is not None and CV[i] > state["lvl"]:
                    state["rec"] = None               # 收回又收上去，reclaim 作废
                if state["rec"] is None and i > state["pierce"] and i - state["pierce"] > RECLAIM_N:
                    skips["no_reclaim"] += 1
                    state = None
                    continue

            if state["rec"] is None and CV[i] < state["lvl"]:
                state["rec"] = i
            if state["rec"] is None:
                continue
            # 触发检查：首个收盘破近端回调结构（sweep 极值前最近一个已确认对侧 swing）
            pb = None
            for s in opp_sw:
                if s.confirmed_at <= i and s.index < state["ext_i"] and v * s.price < state["lvl"]:
                    if pb is None or s.index > pb.index:
                        pb = s
            if pb is not None and CV[i] < v * pb.price and CV[i] < state["lvl"]:
                sig = _emit(symbol, bars, swings, v, side, opp, i, state, fwb, skips, n)
                if sig:
                    signals.append(sig)
                state = None
            elif i - state["rec"] > TRIGGER_N:
                skips["no_trigger"] += 1
                state = None
    return signals, skips


def _emit(symbol, bars, swings, v, side, opp, t, state, fwb, skips, n):
    if t > n - 1 - MIN_SIM_BARS:
        skips["too_late"] += 1
        return None
    v_entry = v * bars[t].close
    atr = average_true_range(bars[:t + 1], ATR_PERIOD)
    v_sl0 = state["ext"] + BASE_BUFFER * atr
    # DOL：触发时刻仍未被取走、位于入场下方(v空间)的最近对侧 swing
    cands = [v * s.price for s in swings
             if s.kind == opp and s.confirmed_at <= t and v * s.price < v_entry
             and (fwb[id(s)] is None or fwb[id(s)] > t)]
    if not cands:
        skips["no_target"] += 1
        return None
    v_target = max(cands)
    risk = v_sl0 - v_entry
    if risk <= 0 or (v_entry - v_target) / risk < RR_MIN:
        skips["rr_too_small"] += 1
        return None
    return Sig(symbol=symbol, dir=("SHORT" if v > 0 else "LONG"), v=v, t=t, ts=bars[t].ts,
               entry=bars[t].close, extreme=v * state["ext"], level=v * state["lvl"], atr=atr,
               target=v * v_target, v_entry=v_entry, v_extreme=state["ext"],
               v_level=state["lvl"], v_target=v_target)


# ---------------- 模拟器（全部 v-空间，同 bar 双触保守先止损） ----------------
def _arrays(bars, v):
    AV = [max(v * b.high, v * b.low) for b in bars]
    FV = [min(v * b.high, v * b.low) for b in bars]
    MIDV = [v * (b.high + b.low) / 2.0 for b in bars]
    return AV, FV, MIDV


def sim_baseline(AV, FV, MIDV, sig, buffer):
    """到 DOL 全平 / 先打 SL 记 -1R / HORIZON 根未决按中价 expired。
    返回 (outcome, R, bars_to_exit)。"""
    n = len(AV)
    v_sl = sig.v_extreme + buffer * sig.atr
    risk = v_sl - sig.v_entry
    for j in range(sig.t + 1, min(sig.t + 1 + HORIZON, n)):
        if AV[j] >= v_sl:
            return "sl", -1.0, j - sig.t
        if FV[j] <= sig.v_target:
            return "tp", (sig.v_entry - sig.v_target) / risk, j - sig.t
    j_last = min(sig.t + HORIZON, n - 1)
    return "expired", (sig.v_entry - MIDV[j_last]) / risk, j_last - sig.t


def sim_mgmt1r(AV, FV, MIDV, sig, buffer):
    """+1R 减半 + 移 BE（BE 自触及 1R 的下一根 bar 生效，近似声明见报告）。"""
    n = len(AV)
    v_sl = sig.v_extreme + buffer * sig.atr
    risk = v_sl - sig.v_entry
    p1 = sig.v_entry - risk
    r_tp = (sig.v_entry - sig.v_target) / risk
    half, be_on = False, False
    for j in range(sig.t + 1, min(sig.t + 1 + HORIZON, n)):
        stop = sig.v_entry if be_on else v_sl
        if AV[j] >= stop:
            back = 0.0 if be_on else -1.0
            return "stop", (0.5 * 1.0 + 0.5 * back) if half else back, j - sig.t
        if FV[j] <= sig.v_target and r_tp <= 1.0:
            return "tp", r_tp, j - sig.t          # 目标比 1R 近，先到目标全平 = 基线
        if not half and FV[j] <= p1:
            half = True                            # 触深必先触浅：同 bar 到目标也先记 1R 减半
        if half and FV[j] <= sig.v_target:
            return "tp", 0.5 * 1.0 + 0.5 * r_tp, j - sig.t
        if half:
            be_on = True                           # 下一根 bar 起 BE 生效
    j_last = min(sig.t + HORIZON, n - 1)
    tail = (sig.v_entry - MIDV[j_last]) / risk
    return "expired", (0.5 * 1.0 + 0.5 * tail) if half else tail, j_last - sig.t


def sim_mgmt2r(AV, FV, MIDV, sig, buffer):
    """+2R 减半，+1R 触及后移 BE（近似：BE 下一根 bar 生效）。"""
    n = len(AV)
    v_sl = sig.v_extreme + buffer * sig.atr
    risk = v_sl - sig.v_entry
    p1, p2 = sig.v_entry - risk, sig.v_entry - 2 * risk
    r_tp = (sig.v_entry - sig.v_target) / risk
    half, be_on, be_pend = False, False, False
    for j in range(sig.t + 1, min(sig.t + 1 + HORIZON, n)):
        if be_pend:
            be_on, be_pend = True, False
        stop = sig.v_entry if be_on else v_sl
        if AV[j] >= stop:
            back = 0.0 if be_on else -1.0
            return "stop", (0.5 * 2.0 + 0.5 * back) if half else back, j - sig.t
        depth = FV[j]
        if depth <= sig.v_target and r_tp <= 2.0:
            # 目标不深于 2R：到目标即全平（若已过 1R 只影响 BE，不影响此路径）
            return "tp", r_tp, j - sig.t
        if not be_on and not be_pend and depth <= p1:
            be_pend = True
        if not half and depth <= p2:
            half = True
        if half and depth <= sig.v_target:
            return "tp", 0.5 * 2.0 + 0.5 * r_tp, j - sig.t
    j_last = min(sig.t + HORIZON, n - 1)
    tail = (sig.v_entry - MIDV[j_last]) / risk
    return "expired", (0.5 * 2.0 + 0.5 * tail) if half else tail, j_last - sig.t


def sim_limit(AV, FV, MIDV, sig, v_limit):
    """触发后挂回踩限价。保守规则（报告声明）：
    - 触及 SL 的 bar 必然先穿过限价（限价<SL），按已成交立即止损记 -1；
    - 成交 bar 当根不计目标（不知先后），目标从下一根起算；
    - 未成交且到 DOL = missed 计 0R。"""
    n = len(AV)
    v_sl = sig.v_extreme + BASE_BUFFER * sig.atr
    if v_limit >= v_sl:
        return "invalid", None, 0
    risk = v_sl - v_limit
    filled = False
    for j in range(sig.t + 1, min(sig.t + 1 + HORIZON, n)):
        if not filled:
            if AV[j] >= v_sl:
                return "fill_sl", -1.0, j - sig.t
            if AV[j] >= v_limit:
                filled = True
                continue  # 成交当根不计目标（保守）
            if FV[j] <= sig.v_target:
                return "missed", 0.0, j - sig.t
        else:
            if AV[j] >= v_sl:
                return "fill_sl", -1.0, j - sig.t
            if FV[j] <= sig.v_target:
                return "fill_tp", (v_limit - sig.v_target) / risk, j - sig.t
    j_last = min(sig.t + HORIZON, n - 1)
    if filled:
        return "fill_expired", (v_limit - MIDV[j_last]) / risk, j_last - sig.t
    return "nofill_expired", None, j_last - sig.t


# ---------------- H1/H2 分类（只用触发时刻之前已收盘的 D1 bar） ----------------
def d1_closed_before(d1: list[Bar], h4_ts: int) -> list[Bar]:
    # D1 bar 须在 H4 触发 bar 开盘前完整收盘：d1.ts + 86400 <= h4_ts（略保守）
    ts_list = [b.ts for b in d1]
    idx = bisect.bisect_right(ts_list, h4_ts - 86400)
    return d1[:idx]


def h1_bucket(sig: Sig, d1: list[Bar]) -> str:
    closed = d1_closed_before(d1, sig.ts)
    if len(closed) < 30:
        return "unknown"
    win = closed[-D1_RANGE_N:]
    hi, lo = max(b.high for b in win), min(b.low for b in win)
    mid = (hi + lo) / 2.0
    aligned = (sig.dir == "SHORT" and sig.entry > mid) or (sig.dir == "LONG" and sig.entry < mid)
    return "aligned" if aligned else "against"


def h2_bucket(sig: Sig, d1: list[Bar]) -> str:
    """机械定义（报告原文引用）：
    入场区 = [entry, sweep极值] 两端各扩 0.1×ATR(D1)。
    D1 array A) swing 极值回踩区：近 100 根已收盘 D1 上 find_swings(k=2) 的同向极值
    （SHORT 用 swing high，LONG 用 swing low），且触发前未被 D1 收盘突破，
    区间 = 极值 ± 0.25×ATR(D1)。
    B) D1 三根K FVG：SHORT 用看跌 FVG（bar[i-2].low > bar[i].high，区间
    [bar[i].high, bar[i-2].low]，触发前无 D1 收盘上破区间上沿即有效）；LONG 镜像。
    入场区与任一 array 区间相交 = confluence。"""
    closed = d1_closed_before(d1, sig.ts)
    if len(closed) < 30:
        return "unknown"
    win = closed[-D1_ARRAY_LOOKBACK:]
    atr_d1 = average_true_range(win, ATR_PERIOD)
    z_lo = min(sig.entry, sig.extreme) - 0.1 * atr_d1
    z_hi = max(sig.entry, sig.extreme) + 0.1 * atr_d1
    kind = "high" if sig.dir == "SHORT" else "low"
    for s in find_swings(win, SWING_K):
        if s.kind != kind:
            continue
        broken = any((b.close > s.price if kind == "high" else b.close < s.price)
                     for b in win[s.confirmed_at + 1:])
        if broken:
            continue
        if z_lo <= s.price + D1_SWING_PAD * atr_d1 and s.price - D1_SWING_PAD * atr_d1 <= z_hi:
            return "confluence"
    for i in range(2, len(win)):
        a, c = win[i - 2], win[i]
        if sig.dir == "SHORT" and a.low > c.high:
            f_lo, f_hi = c.high, a.low
            if any(b.close > f_hi for b in win[i + 1:]):
                continue
        elif sig.dir == "LONG" and a.high < c.low:
            f_lo, f_hi = a.high, c.low
            if any(b.close < f_lo for b in win[i + 1:]):
                continue
        else:
            continue
        if z_lo <= f_hi and f_lo <= z_hi:
            return "confluence"
    return "no_confluence"


# ---------------- 统计与报告 ----------------
def stats(rows):
    """rows: list of (R, sym, day)。返回 (n, avgR, winrate, n_dedup)。"""
    n = len(rows)
    if n == 0:
        return 0, 0.0, 0.0, 0
    avg = sum(r for r, _, _ in rows) / n
    wr = sum(1 for r, _, _ in rows if r > 0) / n
    dedup = len({(s, d) for _, s, d in rows})
    return n, avg, wr, dedup


def fmt_cell(rows):
    n, avg, wr, dd = stats(rows)
    flag = "" if n >= MIN_N else "  [n<20 不可用]"
    return f"n={n:<4d} 去重n={dd:<4d} avgR={avg:+.3f}  胜率={wr:.1%}{flag}"


def day_of(ts: int) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def main():
    t0 = time.time()
    print("拉取真实 K 线（H4×%d + D1×%d，%d 品种）..." % (H4_LIMIT, D1_LIMIT, len(UNIVERSE)),
          file=sys.stderr)
    data, failed = fetch_all()

    all_sigs: list[Sig] = []
    skip_total = defaultdict(int)
    span = {}
    for sym, (h4, d1) in data.items():
        sigs, skips = scan_symbol(sym, h4)
        all_sigs.extend(sigs)
        for k, v in skips.items():
            skip_total[k] += v
        span[sym] = (day_of(h4[0].ts), day_of(h4[-1].ts), len(h4))

    # 预计算每 symbol 每方向的 v 空间数组
    arr_cache = {}
    for sym, (h4, _) in data.items():
        arr_cache[(sym, 1.0)] = _arrays(h4, 1.0)
        arr_cache[(sym, -1.0)] = _arrays(h4, -1.0)

    # 每信号全套结果
    R = {}          # (key) -> list[(R, sym, day)]
    for k in ["base", "mgmt1r", "mgmt2r"] + [f"buf{b}" for b in BUFFERS]:
        R[k] = []
    quick_loss = defaultdict(int)   # buffer -> 3 根内即损数
    buf_n = defaultdict(int)
    h1 = defaultdict(list)
    h2 = defaultdict(list)
    ce_out = defaultdict(list)      # variant -> list[(outcome, R, sym, day)]
    sym_rows = defaultdict(list)
    outcome_cnt = defaultdict(int)

    for sig in all_sigs:
        AV, FV, MIDV = arr_cache[(sig.symbol, sig.v)]
        d1 = data[sig.symbol][1]
        day = day_of(sig.ts)
        row = lambda r: (r, sig.symbol, day)  # noqa: E731

        oc, r_base, _ = sim_baseline(AV, FV, MIDV, sig, BASE_BUFFER)
        outcome_cnt[oc] += 1
        R["base"].append(row(r_base))
        sym_rows[sig.symbol].append(row(r_base))
        h1[h1_bucket(sig, d1)].append(row(r_base))
        h2[h2_bucket(sig, d1)].append(row(r_base))

        _, r1, _ = sim_mgmt1r(AV, FV, MIDV, sig, BASE_BUFFER)
        R["mgmt1r"].append(row(r1))
        _, r2, _ = sim_mgmt2r(AV, FV, MIDV, sig, BASE_BUFFER)
        R["mgmt2r"].append(row(r2))

        for b in BUFFERS:
            oc_b, r_b, nb = sim_baseline(AV, FV, MIDV, sig, b)
            R[f"buf{b}"].append(row(r_b))
            buf_n[b] += 1
            if oc_b == "sl" and nb <= 3:
                quick_loss[b] += 1

        v_ce = (sig.v_extreme + sig.v_entry) / 2.0
        for name, v_lim in (("ce50", v_ce), ("edge", sig.v_level)):
            oc_l, r_l, _ = sim_limit(AV, FV, MIDV, sig, v_lim)
            ce_out[name].append((oc_l, r_l, sig.symbol, day))

    n_all, avg_all, wr_all, dd_all = stats(R["base"])

    # ---------- 报告 ----------
    P = print
    P("=" * 78)
    P("skill 结构层规则 H4/D1 历史回测报告  (%s 生成, 用时 %.0fs)" % (
        time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), time.time() - t0))
    P("=" * 78)
    P("\n【数据与信号生成参数】")
    P(f"品种: {len(data)}/{len(UNIVERSE)} 拉取成功; 失败/跳过: "
      + (", ".join(f"{s}({e})" for s, e in failed) if failed else "无"))
    if span:
        d_min = min(v[0] for v in span.values())
        d_max = max(v[1] for v in span.values())
        P(f"H4 窗口: 每品种最多 {H4_LIMIT} 根 (~5.5 个月), 全体覆盖 {d_min} ~ {d_max}")
    P(f"引擎: sweep(wick 刺穿前置已确认 swing, 前 {FRESH_W} 根未刺穿过, 未被收盘突破)"
      f" -> {RECLAIM_N} 根内收回 -> {TRIGGER_N} 根内首个收盘破近端回调结构 = 触发")
    P(f"入场=触发 bar 收盘; SL=扫荡极值外+buffer×ATR{ATR_PERIOD}(基线 buffer={BASE_BUFFER});"
      f" 目标=触发时最近未取对侧 swing(DOL); 同 bar 双触先止损; {HORIZON} 根未决按中价 expired")
    P(f"过滤剔除: 无目标 {skip_total['no_target']}, RR<{RR_MIN} {skip_total['rr_too_small']},"
      f" 尾部数据不足 {skip_total['too_late']};"
      f" 未成形 setup: 未收回 {skip_total['no_reclaim']}, 未触发 {skip_total['no_trigger']}")
    P(f"\n信号总数 n={n_all} (LONG {sum(1 for s in all_sigs if s.dir=='LONG')}"
      f" / SHORT {sum(1 for s in all_sigs if s.dir=='SHORT')});"
      f" symbol-day 去重独立样本粗估 n≈{dd_all}")
    P(f"基线结果: avgR={avg_all:+.3f} 胜率={wr_all:.1%};"
      f" 结局分布: TP {outcome_cnt['tp']} / SL {outcome_cnt['sl']} / expired {outcome_cnt['expired']}")

    P("\n【统计纪律声明】6 假设×多切片=多重比较。判读门槛: |avgR差|>=%.2fR 且两侧 n>=30"
      " 才称'值得注意', 其余一律称噪音; 本报告不做任何'显著'声明。n<%d 的格标'不可用'。"
      " 同品种同日多信号高度相关, 各格附 symbol-day 去重 n 作独立样本粗估。"
      % (NOTABLE_DIFF, MIN_N))

    verdicts = []

    def compare(tag, rows_a, name_a, rows_b, name_b):
        na, aa, _, _ = stats(rows_a)
        nb, ab, _, _ = stats(rows_b)
        if na >= 30 and nb >= 30 and abs(aa - ab) >= NOTABLE_DIFF:
            better = name_a if aa > ab else name_b
            return f"值得注意: {better} 每单多 {abs(aa-ab):.2f}R", True, aa - ab
        return "噪音水平(未达门槛)", False, aa - ab

    # ---- H1 ----
    P("\n" + "-" * 78)
    P("H1  D1 偏向门 (近 %d 根 D1 区间: 折价做多/溢价做空=顺门)" % D1_RANGE_N)
    P(f"  顺门:   {fmt_cell(h1['aligned'])}")
    P(f"  逆门:   {fmt_cell(h1['against'])}")
    if h1["unknown"]:
        P(f"  D1不足: {fmt_cell(h1['unknown'])}")
    note, notable, diff = compare("H1", h1["aligned"], "顺门", h1["against"], "逆门")
    P(f"  判读: {note} (顺门-逆门 avgR 差 {diff:+.3f})")
    if notable and diff > 0:
        verdicts.append(("H1 D1偏向门", "数据支持保留", f"顺门比逆门每单多 {diff:.2f}R"))
    elif notable and diff < 0:
        verdicts.append(("H1 D1偏向门", "数据反对(建议降级)", f"逆门反而多 {-diff:.2f}R"))
    else:
        verdicts.append(("H1 D1偏向门", "分不清(等实盘)", f"差 {diff:+.2f}R 未达门槛"))

    # ---- H2 ----
    P("\n" + "-" * 78)
    P("H2  D1 重合升级 (机械定义见下)")
    P("  定义: 入场区=[entry,扫荡极值]±0.1×ATR(D1)。array A=近%d根已收盘D1的同向"
      % D1_ARRAY_LOOKBACK)
    P("  swing 极值(k=2, 未被D1收盘突破)±%.2f×ATR(D1) 回踩区; array B=D1三根K FVG" % D1_SWING_PAD)
    P("  (SHORT: bar[i-2].low>bar[i].high 的看跌FVG且未被D1收盘上破; LONG 镜像)。相交=重合。")
    P(f"  重合:   {fmt_cell(h2['confluence'])}")
    P(f"  不重合: {fmt_cell(h2['no_confluence'])}")
    if h2["unknown"]:
        P(f"  D1不足: {fmt_cell(h2['unknown'])}")
    note, notable, diff = compare("H2", h2["confluence"], "重合", h2["no_confluence"], "不重合")
    P(f"  判读: {note} (重合-不重合 avgR 差 {diff:+.3f})")
    if notable and diff > 0:
        verdicts.append(("H2 D1重合升级", "数据支持保留", f"重合每单多 {diff:.2f}R"))
    elif notable and diff < 0:
        verdicts.append(("H2 D1重合升级", "数据反对(建议删或降级)", f"重合反而少 {-diff:.2f}R"))
    else:
        verdicts.append(("H2 D1重合升级", "分不清(等实盘)", f"差 {diff:+.2f}R 未达门槛"))

    # ---- H3 ----
    P("\n" + "-" * 78)
    P("H3  CE(50%) 回踩限价 vs 结构区边缘限价 (同批信号, R 按各自止损距归一)")
    P("  保守规则声明: 触及SL的bar必先过限价->按已成交止损记-1; 成交当根不计目标;")
    P("  未成交且价格到DOL=错过(计0R, 单独报错过率); 未成交且到期=作废。")
    base_n = len(R["base"])
    for name, label in (("ce50", "CE 50%回踩"), ("edge", "结构区边缘")):
        rows = ce_out[name]
        filled = [(r, s, d) for oc, r, s, d in rows if oc in ("fill_sl", "fill_tp", "fill_expired")]
        missed = [x for x in rows if x[0] == "missed"]
        nofill_exp = [x for x in rows if x[0] == "nofill_expired"]
        nf, af, wf, ddf = stats(filled)
        fill_rate = nf / base_n if base_n else 0
        miss_rate = len(missed) / base_n if base_n else 0
        # 机会成本口径: 未成交(错过+作废)计 0R, 与成交单合并
        all_r = [r for r, _, _ in filled] + [0.0] * (len(missed) + len(nofill_exp))
        avg_all_r = sum(all_r) / len(all_r) if all_r else 0.0
        flag = "" if nf >= MIN_N else "  [成交n<20 不可用]"
        P(f"  {label}: 成交率={fill_rate:.1%} (成交n={nf}, 去重n={ddf})")
        P(f"    成交单: avgR={af:+.3f} 胜率={wf:.1%}{flag}")
        P(f"    错过率(未成交且到DOL)={miss_rate:.1%} ({len(missed)}单);"
          f" 未成交作废={len(nofill_exp)}单")
        P(f"    含未成交机会成本口径 avgR={avg_all_r:+.3f} (未成交计0R, 分母={len(all_r)})")
    P(f"  对照 市价入场基线: {fmt_cell(R['base'])}")
    ce_filled = [(r, s, d) for oc, r, s, d in ce_out["ce50"]
                 if oc in ("fill_sl", "fill_tp", "fill_expired")]
    note, notable, diff = compare("H3", ce_filled, "CE成交单", R["base"], "市价基线")
    P(f"  判读(CE成交单 vs 市价基线): {note} (差 {diff:+.3f}; 注意 CE 成交子集有选择偏差)")
    ce_all_avg = (sum(r for r, _, _ in ce_filled)
                  + 0.0 * 1) / base_n if base_n else 0.0  # 未成交计0R 的总体口径
    if notable and diff > 0 and ce_all_avg > stats(R["base"])[1] + NOTABLE_DIFF:
        verdicts.append(("H3 CE限价入场", "数据支持保留", "成交单与机会成本口径都更优"))
    elif notable and diff > 0:
        verdicts.append(("H3 CE限价入场", "分不清(等实盘)",
                         "成交单每单更优但错过成本吃掉优势(机会成本口径未同幅胜出)"))
    elif notable and diff < 0:
        verdicts.append(("H3 CE限价入场", "数据反对(建议降级)", "成交单反而更差=逆向选择"))
    else:
        verdicts.append(("H3 CE限价入场", "分不清(等实盘)", "未达门槛"))

    # ---- H4 ----
    P("\n" + "-" * 78)
    P("H4  止损 buffer 扫描 (同批信号, R 按各自止损距归一; 即损=入场后 3 根内打损)")
    best_b, best_avg = None, -1e9
    for b in BUFFERS:
        rows = R[f"buf{b}"]
        n, avg, wr, dd = stats(rows)
        ql = quick_loss[b] / n if n else 0
        flag = "" if n >= MIN_N else " [不可用]"
        P(f"  buffer={b:.2f}×ATR: n={n} 去重n={dd} avgR={avg:+.3f} 胜率={wr:.1%}"
          f" 3根内即损率={ql:.1%}{flag}")
        if avg > best_avg:
            best_avg, best_b = avg, b
    n05 = stats(R[f"buf{BASE_BUFFER}"])
    spread = best_avg - min(stats(R[f"buf{b}"])[1] for b in BUFFERS)
    P(f"  判读: 档间 avgR 极差 {spread:.3f}R; "
      + ("值得注意, 最优档 %.2f" % best_b if spread >= NOTABLE_DIFF and n05[0] >= 30 else "噪音水平"))
    if spread >= NOTABLE_DIFF and n05[0] >= 30:
        verdicts.append(("H4 止损buffer", "数据支持保留(取%.2f×ATR档)" % best_b,
                         f"档间极差 {spread:.2f}R"))
    else:
        verdicts.append(("H4 止损buffer", "分不清(等实盘)",
                         f"档间极差 {spread:.2f}R 未达门槛, buffer 不敏感"))

    # ---- H5 ----
    P("\n" + "-" * 78)
    P("H5  管理方案对比 (同批信号, 基线 buffer)")
    P("  BE 近似声明: 触及+1R 的下一根 bar 起 BE 生效(略偏乐观: 漏掉同bar回入场价的BE止平);")
    P("  同 bar 触 SL 与减仓位一律先算 SL(偏保守)。两向偏差方向已声明, 净偏差未知但有界。")
    for key, label in (("base", "基线 hold-to-DOL"), ("mgmt1r", "+1R减半+BE"),
                       ("mgmt2r", "mgmt2r(+2R减半,+1R起BE)")):
        P(f"  {label}: {fmt_cell(R[key])}")
    note1, notable1, d1_ = compare("H5a", R["mgmt1r"], "+1R减半", R["base"], "基线")
    note2, notable2, d2_ = compare("H5b", R["mgmt2r"], "mgmt2r", R["base"], "基线")
    P(f"  判读: +1R减半-基线 {d1_:+.3f} ({'值得注意' if notable1 else '噪音'});"
      f" mgmt2r-基线 {d2_:+.3f} ({'值得注意' if notable2 else '噪音'})")
    if notable1 or notable2:
        deltas = [(d1_, "+1R减半+BE"), (d2_, "mgmt2r")]
        best = max(deltas)
        if best[0] > 0:
            verdicts.append(("H5 管理方案", "数据支持保留(%s)" % best[1],
                             f"比基线每单多 {best[0]:.2f}R"))
        else:
            verdicts.append(("H5 管理方案", "数据反对(建议删/降级主动管理)",
                             "主动管理比 hold-to-DOL 每单少 %.2fR" % max(-d1_, -d2_)))
    else:
        verdicts.append(("H5 管理方案", "分不清(等实盘)", "三方案差均未达门槛"))

    # ---- H6 ----
    P("\n" + "-" * 78)
    P("H6  品种分层复核 (基线口径; 现行 A层=%s, C层=%s)" % (
        "/".join(sorted(TIER_A)), "/".join(sorted(TIER_C))))
    flips = []
    for sym in sorted(sym_rows, key=lambda s: -stats(sym_rows[s])[1]):
        n, avg, wr, dd = stats(sym_rows[sym])
        tier = "A层" if sym in TIER_A else ("C层" if sym in TIER_C else "  ")
        flag = "" if n >= MIN_N else " [n<20 不可用]"
        flip = ""
        if n >= 10:
            if sym in TIER_A and avg < 0:
                flip = "  <<< A层翻车(本窗口为负)"
                flips.append(sym)
            elif sym in TIER_C and avg >= NOTABLE_DIFF:
                flip = "  <<< C层翻车(本窗口明显为正)"
                flips.append(sym)
        P(f"  {sym:<8s} {tier} n={n:<3d} 去重n={dd:<3d} avgR={avg:+.3f} 胜率={wr:.1%}{flag}{flip}")
    no_sig = [s for s in data if s not in sym_rows]
    if no_sig:
        P("  无信号品种: " + ", ".join(no_sig))
    P(f"  判读: 各品种 n 普遍小(多数 n<{MIN_N}), 5.5 个月窗口的品种分层几乎必然是噪音;")
    P("  翻车名单(仅提示, 非结论): " + (", ".join(flips) if flips else "无"))
    verdicts.append(("H6 品种分层", "分不清(等实盘)",
                     "单品种 n 太小; 翻车提示: " + (", ".join(flips) if flips else "无")))

    # ---- 结论 ----
    P("\n" + "=" * 78)
    P("【三档结论清单】(自动按门槛规则生成, 不含任何'显著'声明)")
    for name, tier, why in verdicts:
        P(f"  [{tier}] {name} — {why}")

    P("\n【局限声明】")
    P("  1) 窗口仅 ~5.5 个月(H4 1000根)、单一 regime, 任何结论都不够跨周期;"
      " D1 假设(H1/H2)受窗口内 D1 趋势方向支配。")
    P("  2) 信号引擎是 skill 三步走的 H4 机械化近似, 参数(RECLAIM_N/TRIGGER_N/FRESH_W)"
      " 一组固定值, 未做敏感性扫描; 结论对引擎定义有依赖。")
    P("  3) 同品种同日信号相关, 有效样本看去重 n; 跨品种同日(如全体 risk-off)仍相关,"
      " 去重 n 仍是高估。")
    P("  4) 无手续费/滑点/资金费; H4 收盘市价成交假设对 tradfi 周末跳空偏乐观。")
    P("  5) expired 按中价折算引入记账噪音; BE/限价成交的同 bar 次序按保守规则近似。")
    P("  6) 多重比较未做正式校正(BH-FDR), 仅用 0.15R/n>=30 粗门槛, '值得注意'≠显著。")
    P("  7) 数据为交易所在线 K 线, 重跑时窗口右端随行情推移, 数字会小幅漂移。")


if __name__ == "__main__":
    main()
