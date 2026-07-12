#!/usr/bin/env python3
"""Polymarket BTC 5m Up/Down — PAPER bot (default: no real orders).

Strategies
  1) tail      — near window end, if favored side has takeable ask in
                 [min_price, max_price], paper-buy at best_ask (HIT_ASK only).
                 JOIN_BID is logged but NOT filled (honest: you rarely get queue).
  2) dump_hedge — early in window, if one side dumps hard, paper Leg1;
                 later if leg1 + opposite_ask <= sum_target, paper Leg2 lock.

Settlement: when window closes, winner mid≈1 / loser≈0 → paper PnL.

Usage:
  cd /path/to/trading_scanner_service
  python3 scripts/polymarket_btc5m_paper_bot.py
  python3 scripts/polymarket_btc5m_paper_bot.py --strategy both --shares 5
  python3 scripts/polymarket_btc5m_paper_bot.py --state /tmp/pm_bot_state.json \\
      --log /tmp/pm_bot.jsonl

Live trading is intentionally OFF. To go live later you need:
  - py-clob-client + POLYMARKET private key / API creds in env (never chat)
  - separate wallet, tiny bankroll
  - this book SEPARATE from desk BTC/ETH structure

Resolution = Chainlink BTC/USD stream.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
UA = "desk-pm-paper-bot/0.2 (+dry-run; no live orders)"
WINDOW = 300


# ---------------------------------------------------------------------------
# HTTP / market
# ---------------------------------------------------------------------------

def _http_get(url: str, timeout: float = 12.0) -> Any:
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept": "application/json"}
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
    sec_elapsed: float
    closed: bool
    up: SideBook
    down: SideBook
    ts: float


def window_start_now(now: Optional[float] = None) -> int:
    t = int(now if now is not None else time.time())
    return (t // WINDOW) * WINDOW


def fetch_event(slug: str) -> Optional[dict]:
    try:
        data = _http_get(f"{GAMMA}/events?slug={slug}")
    except urllib.error.HTTPError as e:
        if e.code in (404, 403):
            return None
        raise
    if not data:
        return None
    return data[0] if isinstance(data, list) else data


def fetch_book(token_id: str) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
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
            bb, bbs, ba, bas = fetch_book(str(tokens[i]))
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
        sec_elapsed=now_f - start_ts,
        closed=bool(ev.get("closed")),
        up=sides[0],
        down=sides[1],
        ts=now_f,
    )


# ---------------------------------------------------------------------------
# Paper state
# ---------------------------------------------------------------------------

@dataclass
class PaperFill:
    id: str
    slug: str
    strategy: str
    side: str
    token_id: str
    price: float
    shares: float
    cost: float
    ts: float
    mode: str  # HIT_ASK | HEDGE_LEG1 | HEDGE_LEG2
    status: str = "open"  # open | settled
    settle_px: Optional[float] = None
    pnl: Optional[float] = None


@dataclass
class HedgeOpen:
    slug: str
    leg1_side: str
    leg1_price: float
    leg1_shares: float
    leg1_token: str
    leg1_ts: float
    leg2_done: bool = False


@dataclass
class BotState:
    bankroll: float = 50.0
    cash: float = 50.0
    fills: list[dict] = field(default_factory=list)
    hedges: list[dict] = field(default_factory=list)
    # per-slug flags
    tail_done: dict = field(default_factory=dict)  # slug -> bool
    stats: dict = field(default_factory=lambda: {
        "windows_seen": 0,
        "tail_signals_join_bid": 0,
        "tail_fills": 0,
        "hedge_leg1": 0,
        "hedge_leg2": 0,
        "settled": 0,
        "wins": 0,
        "losses": 0,
        "realized_pnl": 0.0,
    })

    def save(self, path: str) -> None:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    @classmethod
    def load(cls, path: str) -> "BotState":
        if not path or not os.path.exists(path):
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        st = cls(
            bankroll=float(raw.get("bankroll", 50)),
            cash=float(raw.get("cash", raw.get("bankroll", 50))),
            fills=list(raw.get("fills") or []),
            hedges=list(raw.get("hedges") or []),
            tail_done=dict(raw.get("tail_done") or {}),
            stats=dict(raw.get("stats") or {}),
        )
        return st


def append_jsonl(path: str, row: dict) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def utc_hhmmss(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S")


# ---------------------------------------------------------------------------
# Strategies (paper)
# ---------------------------------------------------------------------------

def try_tail_paper(
    snap: WindowSnap,
    st: BotState,
    *,
    min_price: float,
    max_price: float,
    max_sec_left: float,
    min_ask_size: float,
    shares: float,
    log_path: str,
) -> Optional[dict]:
    if snap.closed or snap.sec_left < 0 or snap.sec_left > max_sec_left:
        return None
    if st.tail_done.get(snap.slug):
        return None

    # favored by ref
    up_r = snap.up.ref_price if snap.up.ref_price is not None else -1
    dn_r = snap.down.ref_price if snap.down.ref_price is not None else -1
    fav = snap.up if up_r >= dn_r else snap.down

    # JOIN_BID only → log, no fill
    if fav.best_ask is None or not (min_price <= fav.best_ask <= max_price):
        ref = fav.ref_price
        if ref is not None and min_price <= ref <= max_price:
            st.stats["tail_signals_join_bid"] = st.stats.get("tail_signals_join_bid", 0) + 1
            st.tail_done[snap.slug] = True  # one log per window
            row = {
                "event": "TAIL_SKIP_JOIN_BID",
                "slug": snap.slug,
                "side": fav.name,
                "ref": ref,
                "bid": fav.best_bid,
                "ask": fav.best_ask,
                "sec_left": round(snap.sec_left, 1),
            }
            append_jsonl(log_path, row)
            print(f"  skip JOIN_BID {fav.name} ref={ref} (no takeable ask)")
            return row
        return None

    ask = fav.best_ask
    ask_sz = fav.best_ask_size or 0.0
    if ask_sz < min_ask_size:
        # too thin — skip fill honesty
        st.tail_done[snap.slug] = True
        row = {
            "event": "TAIL_SKIP_THIN",
            "slug": snap.slug,
            "side": fav.name,
            "ask": ask,
            "ask_sz": ask_sz,
            "sec_left": round(snap.sec_left, 1),
        }
        append_jsonl(log_path, row)
        print(f"  skip THIN {fav.name} ask={ask} sz={ask_sz:.1f}")
        return row

    cost = ask * shares
    if cost > st.cash:
        print(f"  skip NO_CASH need={cost:.2f} cash={st.cash:.2f}")
        return None

    # paper fill
    fid = f"tail-{snap.slug}-{int(snap.ts)}"
    fill = PaperFill(
        id=fid,
        slug=snap.slug,
        strategy="tail",
        side=fav.name,
        token_id=fav.token_id,
        price=ask,
        shares=shares,
        cost=cost,
        ts=snap.ts,
        mode="HIT_ASK",
    )
    st.cash -= cost
    st.fills.append(asdict(fill))
    st.tail_done[snap.slug] = True
    st.stats["tail_fills"] = st.stats.get("tail_fills", 0) + 1
    row = {"event": "PAPER_FILL", **asdict(fill), "cash": st.cash}
    append_jsonl(log_path, row)
    print(
        f"  FILL tail HIT_ASK {fav.name} @{ask:.3f} x{shares} "
        f"cost={cost:.2f} cash={st.cash:.2f} | {snap.sec_left:.0f}s left"
    )
    return row


def try_dump_hedge_paper(
    snap: WindowSnap,
    st: BotState,
    *,
    dump_move: float,
    dump_window_sec: float,
    sum_target: float,
    shares: float,
    log_path: str,
    prev_mids: dict,
) -> Optional[dict]:
    """Simple dump+hedge paper.

    Leg1: within first dump_window_sec, if one side's mid drops >= dump_move
          from recent ref (or from ~0.5), buy that side at best_ask.
    Leg2: opposite best_ask + leg1_price <= sum_target → buy opposite, lock.
    """
    # settle open hedge for this slug
    open_h = None
    for h in st.hedges:
        if h.get("slug") == snap.slug and not h.get("leg2_done"):
            open_h = h
            break

    # Leg2
    if open_h is not None:
        leg1_side = open_h["leg1_side"]
        opp = snap.down if leg1_side == "Up" else snap.up
        if opp.best_ask is not None:
            total = open_h["leg1_price"] + opp.best_ask
            if total <= sum_target:
                cost = opp.best_ask * shares
                if cost <= st.cash:
                    fid = f"hedge2-{snap.slug}-{int(snap.ts)}"
                    fill = PaperFill(
                        id=fid,
                        slug=snap.slug,
                        strategy="dump_hedge",
                        side=opp.name,
                        token_id=opp.token_id,
                        price=opp.best_ask,
                        shares=shares,
                        cost=cost,
                        ts=snap.ts,
                        mode="HEDGE_LEG2",
                    )
                    st.cash -= cost
                    st.fills.append(asdict(fill))
                    open_h["leg2_done"] = True
                    st.stats["hedge_leg2"] = st.stats.get("hedge_leg2", 0) + 1
                    row = {
                        "event": "PAPER_FILL",
                        **asdict(fill),
                        "pair_sum": round(total, 4),
                        "cash": st.cash,
                    }
                    append_jsonl(log_path, row)
                    print(
                        f"  FILL hedge LEG2 {opp.name} @{opp.best_ask:.3f} "
                        f"sum={total:.3f} cash={st.cash:.2f}"
                    )
                    return row
        return None

    # Leg1 only early
    if snap.sec_elapsed > dump_window_sec or snap.closed:
        return None
    # already did leg1 this slug
    if any(h.get("slug") == snap.slug for h in st.hedges):
        return None

    for side in (snap.up, snap.down):
        if side.mid_price is None or side.best_ask is None:
            continue
        key = f"{snap.slug}:{side.name}"
        prev = prev_mids.get(key)
        # baseline: start-of-seen mid or 0.5
        base = prev if prev is not None else 0.50
        drop = base - side.mid_price
        # also require mid clearly beaten (not just noise)
        if drop >= dump_move and side.mid_price <= (0.50 - dump_move + 0.02):
            ask = side.best_ask
            cost = ask * shares
            if cost > st.cash:
                continue
            fid = f"hedge1-{snap.slug}-{int(snap.ts)}"
            fill = PaperFill(
                id=fid,
                slug=snap.slug,
                strategy="dump_hedge",
                side=side.name,
                token_id=side.token_id,
                price=ask,
                shares=shares,
                cost=cost,
                ts=snap.ts,
                mode="HEDGE_LEG1",
            )
            st.cash -= cost
            st.fills.append(asdict(fill))
            st.hedges.append(
                {
                    "slug": snap.slug,
                    "leg1_side": side.name,
                    "leg1_price": ask,
                    "leg1_shares": shares,
                    "leg1_token": side.token_id,
                    "leg1_ts": snap.ts,
                    "leg2_done": False,
                }
            )
            st.stats["hedge_leg1"] = st.stats.get("hedge_leg1", 0) + 1
            row = {
                "event": "PAPER_FILL",
                **asdict(fill),
                "dump_from": base,
                "drop": round(drop, 4),
                "cash": st.cash,
            }
            append_jsonl(log_path, row)
            print(
                f"  FILL hedge LEG1 {side.name} @{ask:.3f} "
                f"drop={drop:.3f} from {base:.3f} cash={st.cash:.2f}"
            )
            return row

    return None


def settle_fills(snap: WindowSnap, st: BotState, log_path: str) -> int:
    """When window closed (or mid 0/1), settle open fills for slug."""
    if not snap.closed and snap.sec_left > -5:
        # allow a few seconds after end
        if snap.sec_left > 0:
            return 0

    # winner: mid closer to 1
    up_m = snap.up.mid_price
    dn_m = snap.down.mid_price
    if up_m is None or dn_m is None:
        return 0
    # need decisive
    if max(up_m, dn_m) < 0.95 and not snap.closed:
        return 0

    winner = "Up" if up_m >= dn_m else "Down"
    n = 0
    for f in st.fills:
        if f.get("slug") != snap.slug or f.get("status") == "settled":
            continue
        settle_px = 1.0 if f["side"] == winner else 0.0
        pnl = (settle_px - f["price"]) * f["shares"]
        f["status"] = "settled"
        f["settle_px"] = settle_px
        f["pnl"] = round(pnl, 4)
        st.cash += settle_px * f["shares"]
        st.stats["settled"] = st.stats.get("settled", 0) + 1
        st.stats["realized_pnl"] = round(st.stats.get("realized_pnl", 0) + pnl, 4)
        if pnl >= 0:
            st.stats["wins"] = st.stats.get("wins", 0) + 1
        else:
            st.stats["losses"] = st.stats.get("losses", 0) + 1
        row = {
            "event": "SETTLE",
            "id": f["id"],
            "slug": snap.slug,
            "side": f["side"],
            "winner": winner,
            "entry": f["price"],
            "settle_px": settle_px,
            "shares": f["shares"],
            "pnl": f["pnl"],
            "cash": round(st.cash, 4),
        }
        append_jsonl(log_path, row)
        print(
            f"  SETTLE {f['side']} entry={f['price']:.3f} → {settle_px:.0f} "
            f"pnl={pnl:+.3f} cash={st.cash:.2f}"
        )
        n += 1
    return n


def print_status(snap: WindowSnap, st: BotState) -> None:
    print(
        f"[{utc_hhmmss(snap.ts)}Z] {snap.slug} | "
        f"{'CLOSED' if snap.closed else f'{snap.sec_left:.0f}s left'} | "
        f"cash={st.cash:.2f} pnl={st.stats.get('realized_pnl', 0):+.3f} "
        f"fills={st.stats.get('tail_fills', 0)}t/"
        f"{st.stats.get('hedge_leg1', 0)}h1/"
        f"{st.stats.get('hedge_leg2', 0)}h2"
    )
    u, d = snap.up, snap.down
    def fmt(s: SideBook) -> str:
        ask = f"{s.best_ask:.2f}x{s.best_ask_size:.0f}" if s.best_ask is not None else "-"
        bid = f"{s.best_bid:.2f}" if s.best_bid is not None else "-"
        mid = f"{s.mid_price:.3f}" if s.mid_price is not None else "-"
        return f"{s.name} mid={mid} bid={bid} ask={ask}"
    print(f"  {fmt(u)}")
    print(f"  {fmt(d)}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Polymarket BTC 5m PAPER bot")
    p.add_argument(
        "--strategy",
        choices=["tail", "dump_hedge", "both"],
        default="both",
        help="default both",
    )
    p.add_argument("--shares", type=float, default=5.0, help="shares per leg (min ~5)")
    p.add_argument("--bankroll", type=float, default=50.0)
    p.add_argument("--interval", type=float, default=1.5)
    p.add_argument("--once", action="store_true")
    # tail
    p.add_argument("--min-price", type=float, default=0.95)
    p.add_argument("--max-price", type=float, default=0.99)
    p.add_argument("--max-sec-left", type=float, default=45.0)
    p.add_argument("--min-ask-size", type=float, default=15.0)
    # dump hedge
    p.add_argument("--dump-move", type=float, default=0.12, help="mid drop for leg1")
    p.add_argument("--dump-window-sec", type=float, default=180.0, help="first N sec")
    p.add_argument("--sum-target", type=float, default=0.95, help="leg1+opp ask max")
    # io
    p.add_argument("--state", type=str, default="/tmp/pm_btc5m_paper_state.json")
    p.add_argument("--log", type=str, default="/tmp/pm_btc5m_paper.jsonl")
    p.add_argument(
        "--live",
        action="store_true",
        help="REFUSED unless PM_ALLOW_LIVE=1 and keys present (safety)",
    )
    args = p.parse_args(argv)

    if args.live:
        allow = os.environ.get("PM_ALLOW_LIVE") == "1"
        has_key = bool(os.environ.get("POLYMARKET_PRIVATE_KEY") or os.environ.get("PK"))
        if not (allow and has_key):
            print(
                "LIVE blocked. Paper only.\n"
                "To enable later: install py-clob-client, set POLYMARKET_PRIVATE_KEY, "
                "PM_ALLOW_LIVE=1, and extend this script. Never paste keys in chat.",
                file=sys.stderr,
            )
            return 2
        print("LIVE path not implemented in this build — refusing.", file=sys.stderr)
        return 2

    st = BotState.load(args.state)
    if not os.path.exists(args.state):
        st.bankroll = args.bankroll
        st.cash = args.bankroll

    print(
        "Polymarket BTC 5m PAPER bot\n"
        f"  strategy={args.strategy} shares={args.shares} cash={st.cash:.2f}\n"
        f"  tail: ask in [{args.min_price},{args.max_price}] sec≤{args.max_sec_left}\n"
        f"  hedge: dump≥{args.dump_move} in first {args.dump_window_sec:.0f}s; "
        f"sum≤{args.sum_target}\n"
        f"  state={args.state}\n"
        f"  log={args.log}\n"
        "  mode=DRY-RUN (no real orders) | SEPARATE from desk structure book\n"
    )

    prev_mids: dict[str, float] = {}
    seen_windows: set[int] = set()

    try:
        while True:
            start = window_start_now()
            # also settle previous window
            for ws in (start - WINDOW, start):
                try:
                    snap = snap_window(ws)
                except Exception as e:
                    print(f"ERR {ws}: {e}", file=sys.stderr)
                    continue
                if snap is None:
                    continue

                if snap.window_start not in seen_windows:
                    seen_windows.add(snap.window_start)
                    st.stats["windows_seen"] = st.stats.get("windows_seen", 0) + 1

                print_status(snap, st)

                # update mid memory for dump detect
                for side in (snap.up, snap.down):
                    if side.mid_price is not None:
                        key = f"{snap.slug}:{side.name}"
                        if key not in prev_mids:
                            prev_mids[key] = side.mid_price

                settle_fills(snap, st, args.log)

                if not snap.closed and snap.sec_left > 0:
                    if args.strategy in ("dump_hedge", "both"):
                        try_dump_hedge_paper(
                            snap,
                            st,
                            dump_move=args.dump_move,
                            dump_window_sec=args.dump_window_sec,
                            sum_target=args.sum_target,
                            shares=args.shares,
                            log_path=args.log,
                            prev_mids=prev_mids,
                        )
                    if args.strategy in ("tail", "both"):
                        try_tail_paper(
                            snap,
                            st,
                            min_price=args.min_price,
                            max_price=args.max_price,
                            max_sec_left=args.max_sec_left,
                            min_ask_size=args.min_ask_size,
                            shares=args.shares,
                            log_path=args.log,
                        )

                # refresh mid high-water for continuous dump
                for side in (snap.up, snap.down):
                    if side.mid_price is not None:
                        key = f"{snap.slug}:{side.name}"
                        # track recent peak for drop measure
                        prev_mids[key] = max(prev_mids.get(key, side.mid_price), side.mid_price)

                st.save(args.state)
                print()

            if args.once:
                print("stats:", json.dumps(st.stats, ensure_ascii=False))
                return 0

            time.sleep(max(0.4, args.interval))
    except KeyboardInterrupt:
        st.save(args.state)
        print("\nstopped. stats:", json.dumps(st.stats, ensure_ascii=False))
        print(f"cash={st.cash:.2f} realized_pnl={st.stats.get('realized_pnl', 0):+.3f}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
