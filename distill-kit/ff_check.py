#!/usr/bin/env python3
"""事前校验 + 结算：只保留「发帖时还没成交」的喊单，按固定口径结算，和机器基线（先到 +2R 的比例）比。

  python3 ff_check.py --thread 594513 --tz-scan     # 先确认时区：看哪个偏移下市价单最贴近当时价格
  python3 ff_check.py --thread 594513               # 校验 + 结算 + 报告
  python3 ff_check.py --thread 594513 --thread 459973 --baseline 0.305

事前判定（全部用 K 线自动判）：
  市价单：发帖时价格（最后一根已收盘 M15 的收盘）离他写的进场价 ≤ 0.5×ATR14(M15) + 0.1×ATR14(H4)，否则算「事后补发/时区错」
  挂单：发帖时价格还在进场价的「对的一侧」，且发帖前 6 小时内价格没碰过进场价（碰过 = 可能已成交后才发）
结算：dk/common.py settle，同 distill-kit 口径（挂单 14 天有效、只看初始止损、同根先算止损、30 天未决按收盘计 R）。
"""
import argparse, collections, json, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_exam import norm_sym, to_ts
from dk.common import Bars, atr, boot_ci, iso, kit_path, load_config, mean, pct, settle

H = 3600


def wilson(k, n, z=1.96):
    if not n:
        return (float("nan"), float("nan"))
    p = k / n; d = 1 + z * z / n
    c = p + z * z / (2 * n); r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def snap(bars, sym, ts):
    m = bars.closed(sym, "M15", ts, 30)
    h4 = bars.closed(sym, "H4", ts, 20)
    if not m:
        return None
    return {"price": m[-1]["close"], "atr_m15": atr(m), "atr_h4": atr(h4)}


def check(bars, c, lookback_h=6):
    sym = c["sym"]
    if not bars.has(sym):
        return "缺K线", None
    s = snap(bars, sym, c["ts"])
    if not s or not s["atr_m15"]:
        return "发帖时无K线", None
    L = c["side"] == "LONG"
    if (L and c["stop"] >= c["entry"]) or (not L and c["stop"] <= c["entry"]):
        return "几何不合法", s
    p, e = s["price"], c["entry"]
    tol = 0.5 * s["atr_m15"] + 0.1 * (s["atr_h4"] or 0)
    if c["type"] == "market":
        return ("通过" if abs(p - e) <= tol else "市价单离当时价格太远"), s
    # 挂单：限价在回踩侧，突破挂单在突破侧
    right_side = (e < p) if (L == (c["type"] == "limit")) else (e > p)
    if not right_side and abs(p - e) > tol:
        return "挂单在错误一侧（像已成交）", s
    prev = bars.closed(sym, "M15", c["ts"], lookback_h * 4)
    if any(b["low"] <= e <= b["high"] for b in prev):
        return "发帖前 6 小时价格已碰过进场价", s
    return "通过", s


def tz_scan(bars, calls):
    mk = [c for c in calls if c["type"] == "market" and bars.has(c["sym"])]
    if not mk:
        print("没有市价单，无法自检时区；请确认 FF 账号时区设为 GMT。"); return
    print(f"时区自检（{len(mk)} 张市价单）：偏移 = 页面时间比 UTC 快几小时")
    rows = []
    for off in [x / 2 for x in range(-28, 29)]:
        ok = 0
        for c in mk:
            cc = {**c, "ts": int(c["ts"] - off * H)}
            st, _ = check(bars, cc)
            ok += st == "通过"
        rows.append((ok / len(mk), off))
    rows.sort(reverse=True)
    for r, off in rows[:5]:
        print(f"  偏移 {off:+5.1f}h：{pct(r)} 的市价单贴近当时价格")
    print("最好的偏移明显高于其它才可信；若最好的是 0 以外的值，用 ff_extract.py --tz-hours <偏移> 重新抽取。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thread", action="append", required=True)
    ap.add_argument("--dir", default="data/ff")
    ap.add_argument("--baseline", type=float, default=0.305, help="机器基线：先到 +2R 的比例")
    ap.add_argument("--tz-scan", action="store_true")
    a = ap.parse_args()
    cfg = load_config()
    bars = Bars(cfg["bars_dir"])
    calls = []
    for t in a.thread:
        p = kit_path(os.path.join(a.dir, t, "calls.jsonl"))
        for l in open(p, encoding="utf-8"):
            if l.strip():
                c = json.loads(l)
                if not isinstance(c.get("ts"), (int, float)):  # 外部整理的数据可给 "time": "2021-06-03T08:15:00Z"
                    c["ts"] = to_ts(c.get("ts") or c["time"])
                c.setdefault("thread", t); c.setdefault("author", "?"); c.setdefault("type", "limit")
                c["sym"] = norm_sym(c["sym"]); c["side"] = c["side"].upper(); c["type"] = c["type"].lower()
                c["entry"], c["stop"] = float(c["entry"]), float(c["stop"])
                calls.append(c)
    if a.tz_scan:
        tz_scan(bars, calls); return

    by = collections.defaultdict(list)
    reasons = collections.Counter()
    out = kit_path(os.path.join(a.dir, "checked_" + "_".join(a.thread) + ".jsonl"))
    with open(out, "w", encoding="utf-8") as f:
        for c in sorted(calls, key=lambda x: x["ts"]):
            st, s = check(bars, c)
            reasons[st] += 1
            row = {**c, "t": iso(c["ts"]), "check": st}
            if st == "通过":
                otype = "market" if c["type"] == "market" else "limit"  # settle 按进场价在现价哪侧自动区分回踩/突破
                row["settle"] = settle(bars, c["sym"], c["ts"], c["side"], otype, c["entry"], c["stop"], s["price"])
                by[(c["thread"], c["author"])].append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"共 {len(calls)} 单；事前校验：" + "，".join(f"{k} {v}" for k, v in reasons.most_common()))
    print(f"\n机器基线：先到 +2R {pct(a.baseline)}\n")
    for (t, au), rows in by.items():
        f_ = [r for r in rows if r["settle"].get("filled")]
        k2 = sum(r["settle"]["hit2R"] for r in f_)
        lo, hi = wilson(k2, len(f_))
        r2 = [r["settle"]["r2"] for r in f_]
        rl, rh = boot_ci(r2)
        span = f"{rows[0]['t'][:10]} ~ {rows[-1]['t'][:10]}"
        print(f"帖子 {t} / {au}（{span}）：事前单 {len(rows)}，成交 {len(f_)}")
        if f_:
            print(f"  先到1R {pct(mean([r['settle']['hit1R'] for r in f_]))}   先到2R {pct(k2 / len(f_))} "
                  f"[95%CI {pct(lo)}, {pct(hi)}]   2R目标均值 {mean(r2):+.2f}R [{rl:+.2f},{rh:+.2f}]")
            verdict = "高于基线" if lo > a.baseline else ("低于基线" if hi < a.baseline else "和基线分不开")
            print(f"  → {verdict}（CI 下沿 > 基线才算真的更好）")
        syms = collections.Counter(r["sym"] for r in rows)
        print(f"  品种：{dict(syms.most_common(6))}")
    print(f"\n逐单明细：{out}")


if __name__ == "__main__":
    main()
