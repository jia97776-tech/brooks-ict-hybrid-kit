"""limit_zone — deep structure pending limit arithmetic (scanner v2 §五) — 2026-07-14g.

Optional field on map candidates. Codes the Deep Limit Live Contract numbers:
zone / CE refine / SL / mgmt / target / invalidate.

Hard rule: requires_desk_review is ALWAYS true — never machine-direct hang.
Zone sources are deep structure only (sweep extreme, HTF/M15 FVG, OTE).
M1/M5 micro arrays are banned as zone_source.
"""

from __future__ import annotations

from scanner_service.confluence import find_active_fvgs, ote_band, _overlap
from scanner_service.sources import Bar
from scanner_service.structure import Sweep, _fmt_bar_time

SL_BUFFER_ATR = 0.25


def _r(price: float) -> float:
    if abs(price) >= 100:
        return round(price, 2)
    if abs(price) >= 1:
        return round(price, 5)
    return round(price, 8)


def _tf_fvg_label(tf: str, direction: str) -> str:
    side = "bull" if direction == "LONG" else "bear"
    return f"{tf}_FVG_{side}"


def build_limit_zone(
    *,
    direction: str,
    bars: list[Bar],
    sweep: Sweep,
    atr: float,
    dol: float | None,
    tf: str = "M15",
    htf_bias: str | None = None,
    counter_htf: bool = False,
    stale_data: bool = False,
    news_risk: bool = False,
    spread_pad: float = 0.0,
) -> dict | None:
    """Return limit_zone dict or None when preconditions fail.

    Preconditions (all required):
    - direction LONG/SHORT with completed sweep extreme
    - not counter_htf (and if htf_bias is directional it must match)
    - not stale_data / news_risk
    - price has left the zone (deep retest geometry — not instant-fill)
    """
    if direction not in ("LONG", "SHORT"):
        return None
    if counter_htf:
        return None
    if htf_bias in ("LONG", "SHORT") and htf_bias != direction:
        return None
    if stale_data or news_risk:
        return None
    if sweep is None or atr is None or atr <= 0:
        return None
    if not bars or sweep.extreme_index < 0 or sweep.extreme_index >= len(bars):
        return None

    zlo = min(float(sweep.swept_level), float(sweep.extreme))
    zhi = max(float(sweep.swept_level), float(sweep.extreme))
    sources = ["sweep_extreme"]

    # Optional deep-structure refinements (map TF only — never M1/M5)
    fvg_name = _tf_fvg_label(tf, direction)
    for _name, flo, fhi in find_active_fvgs(bars, direction, lookback=40):
        o = _overlap((zlo, zhi), (flo, fhi))
        if o is not None and (o[1] - o[0]) > 0:
            zlo, zhi = o
            if fvg_name not in sources:
                sources.append(fvg_name)
            break

    ote = ote_band(bars, direction)
    if ote is not None:
        o = _overlap((zlo, zhi), ote)
        if o is not None and (o[1] - o[0]) > 0:
            zlo, zhi = o
            if "OTE_618_79" not in sources:
                sources.append("OTE_618_79")

    if zhi <= zlo:
        return None

    price = float(bars[-1].close)
    # Deep limit geometry: price already left zone so limit waits for retest.
    if direction == "SHORT" and price >= zlo:
        return None
    if direction == "LONG" and price <= zhi:
        return None

    refine = (zlo + zhi) / 2.0  # CE(50%) preferred refine
    sl_anchor = float(sweep.extreme)
    buf = max(SL_BUFFER_ATR * float(atr), float(spread_pad or 0.0))
    if direction == "SHORT":
        sl = sl_anchor + buf
        risk = sl - refine
        mgmt = refine - risk if risk > 0 else None  # +1R partial line
    else:
        sl = sl_anchor - buf
        risk = refine - sl
        mgmt = refine + risk if risk > 0 else None

    if risk is None or risk <= 0:
        return None

    target = float(dol) if dol is not None else None
    # Invalidate: map-TF close through sl_anchor (wick alone does not count)
    if direction == "SHORT":
        invalidate = f"{tf} 收盘 > { _r(sl_anchor) }"
    else:
        invalidate = f"{tf} 收盘 < { _r(sl_anchor) }"

    return {
        "zone": [_r(zlo), _r(zhi)],
        "zone_source": " + ".join(sources),
        "refine": _r(refine),
        "sl_anchor": _r(sl_anchor),
        "sl_anchor_bar": _fmt_bar_time(bars[sweep.extreme_index].ts),
        "buffer": _r(buf),
        "buffer_calc": f"max(0.25*ATR={0.25 * atr:.5g}, spread_pad={spread_pad})",
        "sl": _r(sl),
        "mgmt": _r(mgmt) if mgmt is not None else None,
        "target": _r(target) if target is not None else None,
        "invalidate": invalidate,
        "valid_until": "session_end",
        "requires_desk_review": True,
        "never_auto_hang": True,
        "management_scheme_default": "+1R减",
        "note": "desk pipeline required before hang; not machine-direct",
    }
