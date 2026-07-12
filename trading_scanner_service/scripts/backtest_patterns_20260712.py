#!/usr/bin/env python3
"""H7-H9 形态分桶回测（2026-07-12，中等规模）。

在 backtest_skill_rules_20260711.py 的同一 H4 扫荡-反转信号引擎上，对每个信号
在触发时刻（只用 <=t 已收盘 bar）机械判定三个 Brooks 形态是否在场，分桶比较：

  H7 楔形三推：进入被扫位的那条腿由 >=3 个逐级抬高的局部极值构成（v 空间），
      最后一推 = 扫荡极值，且第三推的延伸 < 第二推的延伸（动能收缩）。
  H8 微双顶底：扫荡极值打印后、触发前，出现第二次测试——极值后 >=2 根的某根
      bar 极值进入 [ext - 0.30*ATR, ext]（不创决定性新极值）。
  H9 最终旗形：刺穿 bar 之前 10 根内结束一段 >=8 根、总幅 <=1.5*ATR 的横盘，
      且旗形前 30 根内朝扫荡方向已走出 >=3*ATR（末段趋势 + 停顿 + 终推）。

所有参数一次锁死（见下方常量），单次运行，禁止改参重跑后择优。
统计：ΔavgR 门槛 0.15R、两侧 n>=30、Welch 检验 + BH-FDR(q=0.10) 三假设联合校正。
只读：只拉交易所 API，不写数据文件。

用法: python3 scripts/backtest_patterns_20260712.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backtest_skill_rules_20260711 as base

# ---------------- 形态参数（锁死，不扫描） ----------------
LEG_LOOKBACK = 30      # H7: 从扫荡极值 bar 向前找三推的窗口
PUSH_K = 2             # H7: 局部极值窗口（左右各 K 根）
DT_TOL_ATR = 0.30      # H8: 第二次测试与极值的最大距离（×ATR）
DT_MIN_GAP = 2         # H8: 第二次测试距极值 bar 的最小间隔
FLAG_MIN_LEN = 8       # H9: 旗形最短长度
FLAG_RANGE_ATR = 1.5   # H9: 旗形总幅上限（×ATR）
FLAG_MAX_AGE = 10      # H9: 旗形结束距刺穿 bar 的最大间隔
PRETREND_ATR = 3.0     # H9: 旗形前趋势最小幅度（×ATR）
PRETREND_N = 30        # H9: 旗形前趋势回看窗口
NOTABLE_DIFF = 0.15    # 与 0711 一致
MIN_N = 30
FDR_Q = 0.10


# ---------------- 形态检测（全部 v 空间；只用 <=t 的 bar） ----------------
def _local_maxima(AV, lo, hi, k):
    """[lo,hi] 内左右各 k 根的局部极大 bar 下标（边界不足 k 根的不算）。"""
    out = []
    for i in range(max(lo, k), hi + 1):
        w0, w1 = i - k, min(i + k, hi)
        if AV[i] == max(AV[w0:w1 + 1]) and AV[i] > AV[i - 1]:
            out.append(i)
    return out


def det_wedge3(AV, sig, ext_i) -> bool:
    """H7: 进入扫荡的腿是三推楔形（逐级抬高 + 第三推延伸收缩）。"""
    e = ext_i
    lo = max(0, e - LEG_LOOKBACK)
    peaks = _local_maxima(AV, lo, e, PUSH_K)
    if not peaks or peaks[-1] != e:
        # 极值 bar 本身必须是最后一推（允许它因右侧无 bar 而未进 peaks）
        peaks = [p for p in peaks if p < e] + [e]
    ups = [p for p in peaks if AV[p] <= AV[e]]
    # 取最后三个逐级抬高的推
    if len(ups) < 3:
        return False
    p1, p2, p3 = ups[-3], ups[-2], ups[-1]
    if not (AV[p1] < AV[p2] < AV[p3]):
        return False
    ext2, ext3 = AV[p2] - AV[p1], AV[p3] - AV[p2]
    return ext3 < ext2 and ext3 > 0


def det_micro_double(AV, sig, ext_i) -> bool:
    """H8: 极值后、触发 bar 前出现第二次失败测试。"""
    e, t = ext_i, sig.t
    ext = sig.v_extreme
    tol = DT_TOL_ATR * sig.atr
    for j in range(e + DT_MIN_GAP, t + 1):
        if ext - tol <= AV[j] <= ext:
            return True
    return False


def det_final_flag(AV, FV, sig, pierce_i) -> bool:
    """H9: 刺穿前的末段旗形 + 之前已有充分趋势。"""
    p = pierce_i
    atr = sig.atr
    for end in range(p - 1, max(FLAG_MIN_LEN, p - FLAG_MAX_AGE) - 1, -1):
        start = end - FLAG_MIN_LEN + 1
        if start < PRETREND_N:
            break
        rng = max(AV[start:end + 1]) - min(FV[start:end + 1])
        if rng > FLAG_RANGE_ATR * atr:
            continue
        # 旗形前趋势：进旗形前 PRETREND_N 根内朝扫荡方向走出 >= PRETREND_ATR
        pre = AV[start] - min(FV[max(0, start - PRETREND_N):start])
        if pre >= PRETREND_ATR * atr:
            return True
    return False


# ---- 从 Sig 恢复 ext_i / pierce_i（0711 的 Sig 没存，重扫一次索引） ----
_EXT_CACHE: dict[tuple, tuple] = {}


def index_signal(sig, bars):
    """定位扫荡极值 bar 与首次刺穿 bar：极值 = t 之前最后一个 AV == v_extreme 的 bar；
    刺穿 = 从极值向前回溯首个 AV > v_level 的连续段起点。与引擎同构，仅重建索引。"""
    key = (sig.symbol, sig.dir, sig.ts)
    if key in _EXT_CACHE:
        return _EXT_CACHE[key]
    v = sig.v
    AV = [max(v * b.high, v * b.low) for b in bars]
    ext_i = max(range(0, sig.t + 1), key=lambda i: (AV[i] == sig.v_extreme, i))
    pierce_i = ext_i
    for i in range(ext_i, -1, -1):
        if AV[i] > sig.v_level:
            pierce_i = i
        else:
            break
    _EXT_CACHE[key] = (ext_i, pierce_i)
    return ext_i, pierce_i


# ---------------- 统计 ----------------
def welch_p(xs, ys):
    nx, ny = len(xs), len(ys)
    if nx < 2 or ny < 2:
        return 1.0
    mx, my = sum(xs) / nx, sum(ys) / ny
    vx = sum((a - mx) ** 2 for a in xs) / (nx - 1)
    vy = sum((a - my) ** 2 for a in ys) / (ny - 1)
    se = math.sqrt(vx / nx + vy / ny)
    if se == 0:
        return 1.0
    z = (mx - my) / se
    return math.erfc(abs(z) / math.sqrt(2))  # 大样本正态近似，双尾


def bh_fdr(pvals, q=FDR_Q):
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    passed = [False] * m
    kmax = -1
    for rank, i in enumerate(order, 1):
        if pvals[i] <= q * rank / m:
            kmax = rank
    for rank, i in enumerate(order, 1):
        if rank <= kmax:
            passed[i] = True
    return passed


def cell(rs):
    n = len(rs)
    if n == 0:
        return "n=0"
    avg = sum(rs) / n
    win = sum(1 for r in rs if r > 0) / n
    flag = "" if n >= MIN_N else " (不可用<30)"
    return f"n={n} avgR={avg:+.3f} win={win:.0%}{flag}"


# ---------------- 主流程 ----------------
def main():
    P = print
    P("H7-H9 形态分桶回测 — 定义锁死单次运行（参数见脚本头）")
    P("信号引擎/宇宙/模拟器 = backtest_skill_rules_20260711（H4 扫荡-反转三步走）")
    P()
    data, failed = base.fetch_all()
    P(f"数据: {len(data)} 品种成功, {len(failed)} 失败 {[f[0] for f in failed]}")

    rows = []  # (sig, R_baseline, flags dict)
    total = 0
    for sym, (h4, d1) in sorted(data.items()):
        sigs, _ = base.scan_symbol(sym, h4)
        total += len(sigs)
        for v in (1.0, -1.0):
            AV, FV, MIDV = base._arrays(h4, v)
            for sig in sigs:
                if sig.v != v:
                    continue
                ext_i, pierce_i = index_signal(sig, h4)
                _, r, _ = base.sim_baseline(AV, FV, MIDV, sig, base.BASE_BUFFER)
                flags = {
                    "H7_wedge3": det_wedge3(AV, sig, ext_i),
                    "H8_micro_double": det_micro_double(AV, sig, ext_i),
                    "H9_final_flag": det_final_flag(AV, FV, sig, pierce_i),
                }
                rows.append((sig, r, flags))
    P(f"信号总数: {total}（模拟成功 {len(rows)}）")
    P()

    names = ["H7_wedge3", "H8_micro_double", "H9_final_flag"]
    labels = {"H7_wedge3": "H7 楔形三推(进扫荡腿)",
              "H8_micro_double": "H8 微双顶底(极值二测)",
              "H9_final_flag": "H9 最终旗形(终推前停顿)"}
    pvals, diffs, buckets = [], [], []
    for nm in names:
        yes = [r for (_s, r, f) in rows if f[nm]]
        no = [r for (_s, r, f) in rows if not f[nm]]
        d = (sum(yes) / len(yes) if yes else 0.0) - (sum(no) / len(no) if no else 0.0)
        pvals.append(welch_p(yes, no))
        diffs.append(d)
        buckets.append((yes, no))
    passed = bh_fdr(pvals)

    P("假设            形态在场                        形态不在场                    ΔavgR    p(Welch)  BH-FDR")
    for nm, (yes, no), d, p, ok in zip(names, buckets, diffs, pvals, passed):
        P(f"{labels[nm]}")
        P(f"    在场:   {cell(yes)}")
        P(f"    不在场: {cell(no)}")
        P(f"    ΔavgR={d:+.3f}R  p={p:.4f}  FDR通过={'是' if ok else '否'}")
        both_n = len(yes) >= MIN_N and len(no) >= MIN_N
        if ok and both_n and abs(d) >= NOTABLE_DIFF:
            verdict = "数据支持（过全部门槛）" if d > 0 else "数据反对（形态在场更差）"
        elif not both_n:
            verdict = "样本不足（n<30，一票否决不下结论）"
        else:
            verdict = "分不清（未过 0.15R+FDR 门槛）"
        P(f"    裁决: {verdict}")
        P()

    P("声明: 单次运行、参数锁死；signal 按 symbol 聚簇并非独立样本，p 值偏乐观；")
    P("      正结果也只算线索，须按对抗验证铁律复核后才可进 skill。")


if __name__ == "__main__":
    main()
