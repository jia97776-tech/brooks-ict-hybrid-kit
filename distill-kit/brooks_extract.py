#!/usr/bin/env python3
"""从 brooks_fetch.py 产出的 ES 每日报告里，用模型把「盘前 / 今日预期」部分抽成条件单。

  python3 brooks_extract.py --sample 30                # 先随机抽 30 篇看看（--seed 换一批）
  python3 brooks_extract.py                            # 全部 ES 每日报告（缓存命中的不再调模型）
  python3 brooks_extract.py --stats                    # 只读 orders.jsonl 打印统计
  python3 brooks_extract.py --backend codex --workers 3

模型只看到：标题 + 交易日 + premarket_text（daily chart 一节 + 5-minute chart / what to expect today 一节）。
「Yesterday's setups」和收盘总结一个字都不给。

产出（data/brooks/）：
  orders.jsonl     每篇报告一行：{url, trading_date, ..., orders:[...], levels:[...]}，多次运行按 slug 合并
  canonical.jsonl  只收「方向 + 数字触发价 + 数字止损」的单，一行一张，可直接喂
                   python3 build_exam.py --format canonical --src data/brooks/canonical.jsonl --out exams/brooks.jsonl
  type 映射：stop_entry→"stop"，limit→"limit"，market→"market"，other→"limit"。
  build_exam / settle 只区分 market 和非 market：非 market 一律按「进场价在现价哪侧」自动判成回踩或突破，
  所以 "stop" 能直接用；edge_check 会把它单独列成一组。
"""
import argparse, collections, json, os, random, re, sys, threading
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dk import llm
from dk.common import extract_json, kit_path, load_config, read_jsonl

SYS = ("你从 Al Brooks 价格行为风格的 S&P 500 E-mini（ES）每日报告里抽取条件单。"
       "不要调用任何工具，不要读文件，不要联网。只输出一个 JSON，不要别的文字。")

USER = """标题：{title}
交易日：{trading_date}（品种 ES，S&P 500 E-mini 期货，价格是指数点位）
正文（只有「日线」一节和「5 分钟图 / 今日预期」一节）：
<<<
{text}
>>>

把正文里的条件单抽出来。规则：
1. 订单 = 说交易者（作者、bulls / bears、traders）会、可以、应该在某个条件下朝某个方向进场的句子。
   例："bulls will buy above bar 45 high"、"traders will sell the round number above"、"bulls will scale in lower"、
   "bears want to sell a rally to the September high"。
   只预测走势、没有进场动作的句子（如 "the market will probably test the September low"）不是订单，只把里面的价格放进 levels。
2. explicitness："explicit" = 明确的进场动作（buy / sell / short / go long / enter，含 bulls/bears/traders will buy/sell）；
   "implied" = 只有愿望或偏向（bulls want / hope / need、bears are hoping），但能读出方向和进场条件。
3. 价格只能抄原文里出现的数字（千位逗号去掉，如 "1,234" 写成 1234）。不许推算，不许用你的记忆补数字。
   原文用 K 线编号、"yesterday's high"、"the September low" 之类描述的触发或止损，价格填 null，描述写进 trigger_ref / stop_ref。
4. trigger_kind：
   "stop_entry" = 突破某根 K 线 / 某价位时进场（buy above、sell below、on a breakout）；
   "limit" = 在某价位或区域挂限价（buy at/near support、sell at resistance、scale in lower、buy a pullback to X）；
   "market" = 开盘或此刻直接进；"other" = 都不是。
5. section："daily" = 出自日线一节；"intraday" = 出自 5 分钟图一节。
6. quote：原文里对应的那一整句，逐字复制，不改写、不拼接。
7. probability_words：原文里修饰这笔单的概率词（"60%"、"likely"、"probably"、"good odds"），没有就 ""。
8. levels：正文里出现的每一个价格数字（只要价格；不要 K 线编号、百分比、日期、年份），每个给一句 what 说明。
输出：
{{"orders":[{{"section":"daily|intraday","side":"LONG|SHORT","explicitness":"explicit|implied",
"trigger_kind":"stop_entry|limit|market|other","trigger_price":null,"trigger_ref":"","stop_price":null,"stop_ref":"",
"target_price":null,"target_R":null,"target_ref":"","condition":"","probability_words":"","quote":""}}],
"levels":[{{"price":0,"what":""}}]}}
没有订单就 "orders":[]。"""

KINDS = ("stop_entry", "limit", "market", "other")
TYPE_MAP = {"stop_entry": "stop", "limit": "limit", "market": "market", "other": "limit"}
_plock = threading.Lock()
BARREF = re.compile(r"\bbars?\s*\d", re.I)


def num(x):
    if x is None or isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x) if x else None
    m = re.search(r"\d[\d,]*\.?\d*", str(x))
    if not m:
        return None
    try:
        v = float(m.group(0).replace(",", ""))
        return v or None
    except ValueError:
        return None


