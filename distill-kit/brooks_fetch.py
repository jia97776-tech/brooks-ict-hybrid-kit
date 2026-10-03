#!/usr/bin/env python3
"""抓 Brooks Trading Course 免费的每日 E-mini（ES）Trading Update，拆出「盘前 / 今日预期」部分。纯标准库。

  python3 brooks_fetch.py                         # 默认抓最近 365 天（翻存档页直到早于 --since）
  python3 brooks_fetch.py --since 2025-10-02      # 指定起点
  python3 brooks_fetch.py --parse-only            # 不联网，只用已缓存的 HTML 重新解析（改了解析规则后用）

产出（都在 data/brooks/ 下，data/ 已被 gitignore）：
  index.jsonl    存档页里列出的全部文章（含 BTC / EURUSD / 原油等非 ES 的），只记链接、标题、品种、日期
  html/<slug>.html  ES 报告原始 HTML 缓存（已存在就跳过，断点续跑）
  reports.jsonl  每篇 ES 报告一行：发布时间、距 RTH 开盘几分钟、按标题切开的各节正文、premarket_text 等

premarket_text = 「daily chart」一节 + 「5-minute chart and what to expect today」一节，别的都不要：
  - 「Yesterday's E-mini setups」的箭头是收盘后画的；
  - 「Summary of today's ... price action」和收盘视频是收盘后写的。
注意：近年的报告是盘中写的（文中常见 "As of bar 45"），所以 last_bar_mentioned 也一并记下，盲测切图要用。
"""
import argparse, collections, html as H, json, os, random, re, sys, time, urllib.error, urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dk.common import kit_path

BASE = "https://www.brookstradingcourse.com"
LIST_URL = BASE + "/blog/analysis/market-update/"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
ET, PT = ZoneInfo("America/New_York"), ZoneInfo("America/Los_Angeles")
TODAY = date(2026, 10, 2)

ARTICLE = re.compile(r"<article\b(.*?)</article>", re.S)
HEADING = re.compile(r"<(h[1-4])\b[^>]*>(.*?)</\1>", re.S | re.I)
UPDATE_HDR = re.compile(r"Trading Update:\s*(?:[A-Za-z]+day,?\s+)?([A-Z][a-z]+\.?\s+\d{1,2},?\s+\d{4})")
BARS = re.compile(r"\bbars?\s+(\d{1,2}(?:\s*(?:,|and|to|through|-|–)\s*\d{1,2})*)", re.I)

# 按标题判断品种。先看标题，再看文章 tag。
MARKETS = [("ES", re.compile(r"\be-?mini\b|\bemini\b|s&p|sp500|\bES\b", re.I)),
           ("BTC", re.compile(r"bitcoin|\bbtc\b", re.I)),
           ("EURUSD", re.compile(r"eur\s*/?\s*usd|\beuro\b", re.I)),
           ("NQ", re.compile(r"nasdaq|\bnq\b", re.I)),
           ("CL", re.compile(r"crude|\boil\b", re.I)),
           ("GC", re.compile(r"\bgold\b", re.I)),
           ("YM", re.compile(r"\bdow\b", re.I))]
TAG_MARKET = {"sp-emini": "ES", "emini": "ES", "bitcoin": "BTC", "eurusd": "EURUSD", "forex": "EURUSD",
              "crude-oil": "CL", "nasdaq": "NQ", "gold": "GC"}

# 节标题 → 归类。顺序有意义：先排除收盘后写的节。
SECTION_KEYS = [("other_market", re.compile(r"eur\s*/?\s*usd|forex|bitcoin|crude|\bgold\b", re.I)),  # ES 报告里夹带的外汇等段落
                ("yesterday_setups", re.compile(r"yesterday|setups", re.I)),  # 含 "Friday's E-mini setups"
                ("summary", re.compile(r"summary of today|end of day|after the close|today.s s&p e-?mini chart", re.I)),
                ("weekly", re.compile(r"weekly|monthly|weekend", re.I)),
                ("postclose_5min", re.compile(r"what happened|tomorrow", re.I)),  # 收盘后写的「今天发生了什么 / 明天预期」格式
                ("what_to_expect", re.compile(r"what to expect|5[- ]minute|pre-?open|pre-?market", re.I)),
                ("daily_chart", re.compile(r"daily (?:chart|an\w*lysis)", re.I)),
                ("trading_room", re.compile(r"trading room|pacific time|charts use", re.I)),
                ("header", re.compile(r"trading update|market analysis|market overview", re.I))]
