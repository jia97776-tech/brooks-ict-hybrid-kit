#!/usr/bin/env python3
"""抓 Forex Factory 帖子的全部页面（本地跑；FF 有 Cloudflare，需要开着浏览器窗口过一次验证）。

  pip install playwright && python3 -m playwright install chromium
  python3 ff_fetch.py https://www.forexfactory.com/thread/594513-trade-and-price-action-journal [更多帖子链接...]

- 用持久化浏览器配置（data/ff/browser_profile）：第一次弹窗里手动过验证、登录 FF，并在 FF 账号设置里把时区设成 GMT/UTC。
  之后再跑不用重复。
- 每页存成 data/ff/<帖子号>/page_0001.html；已存在的页跳过（断点续跑）。默认每页间隔 4–7 秒，别调快。
"""
import argparse, os, random, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dk.common import kit_path


def wait_clear(page, limit=180):
    t0 = time.time()
    while "Just a moment" in page.title() or "Attention Required" in page.title():
        if time.time() - t0 > limit:
            raise RuntimeError("Cloudflare 验证没过：请在弹出的浏览器窗口里手动点一下")
        time.sleep(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--out", default="data/ff")
    ap.add_argument("--delay", type=float, default=4.0)
    ap.add_argument("--max-pages", type=int, default=0)
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright

    out = kit_path(a.out)
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(os.path.join(out, "browser_profile"), headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for url in a.urls:
            m = re.search(r"/thread/(\d+)", url)
            if not m:
                print(f"跳过（不是帖子链接）：{url}"); continue
            tid, base = m.group(1), url.split("?")[0].split("#")[0]
            d = os.path.join(out, tid)
            os.makedirs(d, exist_ok=True)
            page.goto(base, wait_until="domcontentloaded", timeout=120000)
            wait_clear(page)
            html = page.content()
            last = max([int(x) for x in re.findall(r"[?&]page=(\d+)", html)] + [1])
            if a.max_pages:
                last = min(last, a.max_pages)
            print(f"帖子 {tid}：共 {last} 页 → {d}")
            open(os.path.join(d, "url.txt"), "w").write(base)
            for p in range(1, last + 1):
                fn = os.path.join(d, f"page_{p:04d}.html")
                if os.path.exists(fn) and os.path.getsize(fn) > 5000:
                    continue
                page.goto(f"{base}?page={p}", wait_until="domcontentloaded", timeout=120000)
                wait_clear(page)
                open(fn, "w", encoding="utf-8").write(page.content())
                if p % 20 == 0 or p == last:
                    print(f"  {p}/{last}", flush=True)
                time.sleep(a.delay + random.random() * 3)
        ctx.close()


if __name__ == "__main__":
    main()
