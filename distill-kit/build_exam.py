#!/usr/bin/env python3
"""出考卷：把交易员带时间戳的真实订单 + 同期「他没出手」的对照点，做成盲测题。

用法：
  python3 build_exam.py --format tom-episodes --src ~/backup/research/work/tom/episodes.jsonl \
      --quotes ~/backup/claude/skills/brooks-ict-lean/references/validation/distill_audit_20260924/tom_recovered/TOM_READ_INDEX.txt \
      --out exams/tom.jsonl
  python3 build_exam.py --format canonical --src my_trader.jsonl --out exams/x.jsonl

canonical 格式（其他交易员用这个）：每行一张单
  {"sym":"GBPUSD","time":"2024-03-08T09:15:00Z","side":"LONG","type":"limit|market","entry":1.271,"stop":1.2685,
   "id":"可选","quotes":["可选：他当时的原话"]}
"""
import argparse, bisect, collections, json, os, random, re, sys, time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dk.common import Bars, load_config, market_snapshot, iso, kit_path

ALIAS = {"FTSE": "UK100", "UK100": "UK100", "DAX": "GER40", "GER30": "GER40", "DE40": "GER40", "GERMANY40": "GER40",
         "DOW": "US30", "DJI": "US30", "SPX": "US500", "SP500": "US500", "NASDAQ": "NAS100", "NDX": "NAS100", "US100": "NAS100",
         "GOLD": "XAUUSD", "SILVER": "XAGUSD", "OIL": "XTIUSD", "WTI": "XTIUSD", "USOIL": "XTIUSD", "NIKKEI": "JPN225", "JP225": "JPN225"}
DAY = 86400


def norm_sym(s):
    if not s:
        return None
    s = re.sub(r"[^A-Z0-9]", "", str(s).upper())
    return ALIAS.get(s, s)


def to_ts(t):
    if isinstance(t, (int, float)):
        return int(t)
    return int(datetime.fromisoformat(str(t).replace("Z", "+00:00")).astimezone(timezone.utc).timestamp())


