"""One-off watcher for the XAUUSD POI retest (2026-07-13 Monday open). Auto-exits after 8h."""
import json
import sys
import time
import urllib.request

sys.path.insert(0, "/home/ubuntu/trading_scanner_service")
from scanner_service.push_ready import send_feishu

LEVELS = [
    ("XAUUSD", "below", 4068.5, "金跌破 4068.6 扫荡极值 —— 回收重测失败风险，看 M15 收盘定生死", True),
    ("XAUUSD", "above", 4076.0, "金从 POI 弹起站回 4076 上方 —— 二次入场序列可能在酝酿，可以叫桌面看触发", True),
    ("XAUUSD", "below", 4055.0, "金 4055 —— 重测彻底失败，多头剧本作废，别接", True),
]


def price(sym: str) -> float:
    with urllib.request.urlopen(f"http://127.0.0.1:8001/price/{sym}", timeout=8) as r:
        return float(json.load(r)["price"])


def main() -> None:
    fired = set()
    deadline = time.time() + 8 * 3600
    while time.time() < deadline:
        for i, (sym, direction, level, msg, once) in enumerate(LEVELS):
            if i in fired:
                continue
            try:
                p = price(sym)
            except Exception:
                continue
            hit = p <= level if direction == "below" else p >= level
            if hit:
                try:
                    send_feishu(f"[价位提醒] {msg}（{sym} 现价 {p}）")
                except Exception as exc:
                    print(f"send fail: {exc}", flush=True)
                print(f"fired: {msg} @ {p}", flush=True)
                if once:
                    fired.add(i)
        if len(fired) == len(LEVELS):
            break
        time.sleep(15)


if __name__ == "__main__":
    main()
