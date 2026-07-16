"""improve_fill — optional confirm_bar subfield (scanner v2 §六) — 2026-07-14h.

Shallow limit inside the confirmation-bar range after market_ok, with a
market fallback fuse. Not an independent strategy; not the default path.

Contract (entry-ladder Tier 2 addendum):
1. Pre: confirm_bar non-null, market_ok=true, screen-on, entry TF (M1/M5).
2. limit_price = zone UPPER edge (not CE) — fill rate over improvement size.
3. fallback_bars of zone_tf without fill + market still ok → cancel limit, market.
4. Price past confirm trigger extreme → improve_fill void, chase rules apply.
5. Not default until journal ≥30; user opt-in only.
"""

from __future__ import annotations

from scanner_service.sources import Bar

ENTRY_TFS = frozenset({"M1", "M5"})
FALLBACK_BARS_DEFAULT = 3


def _r(price: float) -> float:
    if abs(price) >= 100:
        return round(price, 2)
    if abs(price) >= 1:
        return round(price, 5)
    return round(price, 8)


def _fvgs_in_range(
    bars: list[Bar], direction: str, clo: float, chi: float, lookback: int = 40
) -> list[tuple[str, float, float]]:
    """Recent un-invalidated FVGs that overlap confirm-bar [clo, chi]."""
    out: list[tuple[str, float, float]] = []
    if len(bars) < 5:
        return out
    start = max(2, len(bars) - lookback)
    for i in range(len(bars) - 1, start - 1, -1):
        if i < 2:
            break
        first, third = bars[i - 2], bars[i]
        if direction == "LONG" and first.high < third.low:
            flo, fhi = first.high, third.low
            if any(b.close < flo for b in bars[i + 1 :]):
                continue
        elif direction == "SHORT" and first.low > third.high:
            flo, fhi = third.high, first.low
            if any(b.close > fhi for b in bars[i + 1 :]):
                continue
        else:
            continue
        # overlap with confirm bar range
        if max(flo, clo) < min(fhi, chi):
            out.append((f"FVG@{i}", flo, fhi))
        if len(out) >= 3:
            break
    return out


def build_improve_fill(
    confirm_bar: dict | None,
    bars: list[Bar],
    direction: str,
    zone_tf: str | None = None,
    fallback_bars: int = FALLBACK_BARS_DEFAULT,
) -> dict | None:
    """Build improve_fill subfield or None when inapplicable."""
    if not confirm_bar:
        return None
    if not confirm_bar.get("market_ok"):
        return None
    tf = (zone_tf or confirm_bar.get("tf") or "").upper()
    if tf not in ENTRY_TFS:
        return None
    if confirm_bar.get("role") not in (None, "entry_confirm"):
        # map_confirm never gets improve_fill
        if confirm_bar.get("role") == "map_confirm":
            return None
    if direction not in ("LONG", "SHORT"):
        return None

    try:
        clo = float(confirm_bar["low"])
        chi = float(confirm_bar["high"])
        trigger = float(confirm_bar["trigger_price"])
    except (KeyError, TypeError, ValueError):
        return None
    if chi <= clo:
        return None

    fvgs = _fvgs_in_range(bars, direction, clo, chi)
    if not fvgs:
        return None

    _name, flo, fhi = fvgs[0]  # most recent overlap
    # Spec: 区上沿 — not CE (fill rate over improvement)
    limit_price = float(fhi)
    # Keep limit inside confirm range so it remains in the market window
    limit_price = min(max(limit_price, clo), chi)

    # Sanity vs trigger extreme: if limit is already past trigger, improve is moot
    if direction == "SHORT" and limit_price <= trigger:
        return None
    if direction == "LONG" and limit_price >= trigger:
        return None

    return {
        "zone_tf": tf,
        "zone": [_r(flo), _r(fhi)],
        "zone_source": f"{tf}_FVG",
        "limit_price": _r(limit_price),
        "fallback_bars": int(fallback_bars),
        "fallback": "market_if_still_ok",
        "default_path": False,
        "requires_user_opt_in": True,
        "void_if": "price_beyond_confirm_trigger_extreme",
        "journal_fill_enum": ["market", "improved", "improved_timeout_market"],
        "note": "optional shallow improve; fallback market if still ok; not default until n≥30",
    }


def attach_improve_fill(
    confirm_bar: dict | None,
    bars: list[Bar],
    direction: str,
    zone_tf: str | None = None,
) -> dict | None:
    """Return confirm_bar with improve_fill set (may be null)."""
    if confirm_bar is None:
        return None
    cb = dict(confirm_bar)
    cb["improve_fill"] = build_improve_fill(cb, bars, direction, zone_tf=zone_tf)
    return cb