PREMARKET_KEYS = ("daily_chart", "what_to_expect")


# ---------- 网络 ----------

def get(url, delay, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
            with urllib.request.urlopen(req, timeout=60) as r:
                txt = r.read().decode("utf-8", "ignore")
            time.sleep(delay + random.random() * 0.5)
            return txt
        except urllib.error.HTTPError as ex:
            if ex.code == 404:
                return None
            err = f"HTTP {ex.code}"
        except Exception as ex:
            err = f"{type(ex).__name__}: {ex}"
        wait = 10 * (k + 1)
        print(f"  [{err}] {url}，{wait}s 后重试", flush=True)
        time.sleep(wait)
    raise RuntimeError(f"抓取失败：{url}")


# ---------- 解析 ----------

def text_of(h):
    h = re.sub(r"<(script|style|noscript)\b.*?</\1>", " ", h, flags=re.S | re.I)
    h = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>|</div>", "\n", h, flags=re.I)
    t = H.unescape(re.sub(r"<[^>]+>", " ", h)).replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", t)).strip()


def guess_market(title, tags=""):
    for m, rx in MARKETS:
        if rx.search(title):
            return m
    for t in re.findall(r"tag-([a-z0-9-]+)", tags):
        if t in TAG_MARKET:
            return TAG_MARKET[t]
    return "OTHER"


def parse_listing(page_html):
    out = []
    for m in ARTICLE.finditer(page_html):
        a = m.group(0)
        link = re.search(r'class="entry-title-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', a, re.S)
        tm = re.search(r'datetime="([^"]+)"', a)
        if not link:
            continue
        cls = re.search(r'<article\b[^>]*class="([^"]*)"', a)
        cls = cls.group(1) if cls else ""
        title = text_of(link.group(2))
        exc = text_of(re.search(r'<div class="entry-content".*?</div>', a, re.S).group(0)) if 'entry-content' in a else ""
        out.append({"url": link.group(1), "title": title, "date_published": tm.group(1) if tm else None,
                    "market": guess_market(title, cls), "kind": guess_kind(title, exc),
                    "tags": re.findall(r"tag-([a-z0-9-]+)", cls), "excerpt": exc[:200]})
    return out


def guess_kind(title, first_text):
    s = (title + " " + first_text[:200]).lower()
    if "trading update" in s:  # 每日报告第一行固定是 "Trading Update: <星期> <日期>"
        return "daily"
    if "weekend" in s or "weekly" in s or "market overview" in s or "monthly" in s:
        return "weekly"
    return "other"


def slug_of(url):
    return url.rstrip("/").split("/")[-1]


def sections_of(body_html):
    """按 h1–h4 切节。返回 [{heading, key, text, images}]（标题前的内容记作 _lead）。"""
    marks = [(m.start(), m.end(), text_of(m.group(2))) for m in HEADING.finditer(body_html)]
    out = []
    if not marks or marks[0][0] > 0:
        lead = body_html[: marks[0][0] if marks else len(body_html)]
        if text_of(lead):
            out.append({"heading": "_lead", "key": "lead", "text": text_of(lead), "images": imgs(lead)})
    for i, (s, e, head) in enumerate(marks):
        chunk = body_html[e: marks[i + 1][0] if i + 1 < len(marks) else len(body_html)]
        key = next((k for k, rx in SECTION_KEYS if rx.search(head)), "other")
        out.append({"heading": head, "key": key, "text": text_of(chunk), "images": imgs(chunk)})
    return out


def imgs(h):
    return [u for u in re.findall(r'<img[^>]+src="([^"]+)"', h) if "/uploads/" in u][:4]


PRIOR_DAY = re.compile(r"yesterday|monday|tuesday|wednesday|thursday|friday|prior day|previous day|last week|"
                       r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? \d", re.I)
AS_OF = re.compile(r"\bas of bar (\d{1,2})\b", re.I)


def last_bar(text):
    """今日预期一节里「今天」最后一根 5 分钟 K 线编号。有 "As of bar N" 就用它；
    否则取所有句子里的最大编号，但整句跳过提到昨天 / 上周五 / 某月某日的句子（那些编号是前一天的）。"""
    asof = [int(x) for x in AS_OF.findall(text)]
    if asof:
        return max(asof)
    nums = []
    for sent in re.split(r"(?<=[.!?])\s+|\n", text):
        if PRIOR_DAY.search(sent):
            continue
        for m in BARS.finditer(sent):
            nums += [int(x) for x in re.findall(r"\d+", m.group(1))]
    nums = [n for n in nums if 1 <= n <= 81]  # 5 分钟 RTH 一天 81 根
    return max(nums) if nums else None


def parse_report(url, page_html):
    jd = lambda k: (re.search(rf'"{k}"\s*:\s*"([^"]+)"', page_html) or [None, None])[1]
    pub_s, mod_s = jd("datePublished"), jd("dateModified")
    if not pub_s:
        m = re.search(r'article:published_time"\s+content="([^"]+)"', page_html)
        pub_s = m.group(1) if m else None
    if not mod_s:
        m = re.search(r'article:modified_time"\s+content="([^"]+)"', page_html)
        mod_s = m.group(1) if m else None
    title = re.search(r'<h1[^>]*class="entry-title"[^>]*>(.*?)</h1>', page_html, re.S) or \
        re.search(r"<title>(.*?)</title>", page_html, re.S)
    title = re.sub(r"\s*\|\s*Brooks Trading Course\s*$", "", text_of(title.group(1))) if title else ""
    i = page_html.find('class="entry-content"')
    j = page_html.find("</article>", i)
    if i < 0:
        return None
    body = page_html[page_html.find(">", i) + 1: j if j > 0 else len(page_html)]
    body = re.split(r'<footer class="entry-footer"', body)[0]
    secs = sections_of(body)
    cls = re.search(r'<article\b[^>]*class="([^"]*)"', page_html)
    author = re.search(r'class="entry-author-name"[^>]*>([^<]+)<', page_html)

    pub = datetime.fromisoformat(pub_s) if pub_s else None
    mod = datetime.fromisoformat(mod_s) if mod_s else None
    hdr = next((UPDATE_HDR.search(s["heading"]) for s in secs if UPDATE_HDR.search(s["heading"])), None)
    tdate, tsrc = None, "header" if hdr else "published_pt"
    if hdr:
        for fmt in ("%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b. %d, %Y"):
            try:
                tdate = datetime.strptime(hdr.group(1), fmt).date(); break
            except ValueError:
                pass
        wd = re.search(r"Trading Update:\s*([A-Za-z]+day)", hdr.group(0))
        if tdate and wd and pub and wd.group(1).lower() != tdate.strftime("%A").lower():
            # 标题日期笔误（如 "Tuesday May 27" 实为 5 月 26 日）：星期几对不上就用发布日（太平洋时间）
            tdate, tsrc = pub.astimezone(PT).date(), "published_pt(header_weekday_mismatch)"
    if tdate is None and pub:
        tdate = pub.astimezone(PT).date()
    rth_open = datetime(tdate.year, tdate.month, tdate.day, 9, 30, tzinfo=ET) if tdate else None

    pre = [s for s in secs if s["key"] in PREMARKET_KEYS]
    wte = [s for s in secs if s["key"] == "what_to_expect"]
    premarket_text = "\n\n".join(f"## {s['heading']}\n{s['text']}" for s in pre)
    lb = last_bar(" ".join(s["text"] for s in wte))
    lb_time = (rth_open + timedelta(minutes=5 * lb)).astimezone(timezone.utc) if (lb and rth_open) else None
    pub_utc = pub.astimezone(timezone.utc) if pub else None
    cutoff = max([t for t in (pub_utc, lb_time) if t is not None], default=None)
    first_text = " ".join(s["heading"] for s in secs if s["key"] == "header")
    return {
        "url": url, "slug": slug_of(url), "title": title,
        "market": guess_market(title, cls.group(1) if cls else ""), "kind": guess_kind(title, first_text),
        "author": author.group(1).strip() if author else None,
        "date_published": pub_s, "date_modified": mod_s,
        "date_published_utc": pub.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if pub else None,
        "trading_date": tdate.isoformat() if tdate else None,
        "trading_date_src": tsrc,
        "rth_open_utc": rth_open.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if rth_open else None,
        "publish_delay_min": round((pub - rth_open).total_seconds() / 60, 1) if (pub and rth_open) else None,
        "modified_after_publish_hours": round((mod - pub).total_seconds() / 3600, 2) if (pub and mod) else None,
        "has_daily_chart": any(s["key"] == "daily_chart" for s in secs),
        "has_what_to_expect": bool(wte),
        "has_premarket": bool(wte) and bool(premarket_text.strip()),
        "last_bar_mentioned": lb,
        "as_of_bar": max([int(x) for x in AS_OF.findall(" ".join(s["text"] for s in wte))], default=None),
        "last_bar_close_utc": lb_time.strftime("%Y-%m-%dT%H:%M:%SZ") if lb_time else None,
        # 信息截止 = 发布时刻和文中最后一根 K 线收盘取较晚者；整点/整秒的发布时间多是排程占位，不可信
        "info_cutoff_utc": cutoff.strftime("%Y-%m-%dT%H:%M:%SZ") if cutoff else None,
        "published_before_last_bar": bool(pub_utc and lb_time and pub_utc < lb_time - timedelta(minutes=15)),  # 容忍 15 分钟：常是边看当前 K 线边写
        "pub_time_round": bool(pub and pub.second == 0),
        "premarket_chars": len(premarket_text), "premarket_text": premarket_text,
        "section_headings": [f"{s['key']}: {s['heading']}" for s in secs],
        "sections": secs,
    }


# ---------- 统计 ----------

def q(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    lo = int(k)
    return xs[lo] + (xs[min(lo + 1, len(xs) - 1)] - xs[lo]) * (k - lo)


def summary(reps, index):
    print(f"\n存档索引 {len(index)} 篇，按品种/类型：" +
          "，".join(f"{k[0]}-{k[1]} {v}" for k, v in collections.Counter((r['market'], r['kind']) for r in index).most_common()))
    es = [r for r in reps if r["market"] == "ES" and r["kind"] == "daily"]
    print(f"ES 报告 {len(reps)} 篇（每日 {len(es)}，其它 {len(reps) - len(es)}）")
    if not es:
        return
    ds = sorted(r["trading_date"] for r in es)
    print(f"  交易日范围 {ds[0]} → {ds[-1]}；作者：" +
          "，".join(f"{k} {v}" for k, v in collections.Counter(r['author'] for r in es).most_common()))
    hp = sum(r["has_premarket"] for r in es)
    print(f"  有「what to expect today」一节 {hp}/{len(es)}（{100 * hp / len(es):.1f}%）；有 daily chart 一节 "
          f"{sum(r['has_daily_chart'] for r in es)}")
    d = [r["publish_delay_min"] for r in es if r["publish_delay_min"] is not None]
    print(f"  发布时间 − RTH 开盘(09:30 ET)，分钟：min {min(d):.0f}  p10 {q(d, .1):.0f}  p25 {q(d, .25):.0f}  "
          f"中位 {q(d, .5):.0f}  p75 {q(d, .75):.0f}  p90 {q(d, .9):.0f}  max {max(d):.0f}")
    print(f"  开盘前发布 {sum(x < 0 for x in d)}，开盘后 0–2h {sum(0 <= x < 120 for x in d)}，2–5h {sum(120 <= x < 300 for x in d)}，"
          f"≥5h {sum(x >= 300 for x in d)}")
    rd = [r for r in es if r["pub_time_round"]]
    pb = [r for r in es if r["published_before_last_bar"]]
    print(f"  发布时间是整秒（:00，多为排程占位）{len(rd)} 篇；发布时刻比文中最后一根 K 线收盘早 15 分钟以上 {len(pb)} 篇 → 这些的发布时间不可信")
    d2 = [r["publish_delay_min"] for r in es if r["publish_delay_min"] is not None and not r["pub_time_round"]
          and not r["published_before_last_bar"]]
    if d2:
        print(f"  去掉上述可疑的 {len(d2)} 篇：p10 {q(d2, .1):.0f}  中位 {q(d2, .5):.0f}  p90 {q(d2, .9):.0f}，开盘前发布 {sum(x < 0 for x in d2)}")
    m = [r["modified_after_publish_hours"] for r in es if r["modified_after_publish_hours"] is not None]
    print(f"  dateModified − datePublished：中位 {q(m, .5):.1f}h，>24h 的 {sum(x > 24 for x in m)}/{len(m)}"
          f"（{100 * sum(x > 24 for x in m) / len(m):.1f}%）")
    lb = [r["last_bar_mentioned"] for r in es if r["last_bar_mentioned"]]
    if lb:
        print(f"  今日预期一节提到的最后一根 5 分钟 K 线：有 {len(lb)}/{len(es)} 篇，中位 bar {q(lb, .5):.0f}，"
              f"p10 {q(lb, .1):.0f} / p90 {q(lb, .9):.0f}")
    c = [r["premarket_chars"] for r in es if r["has_premarket"]]
    if c:
        print(f"  premarket_text 长度（字符）：中位 {q(c, .5):.0f}，p10 {q(c, .1):.0f} / p90 {q(c, .9):.0f}")


# ---------- 主流程 ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=(TODAY - timedelta(days=365)).isoformat(), help="只要这天及以后发布的（默认 365 天前）")
    ap.add_argument("--out", default="data/brooks")
    ap.add_argument("--delay", type=float, default=1.5, help="每次请求间隔秒数（别调快）")
    ap.add_argument("--max-pages", type=int, default=80, help="存档最多翻几页（每页 10 篇）")
    ap.add_argument("--parse-only", action="store_true", help="不联网：用 index.jsonl 和已缓存的 HTML 重新解析")
    ap.add_argument("--all-markets", action="store_true", help="非 ES 的报告也下载解析（默认只记链接）")
    a = ap.parse_args()
    out = kit_path(a.out)
    hdir = os.path.join(out, "html")
    os.makedirs(hdir, exist_ok=True)
    since = date.fromisoformat(a.since)
    ipath = os.path.join(out, "index.jsonl")

    if a.parse_only:
        index = [json.loads(l) for l in open(ipath, encoding="utf-8") if l.strip()]
        for r in index:
            r["kind"] = guess_kind(r["title"], r.get("excerpt", ""))
    else:
        index, seen = [], set()
        for p in range(1, a.max_pages + 1):
            url = LIST_URL if p == 1 else f"{LIST_URL}page/{p}/"
            page = get(url, a.delay)
            if not page:
                break
            rows = parse_listing(page)
            new = [r for r in rows if r["url"] not in seen]
            for r in new:
                seen.add(r["url"])
            index += new
            ds = [r["date_published"][:10] for r in rows if r["date_published"]]
            print(f"存档第 {p} 页：{len(rows)} 篇，{min(ds) if ds else '?'} → {max(ds) if ds else '?'}", flush=True)
            if not rows or (ds and max(ds) < since.isoformat()):
                break
        index = [r for r in index if (r["date_published"] or "9")[:10] >= since.isoformat()]
        with open(ipath, "w", encoding="utf-8") as f:
            for r in index:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"索引 {len(index)} 篇 → {ipath}")

    want = [r for r in index if a.all_markets or r["market"] == "ES"]
    reps, miss = [], 0
    for k, r in enumerate(want):
        fn = os.path.join(hdir, slug_of(r["url"]) + ".html")
        if not (os.path.exists(fn) and os.path.getsize(fn) > 20000):
            if a.parse_only:
                miss += 1; continue
            page = get(r["url"], a.delay)
            if not page:
                print(f"  404：{r['url']}"); continue
            with open(fn, "w", encoding="utf-8") as f:
                f.write(page)
            if (k + 1) % 20 == 0:
                print(f"  报告 {k + 1}/{len(want)}", flush=True)
        rep = parse_report(r["url"], open(fn, encoding="utf-8").read())
        if rep:
            rep["html_path"] = os.path.relpath(fn, kit_path("."))
            reps.append(rep)
    reps.sort(key=lambda x: (x["trading_date"] or "", x["date_published"] or ""))
    rpath = os.path.join(out, "reports.jsonl")
    with open(rpath, "w", encoding="utf-8") as f:
        for rep in reps:
            f.write(json.dumps(rep, ensure_ascii=False) + "\n")
    if miss:
        print(f"（--parse-only：{miss} 篇没有缓存，跳过）")
    print(f"写入 {len(reps)} 篇 → {rpath}")
    summary(reps, index)


if __name__ == "__main__":
    main()
