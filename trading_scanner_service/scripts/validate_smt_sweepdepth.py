"""G12 SMT背离 / G13 扫荡深度 — 事后验证（幂等只读）.

复用 data/backtest_trigger_deep_trades.jsonl 的 15955 笔触发明细（含结算R），
不重跑结算。明细未存 swept_level，但 parent 生成与触发检测完全确定性，
故通过 backtest_trigger_deep.gen_parents + 同一候选循环重建
(symbol, model, direction, trig_ts) -> parent 映射，取回 swept_level / parent_bar_ts。

无前视口径：
  G12 SMT: 本品种与相关品种 M15 各截到 parent bar 收盘（含）为止 —— parent 收盘
           先于触发 ts，严格无前视；锚在 parent 收盘是因为 SMT 检的是父级扫荡
           那一刻的背离（触发可迟至 24h 后，届时 sweep 已滑出 recent 窗）。
           两边按共同 ts 对齐窗口。仅 CORRELATED_PAIRS 品种参与。
  G13 深度: sweep_depth_atr(m15 截到 parent bar 收盘含, swept_level, direction)。
           extreme 距 parent bar 最多 RECLAIM_N=3 根，落在 lookback=6 窗内。

纪律: n<20 不可用; |ΔavgR|<0.15R 记噪音; 结论 支持/反对/分不清。
avgR 用 hold 管理结算 R；胜率 = outcome=="win" 占比。

Run: python3 scripts/validate_smt_sweepdepth.py
"""
from __future__ import annotations

import json
import sys
from bisect import bisect_left, bisect_right
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import backtest_trigger_deep as bt  # noqa: E402
from scanner_service.structure import (  # noqa: E402
    CORRELATED_PAIRS, smt_divergence, sweep_depth_atr)

TRADES = ROOT / "data" / "backtest_trigger_deep_trades.jsonl"
MIN_N, NOISE_R = 20, 0.15
SMT_MIN_ALIGNED = 40  # 对齐窗口长度（>= lookback16+4，留裕量）


def rebuild_parent_map(sym: str):
    """复刻 run_symbol 的候选循环（含同序 dedup 与过滤），只建 key->parent，不结算。"""
    m15, m5 = bt.load(sym, "M15"), bt.load(sym, "M5")
    if len(m15) < 200 or len(m5) < 500:
        return {}, m15
    parents = bt.gen_parents(sym, m15)
    m5_ts = [b.ts for b in m5]
    atr5 = bt.rolling_atr(m5)
    seen, out = set(), {}
    for p in parents:
        lo = bisect_right(m5_ts, p["ts"])
        hi = bisect_right(m5_ts, p["ts"] + bt.FILL_WINDOW_S)
        window = m5[lo:hi]
        if len(window) < 10:
            continue
        cands = []
        c = bt.detect_ltf_trigger(p, window)
        if c is not None:
            cands.append(("三步走", c))
        cont = bt.detect_continuation_triggers(p, window)
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
            if risk < bt.MIN_RISK_ATR5 * atr5[gi]:
                continue
            reward = (dol - entry) if c["direction"] == "LONG" else (entry - dol)
            if reward <= 0 or risk <= 0:
                continue
            seen.add(key)
            out[key] = p
    return out, m15


def cell(rows):
    n = len(rows)
    if n == 0:
        return 0, 0.0, 0.0
    return n, sum(r["hold"] for r in rows) / n, \
        sum(1 for r in rows if r["outcome"] == "win") / n


def fmt(rows):
    n, avg, wr = cell(rows)
    tag = "" if n >= MIN_N else " [n<20不可用]"
    return f"n={n:<5d} avgR={avg:+.3f} 胜率={wr:.1%}{tag}"


def verdict(rows_a, rows_b, hyp: str) -> str:
    """hyp 语义: rows_a 应优于 rows_b。"""
    na, aa, _ = cell(rows_a)
    nb, ab, _ = cell(rows_b)
    if na < MIN_N or nb < MIN_N:
        return f"分不清（样本不足 n={na}/{nb}）"
    d = aa - ab
    if abs(d) < NOISE_R:
        return f"分不清（Δ={d:+.3f}R < 0.15R 噪音带）"
    return (f"支持（Δ={d:+.3f}R）" if d > 0 else f"反对（Δ={d:+.3f}R，方向相反）")


def main():
    by_sym = defaultdict(list)
    with TRADES.open() as fh:
        for line in fh:
            t = json.loads(line)
            by_sym[t["symbol"]].append(t)
    total = sum(len(v) for v in by_sym.values())

    m15_cache: dict[str, list] = {}
    matched = miss = 0
    g12_rows_yes, g12_rows_no, g12_skip = [], [], 0
    g13 = {"浅": [], "中": [], "深": []}
    pair_stats = defaultdict(lambda: {"yes": [], "no": []})

    for sym in sorted(by_sym):
        pmap, m15 = rebuild_parent_map(sym)
        m15_cache[sym] = m15
        partner = CORRELATED_PAIRS.get(sym)
        pb = None
        if partner:
            if partner not in m15_cache:
                m15_cache[partner] = bt.load(partner, "M15")
            pb = {b.ts: b for b in m15_cache[partner]}
        ts_list = [b.ts for b in m15]
        for t in by_sym[sym]:
            p = pmap.get((sym, t["model"], t["direction"], t["ts"]))
            if p is None:
                miss += 1
                continue
            matched += 1
            # 截到 parent bar 收盘（含），严格先于触发 ts
            cut = bisect_right(ts_list, p["parent_bar_ts"])
            bars = m15[:cut]
            if len(bars) >= 20:
                depth = sweep_depth_atr(bars, p["swept_level"], t["direction"])
                bucket = "浅" if depth <= 0.3 else ("中" if depth <= 0.8 else "深")
                g13[bucket].append(t)
            if pb is not None:
                aligned = [b for b in bars[-(SMT_MIN_ALIGNED * 3):] if b.ts in pb]
                aligned = aligned[-SMT_MIN_ALIGNED:]
                if len(aligned) < 20:
                    g12_skip += 1
                else:
                    bars_b = [pb[b.ts] for b in aligned]
                    ok, _ = smt_divergence(aligned, bars_b, t["direction"])
                    (g12_rows_yes if ok else g12_rows_no).append(t)
                    pk = "/".join(sorted((sym, partner)))
                    pair_stats[pk]["yes" if ok else "no"].append(t)

    print(f"总触发 {total}，parent 映射成功 {matched}，失配 {miss}")
    n12 = len(g12_rows_yes) + len(g12_rows_no)
    print(f"\n== G12 SMT背离（相关对子集 n={n12}，对齐不足跳过 {g12_skip}）==")
    print(f"  有背离: {fmt(g12_rows_yes)}")
    print(f"  无背离: {fmt(g12_rows_no)}")
    print(f"  结论（假设:有背离更好）: {verdict(g12_rows_yes, g12_rows_no, 'smt')}")
    for pk in sorted(pair_stats):
        s = pair_stats[pk]
        print(f"    {pk}: 有 {fmt(s['yes'])} | 无 {fmt(s['no'])}")

    print(f"\n== G13 扫荡深度（ATR分桶，全体可映射触发）==")
    for k in ("浅", "中", "深"):
        lim = {"浅": "≤0.3", "中": "0.3-0.8", "深": ">0.8"}[k]
        print(f"  {k}({lim}): {fmt(g13[k])}")
    print(f"  结论（ICT假设:浅扫更好，浅 vs 深）: {verdict(g13['浅'], g13['深'], 'depth')}")


if __name__ == "__main__":
    main()
