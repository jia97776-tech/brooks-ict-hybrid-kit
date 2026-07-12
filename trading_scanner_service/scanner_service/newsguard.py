"""Economic-calendar news guard.

Source: the free ForexFactory weekly JSON (no key, no scraping):
  https://nfs.faireconomy.media/ff_calendar_thisweek.json

A signal gets news_risk=True when a High-impact event for a related currency
sits within +-NEWS_WINDOW_MIN of now. The desk translates that as
`数据时段，等落地再动` — it is a frequency filter, not an edge claim.
"""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path

URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
CACHE = Path(__file__).resolve().parent.parent / "data" / "ff_calendar.json"
CACHE_TTL_S = 6 * 3600
NEWS_WINDOW_MIN = 30

FX_MAJORS = {"EUR", "GBP", "USD", "JPY", "AUD", "NZD", "CAD", "CHF", "CNY"}
USD_PROXIES = {"XAUUSD", "XAGUSD", "XTIUSD", "US500", "NAS100", "US30",
               "BTC", "ETH", "SOL", "DOGE"}


def symbol_currencies(symbol: str) -> set[str]:
    s = symbol.upper()
    if s in USD_PROXIES:
        return {"USD"}
    if len(s) == 6 and s[:3] in FX_MAJORS and s[3:] in FX_MAJORS:
        return {s[:3], s[3:]}
    return {"USD"}  # default: dollar events move almost everything liquid


def _fetch() -> list[dict]:
    req = urllib.request.Request(URL, headers={"User-Agent": "local-scanner-newsguard/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)


def load_events(now: int | None = None) -> list[dict]:
    """Cached weekly events as [{title, currency, impact, epoch}]."""
    now = now or int(time.time())
    if CACHE.exists():
        try:
            cached = json.loads(CACHE.read_text(encoding="utf-8"))
            if now - cached.get("fetched_at", 0) < CACHE_TTL_S:
                return cached["events"]
        except (json.JSONDecodeError, KeyError):
            pass
    try:
        raw = _fetch()
    except Exception:
        # network failure: fall back to stale cache rather than dropping the guard
        if CACHE.exists():
            try:
                return json.loads(CACHE.read_text(encoding="utf-8"))["events"]
            except (json.JSONDecodeError, KeyError):
                return []
        return []
    events = []
    for ev in raw:
        try:
            epoch = int(datetime.fromisoformat(ev["date"]).timestamp())
            events.append({"title": ev.get("title", ""), "currency": ev.get("country", ""),
                           "impact": ev.get("impact", ""), "epoch": epoch})
        except (KeyError, ValueError):
            continue
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps({"fetched_at": now, "events": events}, ensure_ascii=False),
                     encoding="utf-8")
    return events


def news_risk(symbol: str, now: int | None = None,
              events: list[dict] | None = None,
              window_min: int = NEWS_WINDOW_MIN) -> dict | None:
    """Nearest in-window High-impact event for the symbol, or None."""
    now = now or int(time.time())
    events = load_events(now) if events is None else events
    currencies = symbol_currencies(symbol)
    window = window_min * 60
    hits = [ev for ev in events
            if ev.get("impact") == "High"
            and ev.get("currency") in currencies
            and abs(ev["epoch"] - now) <= window]
    if not hits:
        return None
    ev = min(hits, key=lambda e: abs(e["epoch"] - now))
    return {"title": ev["title"], "currency": ev["currency"],
            "minutes": round((ev["epoch"] - now) / 60)}


if __name__ == "__main__":
    evs = load_events()
    upcoming = [e for e in evs if e["impact"] == "High" and e["epoch"] > time.time()][:8]
    print(f"events cached: {len(evs)}, next high-impact:")
    for e in upcoming:
        print(f"  {time.strftime('%m-%d %H:%M', time.gmtime(e['epoch']))} UTC "
              f"{e['currency']:4} {e['title']}")
