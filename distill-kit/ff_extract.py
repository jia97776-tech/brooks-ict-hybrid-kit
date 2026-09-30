#!/usr/bin/env python3
"""从抓下来的 FF 页面里拆出楼主的帖子，再把「此刻下单/挂单」的喊单结构化。

  python3 ff_extract.py --thread 594513 --inspect         # 先看解析得对不对（打印前 3 个帖子）
  python3 ff_extract.py --thread 594513                   # 拆帖子 + 用模型抽喊单（后端见 config.json）
  python3 ff_extract.py --thread 594513 --no-llm          # 只用正则抽（格式规整的日志够用）

输出 data/ff/<帖子号>/posts.jsonl（全部楼主帖）和 calls.jsonl（结构化喊单）。
时间：默认把页面上的时间当 UTC（请在 FF 账号设置里把时区设为 GMT）；不确定就先跑 ff_check.py --tz-scan。

页面结构没法在云端看到，所以解析是宽松匹配：按帖子永久链接 /thread/post/<id> 或 id="post..." 切块。
--inspect 输出不对的话，改 split_posts() 里的几条正则即可。
"""
import argparse, glob, html as H, json, os, re, sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dk import llm
from dk.common import extract_json, kit_path, load_config

POST_MARK = re.compile(r'(?:/thread/post/(\d{4,})|id="post[_-]?(\d{4,})"|data-postid="(\d{4,})")')
MEMBER = re.compile(r'/member/\d+-([A-Za-z0-9_.\-]+)')
EPOCH_ATTR = re.compile(r'data-[a-z_-]*(?:time|timestamp|date)[a-z_-]*="(\d{10})"')
TEXT_DATE = re.compile(r'([A-Z][a-z]{2} \d{1,2}, \d{4})[ ,]+(\d{1,2}:\d{2}\s?[ap]m)', re.I)
QUOTE = re.compile(r'<blockquote.*?</blockquote>|<div[^>]*class="[^"]*quote[^"]*".*?</div>\s*</div>', re.S | re.I)
IMG = re.compile(r'<img[^>]+src="([^"]+)"', re.I)
CALL_HINT = re.compile(r'\b(buy|sell|long|short|entry|entered|sl|s/l|stop|tp|t/p|limit|pending)\b', re.I)
NUM = re.compile(r'\d+\.\d{2,5}|\b\d{4,5}\b')


def strip(h):
    h = re.sub(r"<(script|style)\b.*?</\1>", " ", h, flags=re.S | re.I)
    h = QUOTE.sub(" ", h)  # 去掉引用别人的内容
    h = re.sub(r"<br\s*/?>|</p>|</div>", "\n", h, flags=re.I)
    t = H.unescape(re.sub(r"<[^>]+>", " ", h))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", t)).strip()


def parse_time(block, tz_hours):
    m = EPOCH_ATTR.search(block)
    if m:
        return int(m.group(1)), "epoch_attr"
    m = TEXT_DATE.search(re.sub(r"<[^>]+>", " ", block))
    if m:
        dt = datetime.strptime(f"{m.group(1)} {m.group(2).replace(' ', '').lower()}", "%b %d, %Y %I:%M%p")
        return int((dt.replace(tzinfo=timezone.utc) - timedelta(hours=tz_hours)).timestamp()), m.group(0)
    return None, None


def split_posts(html_text):
    marks, seen = [], set()
    for m in POST_MARK.finditer(html_text):
        pid = next(g for g in m.groups() if g)
        if pid not in seen:
            seen.add(pid); marks.append((m.start(), pid))
    # 每个帖子 = 从它第一次出现的标记所在标签开头，到下一个帖子标记所在标签开头
    cuts = [max(0, html_text.rfind("<", 0, pos)) for pos, _ in marks] + [len(html_text)]
    return [(pid, html_text[cuts[i]:cuts[i + 1]]) for i, (_, pid) in enumerate(marks)]


def parse_pages(d, tz_hours):
    posts, seen = [], set()
    for fn in sorted(glob.glob(os.path.join(d, "page_*.html"))):
        txt = open(fn, encoding="utf-8", errors="ignore").read()
        for pid, blk in split_posts(txt):
            if pid in seen:
                continue
            seen.add(pid)
            au = MEMBER.search(blk)
            ts, raw = parse_time(blk, tz_hours)
            posts.append({"post_id": pid, "author": au.group(1) if au else None, "ts": ts, "ts_raw": raw,
                          "page": os.path.basename(fn), "text": strip(blk)[:4000],
                          "images": [u for u in IMG.findall(blk) if "attachment" in u or "/image" in u][:6]})
    return posts


LLM_SYS = "你从交易论坛帖子里抽取交易员本人此刻发出的交易指令。只输出 JSON。"
LLM_USER = """帖子作者：{author}；发帖时间（UTC）：{t}；帖子所在的交易日志主要品种：{sym_hint}
帖子正文：
<<<
{text}
>>>
抽出作者在发帖这一刻「正在下的单或刚挂的单」。规则：
- 只要作者本人、当下的指令：已挂的限价/突破挂单、刚刚市价进场、或明确「现在进」。
- 不要：已经平仓的复盘、昨天的单、假设（if…would…）、引用别人的单、只有方向没有价格的观点。
- 已进场并写了进场价 → type=market；挂单 → type=limit（回踩）或 stop（突破）。
- 必须有止损价；没写止损的不要。
- sym 用 EURUSD / GBPUSD / XAUUSD / US30 这种写法。
输出：{{"calls":[{{"sym":"","side":"LONG|SHORT","type":"market|limit|stop","entry":0,"stop":0,"tp":0,"quote":"原文里对应的那句"}}]}}；没有就 {{"calls":[]}}"""

