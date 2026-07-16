# Session Trade Matrix

Use this file when a live decision depends on time of day, an opening window,
dead hours, London/New York overlap, Friday close, weekend availability, or a
news window. Session is context, never a standalone signal.

## Decision Order

1. Determine the instrument's actually tradable session from fresh timestamps.
2. Determine trade class: scalp, intraday, trend, or weekly.
3. Determine cycle state and location.
4. Use this matrix to allow, downgrade, shorten, or reject the trade type.
5. Require the normal PA/ICT trigger, usable stop, and target room.

Do not force an ICT killzone narrative onto bars that lack a real sweep,
reclaim, displacement, failed breakout, or second entry.

## Core Matrix

| Window | Instruments | Preferred work | Default execution | Target permission | Avoid |
| --- | --- | --- | --- | --- | --- |
| Asia / Tokyo | FX, XAU/XAG | Build session range; trade only a clean range edge, HTF POI reaction, or pre-priced deep limit | M5 confirmation for screen-on; deep structural limit when away | Near target by default; runner only with HTF alignment and real displacement | Midrange entries, weak M1 breakout chasing, index scalps |
| Pre-London | FX, XAU/XAG | Map Asia high/low and nearby HTF levels; prepare one conditional plan | Wait for London liquidity event unless a valid HTF limit was already planned | No upgrade merely because London is near | Anticipating a sweep before it prints |
| London open | FX, XAU/XAG | Asia high/low sweep failure, HTF-aligned breakout pullback, second entry after the first false move | M1/M5 event confirmation; first touch is not enough for a countertrend fade | Near target for counter-HTF; main target and runner only when HTF aligned | Blind first-touch fade, chasing the opening spike |
| London/NY overlap | FX, XAU/XAG | Highest-priority intraday window for displacement continuation or confirmed reversal | M1/M5 trigger with cost-aware stop; valid scalp may upgrade to intraday when HTF aligned | HTF-aligned trades may hold to session objective and runner; counter-HTF remains near-target only | Treating participation alone as edge |
| New York RTH open | US500, NAS100, US30 | Opening sweep V-reversal, failed break of prior-day high/low, second entry, catalyst-backed opening-range break | M1 for execution, M5 for context; distrust the first breakout without follow-through | First take nearby liquidity; upgrade only after opening structure resolves | Heavy size on first move, distant default targets |
| NY mid-session / dead hours | FX, metals, indexes | Manage open positions; trade range edge only when unusually clean | Prefer no new scalp; require stronger PA and better location for intraday | Shorten targets; no runner without renewed participation | Midrange entries, polishing marginal triggers |
| NY close / late session | Non-crypto intraday | Harvest, reduce, or exit; only manage an existing trend plan | No fresh trade that needs a long development window | Existing trade follows its written class; intraday objectives shorten | Starting a new slow thesis |
| 24h crypto active window | BTC, ETH, liquid perps | Use actual volatility, liquidity, funding/OI crowding, and cycle state; session opens are secondary context | M1/M5 only with real participation and clean structure | HTF alignment controls runner permission | Assuming London/NY clock time creates crypto edge |
| 24h crypto dead window | BTC, ETH, liquid perps | Wait, use deeper limits, or manage | Stronger PA evidence required; friction check mandatory | Near target unless activity expands | Thin-book scalp and breakout chase |

## Opening Rules

- The first opening breakout has high reversal risk even when the bar looks
  strong. Do not load heavily on it.
- For index RTH opens, a failed breakout of yesterday's high/low followed by a
  second entry is preferred to a first-touch fade.
- If the opening range is still immature, wait for more bars or follow-through.
- If no direction resolves after roughly the first 60-90 minutes, trade the
  established range edge or its confirmed breakout; stop inventing an opening
  narrative.
- Apply index opening statistics directly only to index RTH. London/NY opens
  for FX/metals are an analogy with lower confidence.

## Trade-Class Effects

- **Scalp:** only in high-participation windows and only from the whitelist in
  `trade-class-contract.md`. Dead-hour scalp is a pass.
- **Intraday:** session controls entry urgency and target length. HTF-aligned
  London/NY or RTH-open trades can hold farther; counter-HTF trades take near
  liquidity and leave.
- **Trend:** manage mainly from D1 closes. Intraday session noise cannot rewrite
  the trend stop, but news and weekend gap risk still matter.
- **Weekly:** session is irrelevant to the thesis. Use W1 closes and the written
  allocation plan.

## News, Friday, Weekend

- Scheduled high-impact event: no fresh market entry or breakout order during
  the 30 minutes before and after release. For 30-60 minutes after release,
  reject ordinary M5 triggers unless the event structure has settled.
- Sudden headline/geopolitical shock: pause fresh market and breakout entries;
  wait for the first completed M15 bar. Existing deep limits may stay unchanged
  or be cancelled, never moved toward price.
- Friday is tradable. For non-crypto, estimate whether an intraday target can
  complete before close and flatten all positions before the venue closes.
- Weekend: only live crypto data is actionable. Frozen Friday FX, metals, and
  index bars cannot produce a weekend entry plan.

## Output Use

Compress the session judgment into the plan instead of printing this matrix:

- `亚盘中段，没必要用 M1 追突破；等伦敦扫完一侧再判。`
- `伦敦开盘第一下是假突破高发区，等第二次入场，不摸顶。`
- `纽约 RTH 开盘扫低收回，可以做近端 V 反转；先拿近流动性。`
- `现在是死时段，这个形态合法但不够值钱，放过。`
- `周五还能做，但只按日内拿，闭盘前必须清掉。`
