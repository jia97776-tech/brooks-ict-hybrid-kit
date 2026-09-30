#!/usr/bin/env python3
"""蒸之前先查：这个交易员的单，比「随机时点、同品种、同方向、同止损宽度」的空模型好多少？
好不出来 → 蒸得再像也只是复制一个硬币。按单型（市价/挂单）分开看，只蒸有 edge 的那一半。

  python3 edge_check.py --exam exams/tom.jsonl [--null 20]
"""
import argparse, collections, os, random, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dk.common import Bars, boot_ci, kit_path, load_config, market_snapshot, mean, pct, read_jsonl, settle

DAY = 86400


def line(name, rows):
    f = [r for r in rows if r.get("filled")]
    if not f:
        return f"{name:22s} 无成交"
    r2 = [r["r2"] for r in f]
    lo, hi = boot_ci(r2)
    return (f"{name:22s} n={len(f):5d}  1R {pct(mean([r['hit1R'] for r in f])):>6s}  2R {pct(mean([r['hit2R'] for r in f])):>6s}  "
            f"2R目标均值 {mean(r2):+.3f}R [{lo:+.3f},{hi:+.3f}]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exam", required=True)
    ap.add_argument("--null", type=int, default=20, help="每张真单配几个随机空模型")
    ap.add_argument("--seed", type=int, default=3)
    a = ap.parse_args()
    cfg = load_config()
    bars = Bars(cfg["bars_dir"])
    rnd = random.Random(a.seed)
    items = [it for it in read_jsonl(kit_path(a.exam)) if it["kind"] == "pos"]
    real, null, flip = collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(list)
    for n, it in enumerate(items):
        for e in it["expert_orders"]:
            g = e["type"]
            r = settle(bars, it["sym"], it["ts"], e["side"], e["type"], e["entry"], e["stop"], it["price"])
            real[g].append(r); real["全部"].append(r)
            if not r.get("filled"):
                continue
            k = abs(r["entry"] - e["stop"]) / it["atr_h4"]  # 止损宽度（H4 ATR 倍数）
            # 方向反过来：同一时刻、同止损宽度、市价
            op = "SHORT" if e["side"] == "LONG" else "LONG"
            p = it["price"]; d = k * it["atr_h4"]
            fr = settle(bars, it["sym"], it["ts"], op, "market", p, p + d if op == "SHORT" else p - d, p)
            flip[g].append(fr); flip["全部"].append(fr)
            # 随机时点：±90 天、工作日 07–20 UTC、同方向、同 ATR 倍数止损、市价
            lo_, hi_ = bars.span(it["sym"])
            got = 0
            for _ in range(a.null * 5):
                if got >= a.null:
                    break
                ts = (it["ts"] // DAY + rnd.randint(-90, 90)) * DAY + rnd.randint(28, 80) * 900
                if time.gmtime(ts).tm_wday >= 5 or ts - lo_ < 150 * DAY or hi_ - ts < 45 * DAY:
                    continue
                s = market_snapshot(bars, it["sym"], ts)
                if not s or not s["atr_h4"]:
                    continue
                dd = k * s["atr_h4"]; p = s["price"]
                nr = settle(bars, it["sym"], ts, e["side"], "market", p, p - dd if e["side"] == "LONG" else p + dd, p)
                null[g].append(nr); null["全部"].append(nr); got += 1
        if (n + 1) % 50 == 0:
            print(f"  {n + 1}/{len(items)}", flush=True)
    for g in ("全部", "market", "limit"):
        if not real[g]:
            continue
        print(f"\n--- {g} ---")
        print(line("交易员本人", real[g]))
        print(line("空模型(随机时点)", null[g]))
        print(line("方向反过来", flip[g]))
    print("\n读法：本人的 1R/2R 命中和均值要明显高于空模型（CI 不重叠）才算有可蒸的判断力；"
          "差不多 = 他赚的是止损宽度这类几何，不是看盘。方向反过来也差不多 = 方向判断没贡献。")


if __name__ == "__main__":
    main()
