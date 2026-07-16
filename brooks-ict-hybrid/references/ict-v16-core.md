# ICT V16 Core

This file is distilled from the local `D:\ClaudeWork\TradingPlaybook\ICT_V16_Manual_Core.txt` and related playbook material.

## Core Stack

Read the chart as:

1. HTF bias
2. Named liquidity target
3. PDA zone
4. LTF confirmation
5. Risk geometry

## Stable Concepts

- `HTF bias`: higher-timeframe directional context
- `DOL`: draw on liquidity, meaning a named liquidity destination
- `PDA`: premium-discount array or entry zone
- `Sweep`: take liquidity above highs or below lows, then react
- `Displacement`: unusually forceful move showing urgency
- `FVG / IFVG`: fair value gap or inverse fair value gap
- `OB`: order block
- `Breaker`: failed order block that flips role
- `BPR`: balanced price range
- `SMT`: intermarket divergence or asymmetric confirmation
- `MSS` or `CISD`: lower-timeframe structural trigger (M1/M5 close = Tier 2 entry trigger; M15/H4 close = confirmation/management event — see `references/entry-ladder.md`)

## Mechanical Precision (SMC)

When a read needs exact definitions, use `references/smc-mechanical-definitions.md` (distilled from the `smartmoneyconcepts` library). It pins down FVG, swing, OB, liquidity, PDH/PDL, sessions, and retracement so the same term means the same thing every time. Key precision points:

- `FVG`: a 3-candle imbalance (prior high below later low for bullish, prior low above later high for bearish). A gap price has traded back into is mitigated and spent.
- `BOS` vs `CHoCH`: `BOS` is a continuation break in the existing structure direction; `CHoCH` is the first counter-trend break (early character change). Both count only on a **close** through the swing level, never a wick.
- `OB`: the last opposing candle before a close that takes out the prior swing; failed OB flips to `Breaker`.
- `Liquidity`: equal highs / lows within a small range = a draw; the trade is the sweep failure, not the approach.
- `Retracement`: below ~50% of the leg = discount (long side), above = premium (short side). Entering premium for a long or discount for a short is chasing.

These are mechanical definitions only. They feed the gates below; they never replace them.

## Working Rules

- No HTF bias: no trade clarity
- No named liquidity target: no trade clarity
- PDA without trigger: watch only
- Trigger without location: low quality
- Target space too small relative to invalidation: pass
- Structure not yet confirmed (no close through the level, latest swing still provisional): treat as potential, not fact

## Five-Gate Permission Model

Only rate a setup highly if all are clear:

1. HTF bias
2. Named DOL
3. PDA quality
4. LTF PA confirmation
5. Invalidation and target geometry

## Typical Use Cases

- Sweep of session high or low, then reclaim
- Return into FVG or OB after displacement
- Continuation after pullback failure in trend context
- Reversal from HTF PDA only after LTF structure confirms

## Practical Merge With Brooks

- ICT tells you where the market may be drawn.
- Brooks tells you whether the tape behavior supports that idea right now.
- If Brooks says overlap and trading range, be skeptical of a clean-looking ICT pattern.
- If Brooks says strong breakout and follow-through, continuation ICT logic can be upgraded.
