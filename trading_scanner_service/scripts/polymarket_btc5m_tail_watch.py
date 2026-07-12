#!/usr/bin/env python3
"""Polymarket BTC 5m Up/Down — tail-end (99¢) paper monitor.

Default is DRY-RUN only: poll Gamma + CLOB, log when one side is "almost decided"
near window end. No keys, no orders.

Usage:
  # paper / observe (default)
  python3 scripts/polymarket_btc5m_tail_watch.py
  python3 scripts/polymarket_btc5m_tail_watch.py --once
  python3 scripts/polymarket_btc5m_tail_watch.py --min-price 0.95 --max-sec-left 45

  # log to file
  python3 scripts/polymarket_btc5m_tail_watch.py --log /tmp/pm_btc5m_tail.jsonl

Live trading is intentionally NOT implemented here. Filling at 0.97–0.99 vs bots
is latency + inventory game; use py-clob-client + your own keys only after
paper stats look acceptable — and keep this book SEPARATE from desk structure.

Resolution = Chainlink BTC/USD stream, NOT Bitget/Binance last.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
UA = "desk-pm-tail-watch/0.1 (+local dry-run; no trading)"
WINDOW = 300  # 5 minutes


def _http_get(url: str, timeout: float = 12.0) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _parse_json_field(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (list, dict)):
        return val
    if isinstance(val, str):
        return json.loads(val)
    return val


@dataclass
class SideBook:
    name: str
    token_id: str
    mid_price: Optional[float]
    best_bid: Optional[float]
    best_bid_size: Optional[float]
    best_ask: Optional[float]
    best_ask_size: Optional[float]

    @property
    def ref_price(self) -> Optional[float]:
        """Best available reference: ask > mid > bid (for who is favored)."""
        if self.best_ask is not None:
            return self.best_ask
        if self.mid_price is not None:
            return self.mid_price
        return self.best_bid


@dataclass
class WindowSnap:
    slug: str
    title: str
    window_start: int
    end_ts: int
    sec_left: float
    closed: bool
    up: SideBook
    down: SideBook
    ts: float

    def leader(self) -> tuple[SideBook, SideBook]:
        """Return (favored side, underdog) by ref_price."""
        up_p = self.up.ref_price if self.up.ref_price is not None else -1.0
        dn_p = self.down.ref_price if self.down.ref_price is not None else -1.0
        if up_p >= dn_p:
            return self.up, self.down
        return self.down, self.up


def window_start_now(now: Optional[float] = None) -> int:
    t = int(now if now is not None else time.time())
    return (t // WINDOW) * WINDOW


def fetch_event(slug: str) -> Optional[dict]:
    try:
        data = _http_get(f"{GAMMA}/events?slug={slug}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    if not data:
        return None
    return data[0] if isinstance(data, list) else data


def fetch_book(token_id: str) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """Return best_bid, bid_sz, best_ask, ask_sz."""
    book = _http_get(f"{CLOB}/book?token_id={token_id}")
    bids = book.get("bids") or []
    asks = book.get("asks") or []
    best_bid = best_bid_sz = best_ask = best_ask_sz = None
    if bids:
        b = max(bids, key=lambda x: float(x["price"]))
        best_bid = float(b["price"])
        best_bid_sz = float(b.get("size") or 0)
    if asks:
        a = min(asks, key=lambda x: float(x["price"]))
        best_ask = float(a["price"])
        best_ask_sz = float(a.get("size") or 0)
    return best_bid, best_bid_sz, best_ask, best_ask_sz


def snap_window(start_ts: int, now: Optional[float] = None) -> Optional[WindowSnap]:
    now_f = time.time() if now is None else float(now)
    slug = f"btc-updown-5m-{start_ts}"
    ev = fetch_event(slug)
    if not ev:
        return None
    markets = ev.get("markets") or []
    if not markets:
        return None
    m = markets[0]
    outcomes = _parse_json_field(m.get("outcomes")) or ["Up", "Down"]
    prices = _parse_json_field(m.get("outcomePrices")) or []
    tokens = _parse_json_field(m.get("clobTokenIds")) or []
    if len(tokens) < 2:
        return None

    end_raw = ev.get("endDate") or m.get("endDate")
    if not end_raw:
        end_ts = start_ts + WINDOW
    else:
        end_ts = int(datetime.fromisoformat(end_raw.replace("Z", "+00:00")).timestamp())

    sides: list[SideBook] = []
    for i, name in enumerate(outcomes[:2]):
        mid = float(prices[i]) if i < len(prices) else None
        try:
            bb, bbs, ba, bas = fetch_book(tokens[i])
        except Exception:
            bb = bbs = ba = bas = None
        sides.append(
            SideBook(
                name=str(name),
                token_id=str(tokens[i]),
                mid_price=mid,
                best_bid=bb,
                best_bid_size=bbs,
                best_ask=ba,
                best_ask_size=bas,
            )
        )

    return WindowSnap(
        slug=slug,
        title=str(ev.get("title") or m.get("question") or slug),
        window_start=start_ts,
        end_ts=end_ts,
        sec_left=end_ts - now_f,
        closed=bool(ev.get("closed")),
        up=sides[0],
        down=sides[1],
        ts=now_f,
    )


def classify_tail(
    snap: WindowSnap,
    min_price: float,
    max_price: float,
    max_sec_left: float,
    min_ask_size: float,
) -> Optional[dict]:
    """If favored side is in [min_price, max_price] and time is short → paper signal.

    Modes:
      HIT_ASK  — can marketable-buy at best_ask (rare near true 99¢)
      JOIN_BID — no ask / ask too high; only resting bid makes sense (typical tail)
    """
    if snap.closed or snap.sec_left < 0:
        return None
    if snap.sec_left > max_sec_left:
        return None

    fav, dog = snap.leader()
    ref = fav.ref_price
    if ref is None:
        return None
    if ref < min_price or ref > max_price:
        return None

    if fav.best_ask is not None and min_price <= fav.best_ask <= max_price:
        mode = "HIT_ASK"
        px = fav.best_ask
        sz = fav.best_ask_size or 0.0
        thin = sz < min_ask_size
    else:
        # Tail reality: book is all bids at 0.97–0.99, asks gone → unfillable by take
        mode = "JOIN_BID"
        px = fav.best_bid if fav.best_bid is not None else ref
        if px < min_price or px > max_price:
            return None
        sz = fav.best_bid_size or 0.0
        thin = True  # queue competition; treat as thin for paper honesty

    edge_if_right = 1.0 - px
    return {
        "signal": "TAIL_CANDIDATE",
        "mode": mode,
        "side": fav.name,
        "price": round(px, 4),
        "best_bid": fav.best_bid,
        "best_ask": fav.best_ask,
        "size_at_level": sz,
        "thin_book": thin,
        "sec_left": round(snap.sec_left, 1),
        "underdog": dog.name,
        "underdog_ref": dog.ref_price,
        "paper_edge_if_correct": round(edge_if_right, 4),
        "fillable_now": mode == "HIT_ASK" and not thin,
        "note": (
            "HIT_ASK paper: would take liquidity"
            if mode == "HIT_ASK"
            else "JOIN_BID paper: no takeable ask — queue behind bots; often no fill"
        ),
    }


def fmt_side(s: SideBook) -> str:
    bid = f"{s.best_bid:.2f}x{s.best_bid_size:.0f}" if s.best_bid is not None else "-"
    ask = f"{s.best_ask:.2f}x{s.best_ask_size:.0f}" if s.best_ask is not None else "-"
    mid = f"{s.mid_price:.3f}" if s.mid_price is not None else "-"
    return f"{s.name} mid={mid} bid={bid} ask={ask}"


def print_snap(snap: WindowSnap, signal: Optional[dict]) -> None:
    utc = datetime.fromtimestamp(snap.ts, tz=timezone.utc).strftime("%H:%M:%S")
    status = "CLOSED" if snap.closed else f"{snap.sec_left:.0f}s left"
    print(f"[{utc}Z] {snap.slug} | {status}")
    print(f"  {fmt_side(snap.up)}")
    print(f"  {fmt_side(snap.down)}")
    if signal:
        fill = "fillable" if signal.get("fillable_now") else "maybe-no-fill"
        print(
            f"  >>> PAPER {signal['mode']} {signal['side']} @ {signal['price']} "
            f"| {signal['sec_left']}s | edge≈{signal['paper_edge_if_correct']} "
            f"| sz={signal['size_at_level']:.1f} | {fill}"
            + (" | THIN" if signal["thin_book"] else "")
        )
        print(f"      {signal['note']}")
    else:
        print("  (no tail signal)")
    print()


def append_jsonl(path: str, row: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Polymarket BTC 5m tail-end paper monitor")
    p.add_argument("--once", action="store_true", help="Single poll then exit")
    p.add_argument("--interval", type=float, default=2.0, help="Poll seconds (default 2)")
    p.add_argument(
        "--min-price",
        type=float,
        default=0.95,
        help="Min take price on favored side (default 0.95)",
    )
    p.add_argument(
        "--max-price",
        type=float,
        default=0.99,
        help="Max take price; above this edge too thin / often unfillable (default 0.99)",
    )
    p.add_argument(
        "--max-sec-left",
        type=float,
        default=45.0,
        help="Only signal when ≤ this many seconds remain (default 45)",
    )
    p.add_argument(
        "--min-ask-size",
        type=float,
        default=20.0,
        help="Warn thin if ask size below this (default 20 shares)",
    )
    p.add_argument("--log", type=str, default="", help="Append JSONL path")
    p.add_argument(
        "--also-next",
        action="store_true",
        help="Also print next window book (usually 50/50)",
    )
    args = p.parse_args(argv)

    print(
        "Polymarket BTC 5m tail watch — DRY-RUN (no orders)\n"
        f"  signal when favored ask in [{args.min_price}, {args.max_price}] "
        f"and sec_left ≤ {args.max_sec_left}\n"
        "  resolution = Chainlink BTC/USD stream\n"
        "  keep SEPARATE from desk structure book\n"
    )

    last_sig_key: Optional[str] = None
    try:
        while True:
            start = window_start_now()
            try:
                snap = snap_window(start)
            except Exception as e:
                print(f"ERR fetch: {e}", file=sys.stderr)
                if args.once:
                    return 1
                time.sleep(args.interval)
                continue

            if snap is None:
                # market may lag a few seconds at window open
                print(f"no event for window {start}, retry…")
            else:
                sig = classify_tail(
                    snap,
                    min_price=args.min_price,
                    max_price=args.max_price,
                    max_sec_left=args.max_sec_left,
                    min_ask_size=args.min_ask_size,
                )
                print_snap(snap, sig)
                if args.log:
                    row = {
                        "ts": snap.ts,
                        "slug": snap.slug,
                        "sec_left": snap.sec_left,
                        "closed": snap.closed,
                        "up": {
                            "mid": snap.up.mid_price,
                            "bid": snap.up.best_bid,
                            "ask": snap.up.best_ask,
                            "ask_sz": snap.up.best_ask_size,
                        },
                        "down": {
                            "mid": snap.down.mid_price,
                            "bid": snap.down.best_bid,
                            "ask": snap.down.best_ask,
                            "ask_sz": snap.down.best_ask_size,
                        },
                        "signal": sig,
                    }
                    append_jsonl(args.log, row)

                if sig:
                    key = f"{snap.slug}:{sig['mode']}:{sig['side']}:{sig['price']}"
                    if key != last_sig_key:
                        last_sig_key = key
                        print(
                            f"ALERT paper_tail {sig['mode']} {sig['side']} @{sig['price']} "
                            f"{sig['sec_left']}s fillable={sig.get('fillable_now')} {snap.slug}",
                            flush=True,
                        )

                if args.also_next:
                    try:
                        nxt = snap_window(start + WINDOW)
                        if nxt:
                            print("  next window:")
                            print_snap(nxt, None)
                    except Exception:
                        pass

            if args.once:
                return 0
            # near end, poll faster
            sleep_for = args.interval
            if snap is not None and 0 < snap.sec_left <= args.max_sec_left + 15:
                sleep_for = min(args.interval, 1.0)
            time.sleep(max(0.3, sleep_for))
    except KeyboardInterrupt:
        print("\nstopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