def norm_txt(s):
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def price_in_text(p, text_norm):
    if p is None:
        return False
    i = int(p) if float(p).is_integer() else None
    cands = {f"{p:g}"}
    if i is not None:
        cands |= {str(i), f"{i:,}"}
    return any(re.search(rf"(?<![\d,.]){re.escape(c)}(?![\d])", text_norm) for c in cands)


def clean(o, pre_norm, post_norm, med):
    side = str(o.get("side", "")).upper().strip()
    side = {"BUY": "LONG", "SELL": "SHORT"}.get(side, side)
    kind = str(o.get("trigger_kind", "other")).lower().strip()
    kind = kind if kind in KINDS else ("stop_entry" if "stop" in kind else "limit" if "limit" in kind else "other")
    tp, sp, tg = num(o.get("trigger_price")), num(o.get("stop_price")), num(o.get("target_price"))
    quote = str(o.get("quote") or "")[:500]
    qn = norm_txt(quote)
    r = {"section": str(o.get("section", "")).lower(), "side": side,
         "explicitness": str(o.get("explicitness", "")).lower(), "trigger_kind": kind,
         "trigger_price": tp, "trigger_ref": str(o.get("trigger_ref") or "")[:200],
         "stop_price": sp, "stop_ref": str(o.get("stop_ref") or "")[:200],
         "target_price": tg, "target_R": num(o.get("target_R")), "target_ref": str(o.get("target_ref") or "")[:200],
         "condition": str(o.get("condition") or "")[:300], "probability_words": str(o.get("probability_words") or "")[:80],
         "quote": quote}
    # 自检：原话是不是真出自盘前部分；价格是不是原文里的数字、是不是 ES 的量级
    r["quote_found"] = bool(qn) and qn[:120] in pre_norm
    r["quote_in_postclose"] = bool(qn) and not r["quote_found"] and qn[:120] in post_norm
    prices = [x for x in (tp, sp, tg) if x is not None]
    r["prices_in_text"] = all(price_in_text(x, pre_norm) for x in prices)
    r["prices_plausible"] = all(med and 0.85 * med <= x <= 1.15 * med for x in prices) if prices else True
    geom = tp is not None and sp is not None and ((side == "LONG" and sp < tp) or (side == "SHORT" and sp > tp))
    r["executable"] = side in ("LONG", "SHORT") and geom and r["prices_in_text"]
    return r


