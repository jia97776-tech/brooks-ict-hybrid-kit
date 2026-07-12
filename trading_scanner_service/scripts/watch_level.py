#!/usr/bin/env python3
"""Watch a price level via the local scanner service and alert on cross.

Replaces ad-hoc watch scripts. UTF-8 output, structural exit conditions,
and a hard max duration so a forgotten watcher never runs all night.

Usage:
  python3 watch_level.py SYMBOL --above 60200 --note "反抽压住就空"
  python3 watch_level.py SYMBOL --below 59835 --interval 5 --max-minutes 240
  python3 watch_level.py SYMBOL --above 60200 --below 59835 --webhook https://open.feishu.cn/open-apis/bot/v2/hook/xxx

Exits after the first trigger (an alert is a one-shot event, not a stream).
An alert means the level TRADED, not that any order filled.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8001"


def get_price(symbol: str) -> float:
    with urllib.request.urlopen(f"{BASE}/price/{symbol}", timeout=8) as resp:
        return float(json.load(resp)["price"])


def notify(webhook: str | None, text: str) -> None:
    print(text, flush=True)
    if not webhook:
        return
    payload = json.dumps({"msg_type": "text", "content": {"text": text}}).encode("utf-8")
    req = urllib.request.Request(webhook, data=payload, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=8).read()
    except Exception as exc:  # alert already printed; webhook failure must not kill the watcher
        print(f"[watch] webhook 推送失败: {exc}", file=sys.stderr, flush=True)


def check_cross(price: float, above: float | None, below: float | None) -> str | None:
    if above is not None and price >= above:
        return f"上破 {above}"
    if below is not None and price <= below:
        return f"下破 {below}"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="watch a price level and alert on cross")
    ap.add_argument("symbol")
    ap.add_argument("--above", type=float, default=None, help="alert when price >= level")
    ap.add_argument("--below", type=float, default=None, help="alert when price <= level")
    ap.add_argument("--interval", type=float, default=10.0, help="poll seconds (default 10)")
    ap.add_argument("--max-minutes", type=float, default=480.0, help="hard stop (default 8h)")
    ap.add_argument("--note", default="", help="text appended to the alert (e.g. the plan)")
    ap.add_argument("--webhook", default=None, help="feishu bot webhook url")
    args = ap.parse_args()

    if args.above is None and args.below is None:
        ap.error("need --above and/or --below")

    deadline = time.time() + args.max_minutes * 60
    sym = args.symbol.upper()
    start_price = get_price(sym)
    print(f"[watch] {sym} 现价 {start_price}，盯 above={args.above} below={args.below}，"
          f"每 {args.interval}s，最长 {args.max_minutes} 分钟", flush=True)

    while time.time() < deadline:
        try:
            price = get_price(sym)
        except Exception as exc:
            print(f"[watch] 取价失败，{args.interval}s 后重试: {exc}", file=sys.stderr, flush=True)
            time.sleep(args.interval)
            continue
        hit = check_cross(price, args.above, args.below)
        if hit:
            stamp = time.strftime("%H:%M:%S")
            text = f"⚡ {sym} {hit}，现价 {price}（{stamp}）。这是告警不是成交。{args.note}".strip()
            notify(args.webhook, text)
            return 0
        time.sleep(args.interval)

    notify(args.webhook, f"[watch] {sym} 盯盘超时结束（{args.max_minutes} 分钟未触发），已自动退出。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
