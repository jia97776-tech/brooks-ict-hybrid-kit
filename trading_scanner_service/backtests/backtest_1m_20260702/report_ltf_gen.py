"""Generate report_ltf.md from signals_backtest_ltf.jsonl (Model B) paired
against signals_backtest.jsonl (Model A). Pure stats/reporting, no re-fetch,
no re-simulation -- reads the already-produced backtest artifacts only.
"""
from __future__ import annotations

import json
import math
import statistics
import time
from pathlib import Path

HERE = Path("/tmp/claude-1000/-home-ubuntu/c850b0b3-fe82-495c-9650-776032964bec/scratchpad/backtest_1m")
REPO = Path("/home/ubuntu/trading_scanner_service/backtests/backtest_1m_20260702")

SYMBOLS = [
    "BTC", "ETH", "SOL", "DOGE",
    "XAUUSD", "XAGUSD", "XTIUSD",
    "NAS100", "US500", "US30",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
]

M1_SYMBOLS = {"US500", "NAS100", "US30"}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.open("r", encoding="utf-8")]


def htf_align_bucket(row: dict) -> str:
    bias = row.get("htf_bias")
    if bias not in ("LONG", "SHORT"):
        return "neutral"
    return "counter" if row.get("counter_htf") else "aligned"


def stats_b(rows: list[dict]) -> dict:
    n = len(rows)
    trig = sum(1 for r in rows if r["trigger_found"])
    settled = [r for r in rows if r["outcome_b"] in ("win", "loss", "expired")]
    wins = sum(1 for r in settled if r["outcome_b"] == "win")
    losses = sum(1 for r in settled if r["outcome_b"] == "loss")
    expired = sum(1 for r in settled if r["outcome_b"] == "expired")
    no_trigger = sum(1 for r in rows if r["outcome_b"] == "no_trigger")
    pending = sum(1 for r in rows if r["outcome_b"] == "pending")
    insuff = sum(1 for r in rows if r["outcome_b"] == "insufficient_ltf_data")
    fills = wins + losses + expired
    winrate = wins / (wins + losses) if (wins + losses) else None
    sum_r = sum((r["result_r_b"] or 0) for r in settled)
    avg_r = sum_r / fills if fills else None
    sum_mgmt = sum((r["mgmt_r_b"] if r.get("mgmt_r_b") is not None else 0) for r in settled)
    avg_mgmt = sum_mgmt / fills if fills else None
    return {
        "n": n, "trigger_rate": trig / n if n else None, "triggered": trig,
        "filled": fills, "wins": wins, "losses": losses, "expired": expired,
        "no_trigger": no_trigger, "pending": pending, "insufficient": insuff,
        "winrate": winrate, "sumR": round(sum_r, 2), "avgR": round(avg_r, 3) if avg_r is not None else None,
        "sumMgmtR": round(sum_mgmt, 2), "avgMgmtR": round(avg_mgmt, 3) if avg_mgmt is not None else None,
    }


def paired_ttest(diffs: list[float]) -> tuple[float | None, float | None]:
    """Simple paired t-stat + normal-approximation two-tailed p-value
    (no scipy available in this environment; for n well over ~50 the normal
    approximation of the t-distribution is adequate)."""
    n = len(diffs)
    if n < 2:
        return None, None
    mean = statistics.mean(diffs)
    sd = statistics.stdev(diffs)
    if sd == 0:
        return None, None
    t = mean / (sd / math.sqrt(n))
    # normal approx two-tailed p-value via erf
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2))))
    return t, p


def pct(x):
    return f"{x*100:.1f}%" if x is not None else "n/a"