RX_SIDE = re.compile(r'\b(buy|long|sell|short)\b', re.I)
RX_ENTRY = re.compile(r'(?:entry|entered|buy limit|sell limit|buy stop|sell stop|@|at)\s*[:=]?\s*(\d+\.\d{2,5}|\d{4,5})', re.I)
RX_SL = re.compile(r'\b(?:sl|s/l|stop(?: loss)?)\s*[:=@]?\s*(\d+\.\d{2,5}|\d{4,5})', re.I)
RX_TP = re.compile(r'\b(?:tp\d?|t/p|target)\s*[:=@]?\s*(\d+\.\d{2,5}|\d{4,5})', re.I)
RX_SYM = re.compile(r'\b(EUR|GBP|USD|JPY|AUD|NZD|CAD|CHF|XAU|XAG)\s*/?\s*(EUR|GBP|USD|JPY|AUD|NZD|CAD|CHF)\b|\b(gold|xauusd|dax|us30|nas100|us500)\b', re.I)


def regex_calls(p, sym_hint):
    t = p["text"]
    s, e, sl = RX_SIDE.search(t), RX_ENTRY.search(t), RX_SL.search(t)
    if not (s and e and sl):
        return []
    sm = RX_SYM.search(t)
    sym = (sm.group(1) + sm.group(2)).upper() if sm and sm.group(1) else ((sm.group(3) or "").upper() if sm else sym_hint)
    sym = {"GOLD": "XAUUSD"}.get(sym, sym)
    lim = re.search(r'\b(limit|pending|stop order|buy stop|sell stop)\b', t, re.I)
    stop_order = re.search(r'\b(buy stop|sell stop)\b', t, re.I)
    tp = RX_TP.search(t)
    return [{"sym": sym, "side": "LONG" if s.group(1).lower() in ("buy", "long") else "SHORT",
             "type": "stop" if stop_order else ("limit" if lim else "market"), "entry": float(e.group(1)),
             "stop": float(sl.group(1)), "tp": float(tp.group(1)) if tp else 0, "quote": t[max(0, e.start() - 80):e.end() + 80]}]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thread", required=True, help="帖子号（data/ff/ 下的目录名）")
    ap.add_argument("--dir", default="data/ff")
    ap.add_argument("--author", help="只要这个作者的帖子；默认=第 1 页第 1 个帖子的作者（楼主）")
    ap.add_argument("--sym", default="", help="日志主要品种，帖子里没写品种时用它")
    ap.add_argument("--tz-hours", type=float, default=0.0, help="页面时间比 UTC 快几小时（FF 设成 GMT 就是 0）")
    ap.add_argument("--inspect", action="store_true")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--backend")
    a = ap.parse_args()
    d = kit_path(os.path.join(a.dir, a.thread))
    posts = parse_pages(d, a.tz_hours)
    if not posts:
        sys.exit("一个帖子都没切出来：用 --inspect 看页面，改 POST_MARK 正则。")
    starter = a.author or posts[0]["author"]
    mine = [p for p in posts if p["author"] == starter]
    if a.inspect:
        print(f"切出 {len(posts)} 个帖子，楼主 {starter} 的 {len(mine)} 个；无时间的 {sum(1 for p in posts if not p['ts'])} 个")
        for p in posts[:3]:
            print(json.dumps({**p, "text": p["text"][:600]}, ensure_ascii=False, indent=1))
        return
    with open(os.path.join(d, "posts.jsonl"), "w", encoding="utf-8") as f:
        for p in mine:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    cand = [p for p in mine if p["ts"] and CALL_HINT.search(p["text"]) and len(NUM.findall(p["text"])) >= 2]
    print(f"楼主 {starter}：{len(mine)} 帖，其中像喊单的 {len(cand)} 帖")
    cfg = load_config()
    be = a.backend or cfg["default_backend"]
    n = 0
    with open(os.path.join(d, "calls.jsonl"), "w", encoding="utf-8") as f:
        for i, p in enumerate(cand):
            if a.no_llm:
                calls = regex_calls(p, a.sym)
            else:
                t = datetime.fromtimestamp(p["ts"], timezone.utc).strftime("%Y-%m-%d %H:%M")
                txt = llm.call(cfg, be, LLM_SYS, LLM_USER.format(author=starter, t=t, sym_hint=a.sym or "未知", text=p["text"][:3000]))
                calls = (extract_json(txt, "calls") or {}).get("calls", []) if txt else []
            for c in calls:
                try:
                    row = {"thread": a.thread, "post_id": p["post_id"], "author": starter, "ts": p["ts"],
                           "sym": str(c.get("sym") or a.sym).upper().replace("/", ""), "side": str(c["side"]).upper(),
                           "type": str(c.get("type", "limit")).lower(), "entry": float(c["entry"]), "stop": float(c["stop"]),
                           "tp": float(c.get("tp") or 0), "quote": str(c.get("quote", ""))[:300]}
                except (KeyError, TypeError, ValueError):
                    continue
                f.write(json.dumps(row, ensure_ascii=False) + "\n"); n += 1
            if (i + 1) % 25 == 0:
                print(f"  {i + 1}/{len(cand)}，已抽 {n} 单", flush=True)
    print(f"写入 {n} 单 → {os.path.join(d, 'calls.jsonl')}。下一步：python3 ff_check.py --thread {a.thread} --tz-scan")


if __name__ == "__main__":
    main()