def load_quotes(path):
    """msg_id -> [原话]。支持 TOM_READ_INDEX.txt，或 jsonl（{"msg_id"|"id": 123, "text": "..."}）。"""
    q = collections.defaultdict(list)
    if not path:
        return q
    if path.endswith(".jsonl"):
        for l in open(path, encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                mid = r.get("msg_id", r.get("id"))
                if mid is not None and r.get("text"):
                    q[int(mid)].append(r["text"][:600])
        return q
    txt = open(path, encoding="utf-8").read()
    for m in re.finditer(r'tom_([A-Za-z0-9]+)_(\d{8})_([\d_]+)\[([\w.]+)\]: "(.+?)"(?=<br>| \|)', txt):
        line = f"[{m.group(4)}] {m.group(5)[:400]}"
        # 卡片 id = 品种_日期_消息号；订单常在相邻消息里，所以同时按 (品种, 日期) 建索引
        keys = [int(i) for i in m.group(3).split("_") if i] + [(norm_sym(m.group(1)), m.group(2))]
        for k in keys:
            if line not in q[k]:
                q[k].append(line)
    return q


def from_tom(src, quotes, include_reference):
    rows = [json.loads(l) for l in open(src, encoding="utf-8") if l.strip()]
    orders, busy = [], collections.defaultdict(list)
    for r in rows:
        sym = norm_sym(r["decision_context"].get("instrument"))
        ts = to_ts(r["decision_context"]["decision_time"])
        if sym:
            busy[sym].append(ts)  # 他在这个品种上任何发言都算「在看」，对照点要避开
        d = r["decision"]
        if d["action"] not in ("TRADE", "WAIT") or d["direction"] not in ("LONG", "SHORT") or not (d["entry"] and d["stop"]):
            continue
        if r["quality_class"] == "REJECTED":
            continue
        if r["quality_class"] == "REFERENCE_ONLY" and (not include_reference or r["metadata"].get("admission_status")):
            continue  # 默认只用 SILVER；--include-reference 再加上几何不含糊的 REFERENCE_ONLY
        mid = r["metadata"].get("original_message_id")
        day = time.strftime("%Y%m%d", time.gmtime(ts))
        qs = (quotes.get(mid) if mid is not None else None) or quotes.get((sym, day)) or \
            quotes.get((sym, time.strftime("%Y%m%d", time.gmtime(ts - DAY)))) or []
        orders.append({"sym": sym, "ts": ts, "side": d["direction"],
                       "type": "market" if d["action"] == "TRADE" else "limit",  # TRADE=NOW 市价；WAIT=挂单等成交
                       "entry": float(d["entry"]), "stop": float(d["stop"]), "episode_id": r["episode_id"],
                       "msg_id": mid, "quotes": list(qs)})
    return orders, busy


def from_canonical(src):
    orders, busy = [], collections.defaultdict(list)
    for i, l in enumerate(open(src, encoding="utf-8")):
        if not l.strip():
            continue
        r = json.loads(l)
        o = {"sym": norm_sym(r["sym"]), "ts": to_ts(r.get("ts", r.get("time"))), "side": r["side"].upper(),
             "type": r.get("type", "limit"), "entry": float(r["entry"]), "stop": float(r["stop"]),
             "episode_id": r.get("id", f"row{i}"), "msg_id": r.get("msg_id"), "quotes": r.get("quotes", [])}
        orders.append(o)
        busy[o["sym"]].append(o["ts"])
    return orders, busy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", choices=["tom-episodes", "canonical"], required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--quotes", help="TOM_READ_INDEX.txt 或 {msg_id,text} jsonl；只给优化器看，桌面看不到")
    ap.add_argument("--include-reference", action="store_true", help="tom：加入 REFERENCE_ONLY 里几何清楚的单（样本更多，噪声更大）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--bars-dir")
    ap.add_argument("--neg-ratio", type=float, default=0.5, help="每道真题配多少道对照题（他没出手的时点）")
    ap.add_argument("--quiet-days", type=float, default=3, help="对照点前后几天内他不能在该品种发过言")
    ap.add_argument("--holdout-frac", type=float, default=0.25, help="按时间最后这部分做留出集，优化全程不碰")
    ap.add_argument("--dev-frac", type=float, default=0.2, help="非留出部分里随机抽这么多做验证集")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    cfg = load_config()
    bars = Bars(a.bars_dir or cfg["bars_dir"])
    rnd = random.Random(a.seed)

    if a.format == "tom-episodes":
        orders, busy = from_tom(a.src, load_quotes(a.quotes), a.include_reference)
    else:
        orders, busy = from_canonical(a.src)
    for s in busy:
        busy[s].sort()

    drop = collections.Counter()
    good = []
    for o in orders:
        if (o["side"] == "LONG" and o["stop"] >= o["entry"]) or (o["side"] == "SHORT" and o["stop"] <= o["entry"]):
            drop["几何不合法"] += 1; continue
        if not bars.has(o["sym"]):
            drop[f"缺K线:{o['sym']}"] += 1; continue
        lo, hi = bars.span(o["sym"])
        if o["ts"] - lo < 150 * DAY or hi - o["ts"] < 45 * DAY:
            drop["K线覆盖不够(前150天/后45天)"] += 1; continue
        good.append(o)

    # 同一品种同一时刻的多张单（OCO/分批）合成一道题
    groups = collections.defaultdict(list)
    for o in good:
        groups[(o["sym"], o["ts"])].append(o)

    items = []
    for (sym, ts), os_ in sorted(groups.items(), key=lambda kv: kv[0][1]):
        snap = market_snapshot(bars, sym, ts)
        if not snap or not snap["atr_h4"]:
            drop["决策时点无K线"] += 1; continue
        qs = []
        for o in os_:
            qs += [x for x in o.pop("quotes") if x not in qs]
        items.append({"id": f"p_{sym}_{ts}", "kind": "pos", "sym": sym, "ts": ts, "t": iso(ts), "expert_orders": os_,
                      "quotes": qs, "price": snap["price"], "atr_h4": snap["atr_h4"], "dec": snap["dec"]})

    # 对照题：同品种、真题前后 60 天内、他前后 quiet-days 天没在该品种发言、欧美盘时段、工作日
    negs = []
    for it in list(items):
        if rnd.random() >= a.neg_ratio:
            continue
        for _ in range(40):
            day = (it["ts"] // DAY + rnd.randint(-60, 60)) * DAY
            ts = day + rnd.randint(28, 80) * 900  # 07:00–20:00 UTC 之间的某个 M15 边界
            if time.gmtime(ts).tm_wday >= 5:
                continue
            b = busy[it["sym"]]
            j = bisect.bisect_left(b, ts - a.quiet_days * DAY)
            if j < len(b) and b[j] <= ts + a.quiet_days * DAY:
                continue
            lo, hi = bars.span(it["sym"])
            if ts - lo < 150 * DAY or hi - ts < 45 * DAY:
                continue
            snap = market_snapshot(bars, it["sym"], ts)
            if not snap or not snap["atr_h4"]:
                continue
            negs.append({"id": f"n_{it['sym']}_{ts}", "kind": "neg", "sym": it["sym"], "ts": ts, "t": iso(ts),
                         "expert_orders": [], "quotes": [], "price": snap["price"], "atr_h4": snap["atr_h4"], "dec": snap["dec"]})
            break
    items += negs
    items.sort(key=lambda x: x["ts"])

    # 按时间切留出集；其余随机分训练/验证
    cut = items[int(len(items) * (1 - a.holdout_frac))]["ts"] if items else 0
    for it in items:
        if it["ts"] >= cut:
            it["split"] = "holdout"
        else:
            it["split"] = "dev" if rnd.random() < a.dev_frac else "train"

    os.makedirs(os.path.dirname(kit_path(a.out)) or ".", exist_ok=True)
    with open(kit_path(a.out), "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    c = collections.Counter((it["split"], it["kind"]) for it in items)
    print(f"原始订单 {len(orders)}，可用 {len(good)}，合成真题 {sum(1 for i in items if i['kind'] == 'pos')}，对照题 {len(negs)}")
    for k, v in drop.most_common():
        print(f"  丢弃 {k}: {v}")
    for sp in ("train", "dev", "holdout"):
        print(f"  {sp:8s} 真题 {c[(sp, 'pos')]:4d}  对照 {c[(sp, 'neg')]:4d}")
    if items:
        print(f"  留出集起点 {iso(cut)}；有原话的真题 {sum(1 for i in items if i['quotes'])}")
    print(f"写入 {kit_path(a.out)}")


if __name__ == "__main__":
    main()