def extract_one(cfg, be, rep, use_cache):
    user = USER.format(title=rep["title"], trading_date=rep["trading_date"], text=rep["premarket_text"][:12000])
    txt = llm.call(cfg, be, SYS, user, use_cache=use_cache)
    obj = extract_json(txt, "orders") if txt else None
    pre_norm = norm_txt(rep["premarket_text"])
    post_norm = norm_txt(" ".join(s["text"] for s in rep["sections"] if s["key"] not in ("daily_chart", "what_to_expect")))
    levels = []
    for lv in (obj or {}).get("levels") or []:
        p = num(lv.get("price") if isinstance(lv, dict) else lv)
        if p:
            levels.append({"price": p, "what": str(lv.get("what", "") if isinstance(lv, dict) else "")[:120],
                           "in_text": price_in_text(p, pre_norm)})
    ps = sorted(l["price"] for l in levels if l["in_text"] and l["price"] > 1000)
    med = ps[len(ps) // 2] if ps else None
    orders = [clean(o, pre_norm, post_norm, med) for o in (obj or {}).get("orders") or [] if isinstance(o, dict)]
    keep = ("url", "slug", "title", "trading_date", "date_published", "date_published_utc", "publish_delay_min",
            "last_bar_mentioned", "last_bar_close_utc", "modified_after_publish_hours")
    return {**{k: rep.get(k) for k in keep}, "backend": be, "parse_ok": obj is not None,
            "n_orders": len(orders), "n_executable": sum(o["executable"] for o in orders),
            "orders": orders, "levels": levels, "level_median": med,
            "raw_tail": None if obj is not None else (txt or "")[-400:]}


def q(xs, p):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * p
    lo = int(k)
    return xs[lo] + (xs[min(lo + 1, len(xs) - 1)] - xs[lo]) * (k - lo)


def stats(rows):
    rows = [r for r in rows if r["parse_ok"]]
    if not rows:
        print("没有可统计的结果"); return
    n = len(rows)
    ex = [r["n_executable"] for r in rows]
    allo = [o for r in rows for o in r["orders"]]
    exo = [o for o in allo if o["executable"]]
    print(f"\n已抽取 {n} 篇（交易日 {min(r['trading_date'] for r in rows)} → {max(r['trading_date'] for r in rows)}）")
    print(f"  条件单（任何形式）每篇：均值 {sum(r['n_orders'] for r in rows) / n:.2f}，中位 {q([r['n_orders'] for r in rows], .5):.0f}，"
          f"≥1 的 {sum(r['n_orders'] > 0 for r in rows)}/{n}")
    print(f"  可执行单（方向 + 数字触发 + 数字止损）每篇：均值 {sum(ex) / n:.2f}，中位 {q(ex, .5):.0f}，"
          f"≥1 的 {sum(x > 0 for x in ex)}/{n}（{100 * sum(x > 0 for x in ex) / n:.1f}%），分布 "
          + "，".join(f"{k}张:{v}篇" for k, v in sorted(collections.Counter(ex).items())))
    print(f"  全部单 {len(allo)}：有数字触发价 {sum(o['trigger_price'] is not None for o in allo)}，有数字止损 "
          f"{sum(o['stop_price'] is not None for o in allo)}，两者都有 {sum(o['trigger_price'] is not None and o['stop_price'] is not None for o in allo)}，"
          f"有目标（价或R）{sum(o['target_price'] is not None or o['target_R'] is not None for o in allo)}")
    print(f"  触发是 K 线编号的（如 above bar 45 high；有 5 分钟 K 线就能换成数字）："
          f"{sum(bool(BARREF.search(o['trigger_ref'])) for o in allo)}；"
          f"止损是 K 线编号的：{sum(bool(BARREF.search(o['stop_ref'])) for o in allo)}")
    for name, os_ in (("全部单", allo), ("可执行单", exo)):
        c = collections.Counter(o["trigger_kind"] for o in os_)
        e = collections.Counter(o["explicitness"] for o in os_)
        s = collections.Counter(o["section"] for o in os_)
        d = collections.Counter(o["side"] for o in os_)
        print(f"  {name} {len(os_)}：" + "，".join(f"{k} {v}" for k, v in c.most_common()) + " | "
              + "，".join(f"{k} {v}" for k, v in e.most_common()) + " | "
              + "，".join(f"{k} {v}" for k, v in s.most_common()) + " | "
              + "，".join(f"{k} {v}" for k, v in d.most_common()))
    print(f"  自检：原话在盘前正文里找得到 {sum(o['quote_found'] for o in allo)}/{len(allo)}，"
          f"原话出自收盘后段落 {sum(o['quote_in_postclose'] for o in allo)}，"
          f"价格不在原文里 {sum(not o['prices_in_text'] for o in allo)}，价格偏离当篇中位数 >15% {sum(not o['prices_plausible'] for o in allo)}")
    lv = [l["price"] for r in rows for l in r["levels"] if l["in_text"] and l["price"] > 1000]
    if lv:
        print(f"  当篇提到的价位（>1000 且在原文里）：每篇中位 {q([len(r['levels']) for r in rows], .5):.0f} 个，"
              f"全体范围 {min(lv):g} – {max(lv):g}；不在原文里的 level {sum(not l['in_text'] for r in rows for l in r['levels'])} 个")
    bad = [r for r in rows if not r["parse_ok"]]
    if bad:
        print(f"  解析失败 {len(bad)} 篇")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/brooks")
    ap.add_argument("--sample", type=int, default=0, help="随机抽几篇（0 = 全部）")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--backend", help="默认 config 里的 default_backend")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--stats", action="store_true", help="只打印 orders.jsonl 的统计")
    a = ap.parse_args()
    d = kit_path(a.dir)
    opath, cpath = os.path.join(d, "orders.jsonl"), os.path.join(d, "canonical.jsonl")
    if a.stats:
        stats(read_jsonl(opath)); return

    reps = [r for r in read_jsonl(os.path.join(d, "reports.jsonl"))
            if r["market"] == "ES" and r["kind"] == "daily" and r["has_premarket"]]
    if a.sample:
        reps = random.Random(a.seed).sample(reps, min(a.sample, len(reps)))
    cfg = load_config()
    be = a.backend or cfg["default_backend"]
    done = {r["slug"]: r for r in read_jsonl(opath)}
    print(f"待抽取 {len(reps)} 篇（后端 {be}，并发 {a.workers}）", flush=True)
    k = [0]

    def work(rep):
        row = extract_one(cfg, be, rep, not a.no_cache)
        with _plock:
            done[rep["slug"]] = row
            k[0] += 1
            if k[0] % 10 == 0 or k[0] == len(reps):
                print(f"  {k[0]}/{len(reps)}（解析失败累计 {sum(not r['parse_ok'] for r in done.values())}）", flush=True)
        return row

    with ThreadPoolExecutor(max_workers=max(1, a.workers)) as ex:
        list(ex.map(work, reps))

    rows = sorted(done.values(), key=lambda r: r["trading_date"] or "")
    with open(opath, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n = 0
    with open(cpath, "w", encoding="utf-8") as f:
        for r in rows:
            for i, o in enumerate(r["orders"]):
                if not o["executable"]:
                    continue
                f.write(json.dumps({"sym": "ES", "time": r["date_published_utc"], "side": o["side"],
                                    "type": TYPE_MAP[o["trigger_kind"]], "entry": o["trigger_price"], "stop": o["stop_price"],
                                    "id": f"{r['slug']}#{i}", "quotes": [o["quote"]], "target": o["target_price"],
                                    "trigger_kind": o["trigger_kind"], "info_cutoff_utc": r["last_bar_close_utc"]},
                                   ensure_ascii=False) + "\n")
                n += 1
    print(f"写入 {len(rows)} 篇 → {opath}；可执行单 {n} 张 → {cpath}")
    stats(rows)


if __name__ == "__main__":
    main()
