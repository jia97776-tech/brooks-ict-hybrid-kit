#!/usr/bin/env python3
"""打分：像不像（忠实度）+ 赚不赚（同一固定口径结算），可两份答卷配对比较。

  python3 score.py --exam exams/tom.jsonl --run lean                  # 单份
  python3 score.py --exam exams/tom.jsonl --run bare --run lean        # 配对比较：lean 比裸模型强多少
  python3 score.py --exam exams/tom.jsonl --run lean --run lean_rep1   # 同一手册跑两遍 = 噪声地板
  加 --settle 同时结算模型的单和交易员本人的单。
"""
import argparse, json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dk.common import Bars, boot_ci, kit_path, load_config, mean, paired_boot, pct, read_jsonl, settle
from dk.desk import score_run


def load_run(tag):
    d = kit_path(os.path.join("runs", tag))
    meta = json.load(open(os.path.join(d, "meta.json")))
    ans = {}
    for r in read_jsonl(os.path.join(d, "answers.jsonl")):
        ans[r["id"]] = r  # 同一题多行时取最后一行
    return meta, ans


def settle_side(bars, it, side, otype, entry, stop):
    return settle(bars, it["sym"], it["ts"], side, otype, entry, stop, it["price"])


def outcome_stats(rows):
    f = [r for r in rows if r.get("filled")]
    if not f:
        return "无成交"
    r2 = [r["r2"] for r in f]
    lo, hi = boot_ci(r2)
    return (f"成交 {len(f)}/{len(rows)}  先到1R {pct(mean([r['hit1R'] for r in f]))}  先到2R {pct(mean([r['hit2R'] for r in f]))}  "
            f"2R目标均值 {mean(r2):+.2f}R [{lo:+.2f},{hi:+.2f}]")


def report(tag, items, sc, ans, bars, do_settle):
    pos = [it for it in items if it["kind"] == "pos"]
    neg = [it for it in items if it["kind"] == "neg"]
    s = [sc[it["id"]]["score"] for it in items]
    lo, hi = boot_ci(s)
    parsed = sum(1 for it in items if sc[it["id"]]["parsed"])
    print(f"\n=== {tag} ===  {len(items)} 题（真题 {len(pos)} / 对照 {len(neg)}），解析成功 {parsed}")
    print(f"忠实分 {mean(s):.3f}  95%CI [{lo:.3f}, {hi:.3f}]")
    acted_pos = [sc[it["id"]] for it in pos if sc[it["id"]]["acted"]]
    print(f"真题出手率 {pct(len(acted_pos) / len(pos) if pos else None)}   对照题不出手率 "
          f"{pct(mean([sc[it['id']]['score'] for it in neg]) if neg else None)}")
    if acted_pos:
        side = [x["side_ok"] for x in acted_pos]
        same = [x for x in acted_pos if x["side_ok"]]
        print(f"出手的真题里：方向一致 {pct(mean(side))}", end="")
        if same:
            ee = [x["entry_err"] for x in same]; se = [x["stop_err"] for x in same]
            print(f"；方向对的 {len(same)} 题：入场误差中位 {statistics.median(ee):.2f} ATR(H4)，"
                  f"入场≤0.5ATR {pct(mean([e <= 0.5 for e in ee]))}，止损≤0.5ATR {pct(mean([e <= 0.5 for e in se]))}，"
                  f"市价/挂单一致 {pct(mean([x['type_ok'] for x in same]))}")
        else:
            print()
    if do_settle:
        mine, his = [], []
        for it in items:
            a = (ans.get(it["id"]) or {}).get("answer")
            if a and a["decision"] != "不做":
                mine.append(settle_side(bars, it, a["side"], "market" if a["decision"] == "市价" else "limit", a["entry"], a["stop"]))
        for it in pos:
            for e in it["expert_orders"]:
                his.append(settle_side(bars, it, e["side"], e["type"], e["entry"], e["stop"]))
        print(f"结算·模型的单：{outcome_stats(mine)}")
        print(f"结算·交易员本人（同一批题）：{outcome_stats(his)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exam", required=True)
    ap.add_argument("--run", action="append", required=True)
    ap.add_argument("--settle", action="store_true")
    a = ap.parse_args()
    cfg = load_config()
    bars = Bars(cfg["bars_dir"])
    exam = {it["id"]: it for it in read_jsonl(kit_path(a.exam))}
    runs = [(t, *load_run(t)) for t in a.run]
    ids = set(exam)
    for _, meta, ans in runs:
        ids &= set(ans)  # 只比都答过的题
    items = sorted((exam[i] for i in ids), key=lambda x: x["ts"])
    if not items:
        sys.exit("没有共同答过的题。")
    scs = []
    for tag, meta, ans in runs:
        sc = score_run(items, {k: v for k, v in ans.items()})
        scs.append(sc)
        report(tag, items, sc, ans, bars, a.settle)
        with open(kit_path(os.path.join("runs", tag, "scored.jsonl")), "w", encoding="utf-8") as f:
            for it in items:
                f.write(json.dumps({**sc[it["id"]], "sym": it["sym"], "t": it["t"],
                                    "answer": (ans.get(it["id"]) or {}).get("answer"),
                                    "expert": it["expert_orders"]}, ensure_ascii=False) + "\n")
    if len(runs) == 2:
        (t1, _, a1), (t2, _, a2) = runs[0], runs[1]
        d, (lo, hi), p = paired_boot([scs[1][i["id"]]["score"] - scs[0][i["id"]]["score"] for i in items])
        print(f"\n=== 配对：{t2} − {t1} ===\n忠实分差 {d:+.3f}  95%CI [{lo:+.3f}, {hi:+.3f}]  P(>0)={p:.2f}")

        def key(r):
            x = (r or {}).get("answer")
            return None if x is None else ("不做" if x["decision"] == "不做" else x["side"])
        agree = mean([key(a1.get(i["id"])) == key(a2.get(i["id"])) for i in items])
        print(f"两份答卷「做不做+方向」一致率 {pct(agree)}（同一手册两遍时，这就是噪声地板）")


if __name__ == "__main__":
    main()
