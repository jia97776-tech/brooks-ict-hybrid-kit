"""One-off watcher for the SOL 76.35 limit plan (2026-07-11). Auto-exits after 8h."""
import json
import sys
import time
import urllib.request
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))
from scanner_service.push_ready import send_feishu

LEVELS = [
    # (symbol, direction, level, message, once)
    ("BTC", "below", 63631.0, "BTC 扫昨低 63631 —— SOL 二次下杀窗口打开，注意 76.35 限价", True),
    ("SOL", "below", 76.45, "SOL 接近你的 76.35 限价（现价已到 76.45 下方），大概率要成交", True),
    ("SOL", "below", 76.05, "SOL 逼近 75.90 止损区 —— 成交了的话按票据执行，不挪损", True),
    ("BTC", "above", 64100.0, "BTC 收复 64100 上方 —— beta 风险解除，SOL 多头环境变好", True),
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