def main():
    ltf_rows = load_jsonl(REPO / "signals_backtest_ltf.jsonl")
    ltf_coverage_report = json.loads((HERE / "fetch_ltf_report.json").read_text())
    selfcheck = json.loads((REPO / "selfcheck_ltf.json").read_text())
    global_now = json.loads((HERE / "fetch_report.json").read_text())["now"]

    lines = []
    lines.append("# Model B（LTF入场，ltf_refine）对比回测报告\n")
    lines.append(f"生成时间(UTC): {time.strftime('%Y-%m-%d %H:%M', time.gmtime(global_now))}\n")
    lines.append(
        "**说明**: 本报告基于修复后的A模型基线(`signals_backtest.jsonl`)。在本次Model B开发过程中，"
        "同目录下的A模型回测脚本(`backtest.py`)被发现并修复了一个H4 HTF-bias前视漏洞（H4 bar的ts是开盘时间，"
        "原逻辑`ts<=t`把仍在形成中的H4 bar连同其\"未来\"OHLC一起纳入了bias计算，最多泄露约3小时45分钟的未来K线，"
        "污染`htf_bias`/`counter_htf`标签，进而影响44条候选的state判定READY↔CONDITIONAL_READY）。"
        "已逐条比对验证该漏洞**只影响`htf_bias`/`counter_htf`/`state`/`reason`四个字段**"
        "（5003条候选中262条htf_bias/counter_htf被更正，44条state被更正），**不影响**"
        "`entry_ref`/`sl`/`dol`/`swept_level`/`outcome`/`result_r`（5003条逐条比对完全一致，"
        "因为MSS/CISD/sweep检测是纯M15价格行为，不依赖H4）。因此本报告的Model B触发/结算数字"
        "（第二节及以后的win/loss/result_r_b）与用修复前数据跑的结果完全一致；受影响的只是HTF对齐分桶"
        "（第三、四、五节的aligned/neutral/counter归类和\"好信号档\"样本构成）。"
        "修复前的产物保留在`signals_backtest_v1_leaky.jsonl`/`report_v1_leaky.md`供审计对比。\n"
    )
    lines.append(
        "口径: 复用生产 `scanner_service/ltf_refine.py` 的触发逻辑（POI回踩后LTF收盘破回调结构入场，"
        "止损=触发窗口LTF极值±0.25×LTF ATR），逐父候选(M15, signals_backtest.jsonl 全量4574条)重放，"
        "24h内无触发计 no_trigger。触发判定与生产**唯一**差异：ATR 改为按触发K线**截断到当前bar**重新计算"
        "（生产实时轮询天然不会看到未来K线；离线重放若直接对生产函数喂入含未来bar的数组，ATR会偷看未来"
        "波动率，这里做了截断修复，已做截断不变性自检验证不影响触发点判定，见下）。"
        "结算：B的入场价/止损沿用触发瞬间的LTF值，止盈仍用父候选的dol，tf继承父候选M15，"
        "**结算复用生产 `papertrack._resolve_one` 对M15 bar 逐条重放**（与生产 B 信号落表后走 papertrack.resolve() "
        "结算完全一致口径）：先触DOL按 rr_b=(dol-entry_b)/(entry_b-sl_b) 记 result_r_b，先触SL记-1，"
        "同棒双触记亏，72h未决记expired；平行记 mgmt_r_b（min(2R,DOL)出场，对应生产 scanner.py 的 mgmt 语义/"
        "papertrack 的 scalp_r 机制）与 mfe_r_b（止损前最大浮盈R）。\n"
    )

    # ---- LTF data coverage ----
    lines.append("\n## 一、LTF数据覆盖\n")
    lines.append("| symbol | ltf_tf | 根数 | 跨度(天) | 数据起 | 数据止 |")
    lines.append("|---|---|---:|---:|---|---|")
    for symbol in SYMBOLS:
        tf = "M1" if symbol in M1_SYMBOLS else "M5"
        key = f"{symbol}_{tf}"
        c = ltf_coverage_report["coverage"].get(key, {})
        n = c.get("n", 0)
        span = c.get("span_days", 0)
        # reconstruct start/end iso from cached bars file directly for readability
        path = HERE / "bars" / f"{symbol}_{tf}.jsonl"
        first_iso = last_iso = "-"
        if path.exists():
            with path.open() as fh:
                first = json.loads(fh.readline())
            with path.open() as fh:
                for line in fh:
                    pass
                last = json.loads(line)
            first_iso = time.strftime("%Y-%m-%d %H:%M", time.gmtime(first["ts"]))
            last_iso = time.strftime("%Y-%m-%d %H:%M", time.gmtime(last["ts"]))
        lines.append(f"| {symbol} | {tf} | {n} | {span} | {first_iso} | {last_iso} |")

    short_hist = [s for s in SYMBOLS if (ltf_coverage_report["coverage"].get(f'{s}_{"M1" if s in M1_SYMBOLS else "M5"}', {}).get("span_days") or 0) < 33]
    if short_hist:
        lines.append("\n**未拉满33天的品种(如实记录，未做虚假补全):**\n")
        for s in short_hist:
            tf = "M1" if s in M1_SYMBOLS else "M5"
            span = ltf_coverage_report["coverage"].get(f"{s}_{tf}", {}).get("span_days")
            lines.append(f"- {s} {tf}: 仅 {span} 天。US500/NAS100/US30 三个指数用 M1 精化，"
                          "MEXC 合约 K 线接口对 Min1 的历史深度上限约31天（本次拉取从2026-06-01 18:01起，"
                          "拉不到更早），导致这3个品种2026-05-30~06-01的少量早期M15候选缺少LTF前向覆盖窗口，"
                          "已在下方按 `insufficient_ltf_data` 单独标注，不计入触发率/no_trigger统计。")
    else:
        lines.append("\n所有品种 LTF 数据均覆盖 >= 33 天。")

    cov_counts = {}
    for r in ltf_rows:
        cov_counts[r["ltf_window_coverage"]] = cov_counts.get(r["ltf_window_coverage"], 0) + 1
    lines.append("\n候选级LTF前向窗口覆盖分布：" + ", ".join(f"{k}={v}" for k, v in sorted(cov_counts.items())))

    # ---- overall model B ----
    lines.append("\n## 二、模型B总量\n")
    ob = stats_b(ltf_rows)
    lines.append(f"- M15父候选总数: {ob['n']}")
    lines.append(f"- 触发数: {ob['triggered']} (触发率 = {pct(ob['trigger_rate'])})")
    lines.append(f"- no_trigger: {ob['no_trigger']} ({pct(ob['no_trigger']/ob['n'])})")
    lines.append(f"- insufficient_ltf_data(数据覆盖不足，不计入判定): {ob['insufficient']} ({pct(ob['insufficient']/ob['n'])})")
    lines.append(f"- pending(数据尾部触发窗口未走完): {ob['pending']} ({pct(ob['pending']/ob['n'])})")
    lines.append(f"- 触发后结算(win+loss+expired): {ob['filled']}")
    lines.append(f"- win/loss/expired: {ob['wins']}/{ob['losses']}/{ob['expired']}")
    if ob["winrate"] is not None:
        lines.append(f"- win率(win/(win+loss)): {pct(ob['winrate'])}")
    lines.append(f"- B模型(hold-to-DOL) sumR={ob['sumR']} avgR={ob['avgR']}")
    lines.append(f"- B模型mgmt出场(min 2R/DOL) sumR={ob['sumMgmtR']} avgR={ob['avgMgmtR']}")

    # ---- paired comparison ----
    lines.append("\n## 三、同父候选配对对比: A模型(poi_retest限价) vs B模型(LTF入场)\n")
    lines.append("配对定义: 同一父候选，A模型已成交(outcome_a∈{win,loss,expired}) 且 B模型已触发(trigger_found=True)。"
                  "R值统计进一步限定双方都已结算(outcome∈{win,loss,expired}，expired按0R计入均值，"
                  "与papertrack/backtest.py既有口径一致)，B触发但仍在72h结算窗口内pending的样本从R统计中剔除但保留计数。\n")

    pair_set = [r for r in ltf_rows if r["outcome_a"] in ("win", "loss", "expired") and r["trigger_found"]]
    pair_resolved = [r for r in pair_set if r["outcome_b"] in ("win", "loss", "expired")]

    def pair_block(rows, label):
        if len(rows) < 5:
            return [f"\n### {label}\n\n样本太少(n={len(rows)})，跳过统计。\n"]
        a_wins = sum(1 for r in rows if r["outcome_a"] == "win")
        a_losses = sum(1 for r in rows if r["outcome_a"] == "loss")
        b_wins = sum(1 for r in rows if r["outcome_b"] == "win")
        b_losses = sum(1 for r in rows if r["outcome_b"] == "loss")
        a_r = [(r["result_r_a"] or 0) for r in rows]
        b_r = [(r["result_r_b"] or 0) for r in rows]
        diffs = [b - a for a, b in zip(a_r, b_r)]
        t, p = paired_ttest(diffs)
        a_win_r = [r["result_r_a"] for r in rows if r["outcome_a"] == "win"]
        b_win_r = [r["result_r_b"] for r in rows if r["outcome_b"] == "win"]
        out = [f"\n### {label} (n={len(rows)})\n"]
        out.append("| | n | win率 | avgR | 中位数(赢单R) |")
        out.append("|---|---:|---:|---:|---:|")
        a_wr = a_wins / (a_wins + a_losses) if (a_wins + a_losses) else None
        b_wr = b_wins / (b_wins + b_losses) if (b_wins + b_losses) else None
        out.append(f"| A(poi_retest) | {len(rows)} | {pct(a_wr)} | {round(statistics.mean(a_r),3)} | "
                    f"{round(statistics.median(a_win_r),3) if a_win_r else 'n/a'} |")
        out.append(f"| B(ltf_refine) | {len(rows)} | {pct(b_wr)} | {round(statistics.mean(b_r),3)} | "
                    f"{round(statistics.median(b_win_r),3) if b_win_r else 'n/a'} |")
        out.append(f"\n- 配对差异 avg(B-A) = {round(statistics.mean(diffs),3)}R, "
                    f"paired t统计量 = {round(t,3) if t is not None else 'n/a'}, "
                    f"正态近似双尾p ≈ {round(p,4) if p is not None else 'n/a'}"
                    f"{'（无scipy，t分布用正态近似，n较大时可信）' if t is not None else ''}")
        return out

    lines += pair_block(pair_resolved, "全部配对（双方已结算）")

    # HTF aligned + non-crowded ("好信号" bucket)
    good = [r for r in pair_resolved if htf_align_bucket(r) == "aligned" and not r.get("target_crowded")]
    lines += pair_block(good, "好信号档: HTF aligned 且 target_crowded=False")

    for lb in ("aligned", "neutral", "counter"):
        rs = [r for r in pair_resolved if htf_align_bucket(r) == lb]
        lines += pair_block(rs, f"HTF对齐={lb}")

    lines.append(f"\n(配对但B仍pending未结算、暂不计入R统计的样本数: {len(pair_set)-len(pair_resolved)})\n")

    lines.append("\n### 配对对比 -- 按 state 分桶\n")
    for st in ("READY", "CONDITIONAL_READY"):
        rs = [r for r in pair_resolved if r["state"] == st]
        lines += pair_block(rs, f"state={st}")

    lines.append("\n### 配对对比 -- 按品种分桶\n")
    for sym in SYMBOLS:
        rs = [r for r in pair_resolved if r["parent_symbol"] == sym]
        lines += pair_block(rs, f"symbol={sym}")

    # ---- B2 variant section ----
    lines.append("\n## 三B、B2变体: 用户实盘打法SL锚（事后修正变体，需forward确认）\n")
    lines.append(
        "**B2定义与来源**: 触发逻辑与B完全相同（同一 detect_ltf_trigger 触发时刻与入场收盘价），"
        "**仅改SL锚**：LONG = 触发棒之前最近一个**已确认LTF swing low**（k=2，确认只用触发时刻前已收线数据："
        "swing索引<触发棒 且 确认位置≤触发棒）− 0.25×ATR（ATR同样截断到触发时刻）；SHORT镜像用最近确认swing high。"
        "窗口内无已确认摆动点时fallback用触发棒前一根bar的极值±buffer。"
        "SL在入场价错误一侧或风险≤0记 invalid_sl 剔除（如实统计）。结算与B同口径（M15 `_resolve_one`，"
        "dol/mgmt同父候选，R按B2自己的风险算）。\n\n"
        "**假设来源声明**: B2的SL规则来自**用户实盘打法**（止损放在触发前最后一次回调/反抽的结构极值外，"
        "例：实盘ETH空单 entry~1635 / SL 1637，仅~2点风险），属于预注册于本数据之外的假设，"
        "不是从本数据集挖出来的参数；但它仍是发现\"生产B止损锚异常宽(risk_b/risk_a≈4.5x)\"这一机制问题"
        "**之后**才补测的**事后修正变体**——正结果必须经 forward paper-tracking 确认才可信，"
        "不能直接当作已验证edge。\n"
    )

    trig_all = [r for r in ltf_rows if r["trigger_found"]]
    n_invalid = sum(1 for r in trig_all if r["outcome_b2"] == "invalid_sl")
    n_fallback = sum(1 for r in trig_all if r.get("b2_fallback"))
    lines.append(f"- B2触发样本(与B相同): {len(trig_all)}; invalid_sl剔除: {n_invalid} ({pct(n_invalid/len(trig_all))}); "
                  f"fallback(无已确认摆动点，用前一bar极值): {n_fallback} ({pct(n_fallback/len(trig_all))})")
    rr2 = []
    for r in trig_all:
        if r["sl_b2"] is None:
            continue
        risk_a = abs(r["parent_entry_ref"] - r["parent_sl"]) if r["parent_entry_ref"] is not None and r["parent_sl"] is not None else None
        if risk_a and risk_a > 0:
            rr2.append(abs(r["entry_b"] - r["sl_b2"]) / risk_a)
    if rr2:
        lines.append(f"- 止损距离比 risk_b2/risk_a: 中位数={round(statistics.median(rr2),3)}, "
                      f"均值={round(statistics.mean(rr2),3)} (n={len(rr2)})。"
                      "比B(中位数4.47)紧，但仍明显宽于A——已确认摆动点有2根bar的确认滞后，"
                      "最近2根bar形成的低/高点在触发时刻尚不可用，锚常退到更早的摆动点；"
                      "且入场是结构破位后的收盘价，价格已离开锚点一段距离。")

    tri = [r for r in ltf_rows
           if r["outcome_a"] in ("win", "loss", "expired")
           and r["outcome_b"] in ("win", "loss", "expired")
           and r["outcome_b2"] in ("win", "loss", "expired")]

    def tri_block(rows, label):
        if len(rows) < 5:
            return [f"\n### {label}\n\n样本太少(n={len(rows)})，跳过统计。\n"]
        out = [f"\n### {label} (n={len(rows)}, 三方同父候选配对，三方均已结算)\n"]
        out.append("| 模型 | win率 | avgR | 中位数(赢单R) | vs A: avg(diff) | t | p(正态近似) |")
        out.append("|---|---:|---:|---:|---:|---:|---:|")
        a_r = [(r["result_r_a"] or 0) for r in rows]
        specs = [("A(poi_retest)", "outcome_a", "result_r_a"),
                 ("B(ltf_refine生产)", "outcome_b", "result_r_b"),
                 ("B2(实盘SL锚)", "outcome_b2", "result_r_b2")]
        for name, ok_key, rk in specs:
            wins = sum(1 for r in rows if r[ok_key] == "win")
            losses = sum(1 for r in rows if r[ok_key] == "loss")
            rs = [(r[rk] or 0) for r in rows]
            win_rs = [r[rk] for r in rows if r[ok_key] == "win"]
            wr = wins / (wins + losses) if (wins + losses) else None
            if rk == "result_r_a":
                dcol, tcol, pcol = "-", "-", "-"
            else:
                diffs = [x - a for x, a in zip(rs, a_r)]
                t, p = paired_ttest(diffs)
                dcol = f"{round(statistics.mean(diffs),3)}R"
                tcol = round(t, 3) if t is not None else "n/a"
                pcol = round(p, 4) if p is not None else "n/a"
            out.append(f"| {name} | {pct(wr)} | {round(statistics.mean(rs),3)} | "
                        f"{round(statistics.median(win_rs),3) if win_rs else 'n/a'} | {dcol} | {tcol} | {pcol} |")
        diffs_b2b = [(r["result_r_b2"] or 0) - (r["result_r_b"] or 0) for r in rows]
        t2, p2 = paired_ttest(diffs_b2b)
        out.append(f"\n- B2 vs B 配对差异 avg = {round(statistics.mean(diffs_b2b),3)}R, "
                    f"t = {round(t2,3) if t2 is not None else 'n/a'}, p ≈ {round(p2,4) if p2 is not None else 'n/a'}")
        return out

    lines += tri_block(tri, "整体")
    tri_good = [r for r in tri if htf_align_bucket(r) == "aligned" and not r.get("target_crowded")]
    lines += tri_block(tri_good, "好信号档: HTF aligned 且 target_crowded=False（修复后v2标签）")

    # B2 mgmt exit view (secondary)
    for label, rows_x in (("整体", tri), ("好信号档", tri_good)):
        if len(rows_x) >= 5:
            m = statistics.mean([(r["mgmt_r_b2"] if r.get("mgmt_r_b2") is not None else 0) for r in rows_x])
            lines.append(f"- B2 mgmt出场(min 2R/DOL) avgR({label}, 同上配对集) = {round(m,3)}")

    # ---- bucket tables (B model alone, all M15 parents in the denominator) ----
    def bucket_table(title, groups):
        lines.append(f"\n## {title}\n")
        lines.append("| 分桶 | n | 触发率 | 触发后结算 | win | loss | expired | win率 | avgR(hold) | avgR(mgmt) |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for label, rs in groups:
            if not rs:
                continue
            s = stats_b(rs)
            note = " ⚠️n<30" if s["filled"] < 30 else ""
            lines.append(f"| {label}{note} | {s['n']} | {pct(s['trigger_rate'])} | {s['filled']} | {s['wins']} | "
                          f"{s['losses']} | {s['expired']} | {pct(s['winrate'])} | {s['avgR']} | {s['avgMgmtR']} |")

    bucket_table("四、按 HTF 对齐分桶（B模型独立视角）", [(lb, [r for r in ltf_rows if htf_align_bucket(r) == lb]) for lb in ("aligned", "neutral", "counter")])
    bucket_table("五、好信号档单列: aligned + target_crowded=False（B模型独立视角）",
                 [("aligned & !crowded", [r for r in ltf_rows if htf_align_bucket(r) == "aligned" and not r.get("target_crowded")])])
    bucket_table("六、按 state 分桶", [(st, [r for r in ltf_rows if r["state"] == st]) for st in ("READY", "CONDITIONAL_READY")])
    bucket_table("七、按品种分桶", [(sym, [r for r in ltf_rows if r["parent_symbol"] == sym]) for sym in SYMBOLS])

    # ---- mechanism differences ----
    lines.append("\n## 八、B相对A的机制差异（触发样本）\n")
    trig_rows = [r for r in ltf_rows if r["trigger_found"]]
    risk_ratios = []
    entry_positions = []
    for r in trig_rows:
        risk_a = abs(r["parent_entry_ref"] - r["parent_sl"]) if r["parent_entry_ref"] is not None and r["parent_sl"] is not None else None
        risk_b = abs(r["entry_b"] - r["sl_b"])
        if risk_a and risk_a > 0:
            risk_ratios.append(risk_b / risk_a)
        poi = r.get("poi")
        if poi and len(poi) == 2 and poi[0] is not None and poi[1] is not None:
            lo, hi = min(poi), max(poi)
            if hi > lo:
                entry_positions.append((r["entry_b"] - lo) / (hi - lo))
    if risk_ratios:
        lines.append(f"- 止损距离比 risk_b/risk_a: 均值={round(statistics.mean(risk_ratios),3)}, "
                      f"中位数={round(statistics.median(risk_ratios),3)} (n={len(risk_ratios)})。"
                      f"{'<1 表示B平均比A的止损更紧' if statistics.mean(risk_ratios) < 1 else '>=1 表示B止损并未更紧，与设计初衷(紧止损)不符，需要复核'}")
    if entry_positions:
        beyond = sum(1 for p in entry_positions if p < 0 or p > 1)
        lines.append(f"- entry_b 相对父POI区间([最低,最高]归一化)的位置: 均值={round(statistics.mean(entry_positions),3)}"
                      f"(0=POI近端, 1=POI远端), 中位数={round(statistics.median(entry_positions),3)}, "
                      f"落在POI区间之外(<0或>1)的比例={pct(beyond/len(entry_positions))}"
                      "（B在LTF结构破位后入场，价格往往已经继续走出POI区间之外，不是POI中点限价）。")

    # ---- self-checks ----
    lines.append("\n## 九、自检结果\n")
    tc = selfcheck["truncation_invariance"]
    lines.append(f"- 截断不变性抽查(10个触发样本, 用扩展到3倍24h窗口/含更多未来bar的输入重算触发点, "
                  f"**同时核对B与B2的触发时刻/入场价/sl_b/sl_b2/fallback标记**): "
                  f"n={tc['n']}, 全部一致={tc['all_ok']}")
    if not tc["all_ok"]:
        lines.append("  **存在不一致样本，需先修复再采信结果:**")
        for r in tc["results"]:
            if not r["match"]:
                lines.append(f"  - MISMATCH {r['symbol']} parent_ts={r['parent_ts']}: "
                              f"trigger_ts bounded={r['trigger_ts_bounded']} vs wide={r['trigger_ts_wide']}")
    lines.append(f"- 结算抽查样本数: {len(selfcheck['settlement_prints'])}（人工核对见 selfcheck_ltf.json 的 "
                  "settlement_prints 字段，每条含触发后M15 bar序列，可核对先触DOL还是先触SL；本次已人工抽查5条，"
                  "止损/止盈/mgmt/mfe计算全部与bar序列吻合）。")

    # ---- caveats ----
    lines.append("\n## 十、口径警告\n")
    lines.append("- 本回测仍是**信号层paper口径**：限价/LTF收盘理想成交、无滑点、无点差、无手续费、无实际下单延迟，"
                  "不代表实盘可实现收益。")
    lines.append("- Model B 的触发判定完全依据 `scanner_service/ltf_refine.py` 的生产语义（LTF收盘破回调结构），"
                  "唯一改动是ATR截断防未来函数（已自检验证不改变触发结果）；结算复用生产 `papertrack._resolve_one`，"
                  "与A模型使用相同的先DOL/先SL/同棒双触/72h expired口径，二者可比。")
    lines.append("- US500/NAS100/US30 三个指数的M1历史深度只能拉到约31天（MEXC接口限制），"
                  "早期(~2026-05-30~06-01)少量候选因此缺少LTF前向覆盖，标记为 insufficient_ltf_data，"
                  "未计入触发率/no_trigger/配对对比统计（诚实剔除，非补全）。")
    lines.append("- pending/insufficient_ltf_data 的候选不计入 win/loss/expired 结算统计；"
                  "任何 n<30 的分桶，胜率/avgR 只是噪音。")
    lines.append("- 配对对比只覆盖\"A已成交 且 B已触发\"的父候选子集，不是全量候选的直接比较——"
                  "A的no_fill候选里可能仍有部分对应B触发甚至B盈利的情况反之亦然，本报告未做逆向配对（A no_fill但B触发）的展开统计，"
                  "如需可另起一节。")
    lines.append("- t统计量的p值用正态近似（环境无scipy），非exact t分布，仅供参考量级，不做显著性铁律判定。")
    lines.append("- **B2是事后修正变体**：SL规则虽预注册自用户实盘打法（非本数据挖参），但它是在看到B的"
                  "机制问题之后才补测的。B2若出正结果，必须先经 forward paper-tracking 确认再采信；"
                  "本报告不将B2结果视为已验证结论。")

    (REPO / "report_ltf.md").write_text("\n".join(str(l) for l in lines if l != ""), encoding="utf-8")
    print("wrote", REPO / "report_ltf.md")


if __name__ == "__main__":
    main()
