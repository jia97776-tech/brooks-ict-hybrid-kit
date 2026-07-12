# OpenMobius ICT Case Memory Extract

Source: local clone of `https://github.com/MobiusQuant/OpenMobius-skill` at `work\OpenMobius-skill`.

Use this as an experience layer, not as a rulebook. Cases can remind the analyst what often happens in similar structures, but they cannot override current chart evidence, PA context, or the binary gates.

## What To Keep

Keep only these OpenMobius elements:

- Core ICT concept cards: `fair_value_gap`, `change_in_state_of_delivery`, `liquidity_sweep`, `order_block`, `breaker_block`, `balanced_price_range`, `premium_discount`, `optimal_trade_entry`, `accumulation_manipulation_distribution`, `a_ict_entry_checklist`, `smt_divergence`, and `killzone`.
- Knowledge retrieval pattern: when an ICT term is central to the user's question, first retrieve or recall the matching rule card, then fuse it into the PA decision chain. Do not answer ICT from vague memory when a rule card is available.
- Case memory patterns: recurring structure sequences, common failure modes, target selection, and invalidation clues.
- Term alias idea: map user synonyms such as `sweep`, `stop run`, `liquidity grab`, and `raid` into one concept family.
- Freshness principle: do not answer live market questions from memory when fresh data is required or available.

Do not keep:

- Full case database in context.
- Indicator-heavy cards unrelated to PA/ICT.
- Mandatory OpenMobius output headings.
- Mobius API dependency as a hard requirement for this skill.

## Core Concept Extract

### A+ ICT Entry Checklist

Use as a fused gate sequence:

1. Stop raid / liquidity sweep.
2. Structure shift or CISD.
3. Discount for longs, premium for shorts.
4. Valid PD array: FVG, OB, OTE, Breaker, BPR.
5. Solid risk-reward after entry/stop/target are known.

PA translation: this is not a standalone long/short signal. It becomes valid only when the PA environment allows the idea and a signal/entry bar confirms it.

### Liquidity Sweep

Keep:

- Sweep must occur at a real resting-liquidity area: prior swing, equal highs/lows, session high/low, previous day/week high/low.
- Higher-quality sweep closes back inside the prior range.
- After the sweep, require displacement, CISD, MSS, reclaim, or PA entry-bar confirmation.
- Stop usually belongs beyond the swept extreme.

PA translation: sweep = failed breakout or stop run. Do not enter on the sweep alone.

### Fair Value Gap

Keep:

- Three-candle imbalance: bullish gap when candle 1 high is below candle 3 low; bearish gap when candle 1 low is above candle 3 high.
- Middle candle should be displacement, not slow drift.
- Consequent encroachment / 50% midpoint is a reaction reference.
- FVG is stronger after sweep, MSS/CISD, or inside a higher-timeframe PD array.
- Close fully through the gap can invalidate or invert it.

PA translation: FVG = pullback location. It still needs signal-bar/entry-bar/follow-through evidence.

### CISD

Keep:

- Confirmed by a body close beyond the open/body boundary of an opposing candle series.
- Wick breach alone is not enough.
- Often follows a sweep/manipulation leg.
- The candle series closed beyond can become the retest zone / order-block area.

PA translation: CISD = trigger candidate. It must still define invalidation and target space. On M1/M5 it can be a Tier 2 entry trigger; on M15/H4 it is a confirmation/management event (`references/entry-ladder.md`), not a fresh entry.

### Order Block

Keep:

- Last opposing-close candle(s) before displacement.
- Best after sweep + structure shift / CISD.
- Retest should respect the OB; body close through weakens or invalidates.
- Prefer OBs aligned with HTF bias and premium/discount.

PA translation: OB = candidate pullback zone. Do not treat any supply/demand rectangle as valid without displacement and follow-through.

### Breaker / BPR / OTE

Breaker:
- Needs a confirmed four-point structure plus prior liquidity sweep and displacement.
- Retest should hold the breaker mean threshold.

BPR:
- Overlap of opposing FVGs after aggressive sweep and return.
- Stronger in the correct premium/discount side.

OTE:
- 0.618-0.786 retracement of displacement leg after sweep/MSS.
- Needs overlap with PD array and HTF context.

PA translation: these refine location; they do not replace trigger quality.

### AMD / Power of Three

Keep:

- Accumulation = range building liquidity.
- Manipulation = sweep against expected delivery direction.
- Distribution = expansion toward DOL.
- If price fails to return aggressively after a breakout, do not label it manipulation.

PA translation: AMD is a session narrative. It is useful only if current bars confirm the transition from manipulation to distribution.

### SMT Divergence

Keep:

- SMT compares correlated instruments or related indexes.
- It is most useful near real liquidity pools or session extremes.
- SMT is context evidence, not a standalone trigger.
- Require the traded instrument to show its own sweep, CISD/MSS, PA signal bar, or displacement before execution.

PA translation: SMT = divergence context. It can strengthen a reversal thesis, but cannot replace price action on the traded chart.

### Killzone

Keep:

- London and New York windows often matter because liquidity and displacement are more likely there.
- Killzone context can upgrade a sweep/reclaim/displacement sequence.
- A signal outside killzone is not automatically invalid, but it needs stronger PA evidence and fresh data context.

PA translation: killzone = time-of-day context. It supports a setup only after location, trigger, and trade equation are valid.

## Case Memory Patterns To Use

Use these recurring patterns as reminders while analyzing current charts:

### Pattern 1: MSS -> PD Array -> Inducement -> Expansion

Observed sequence:

1. Existing orderflow weakens or fails to close beyond a prior low/high.
2. Price breaks an intermediate swing and shifts structure.
3. Displacement creates an OB/FVG.
4. Price retraces into the PD array.
5. A short-term low/high is swept as inducement.
6. Price expands toward opposing liquidity.

Use as: a watch pattern after MSS. Do not call it complete until inducement and PA confirmation appear.

### Pattern 2: FVG Contains An Old Low/High

Observed sequence:

1. Strong displacement creates FVG.
2. Price later pulls back.
3. An old low/high inside the FVG becomes inducement.
4. If price sweeps it but fails to close through, continuation becomes more plausible.

Use as: target/entry refinement. The decisive evidence is whether closes respect the old low/high inside the FVG.

### Pattern 3: Multiple Inducements In One Trend Leg

Observed sequence:

1. Trend leg forms FVG.
2. Price sweeps one internal low/high but closes back inside.
3. A second FVG and second internal sweep form.
4. Continued respect of closes suggests continuation toward external liquidity.

Use as: avoid assuming the first internal sweep ends the trend. In strong PA trend context, internal sweeps can be continuation entries.

### Pattern 4: Protected Swing Fractal

Observed sequence:

1. HTF swing becomes important only after LTF CISD/MSS protects it.
2. LTF confirmation allows the HTF wick or swing to be treated as meaningful.
3. Retest of LTF OB/FVG gives refined entry.

Use as: HTF bias needs LTF delivery confirmation before execution.

### Pattern 5: Session Manipulation To Distribution

Observed sequence:

1. Asia or early session creates range.
2. London or NY sweeps one side.
3. CISD/reclaim confirms the sweep as manipulation.
4. Distribution targets the opposite side liquidity.

Use as: session context only. If there is no sweep/reclaim/displacement, do not force AMD.

## Failure Modes From Cases

Downgrade or wait when:

- Sweep occurs at a random level, not a real liquidity pool.
- Price sweeps but does not return inside or does not produce displacement.
- FVG/OB is in the wrong premium/discount side for the intended direction.
- Entry is taken before CISD or before a signal/entry bar.
- Target is too close to justify stop distance.
- Too many PD arrays are marked at once, making the entry model unclear.
- The case analogy is similar in labels but different in market state.

## How To Use Case Memory In Output

Internal reasoning or explicit full-report requests only — normal live chat never shows a case-memory line (WORKFLOW_CN 禁止输出 case memory 提醒段). Internally, keep one compact line after the binary gates:

`Case memory: similar OpenMobius cases support/ warn against this pattern because ...`

Allowed:

- "Similar cases often waited for inducement into FVG/OB after MSS."
- "Similar cases warned that sweep alone was not enough; CISD or reclaim was required."
- "Similar cases treated old lows inside FVG as inducement, but only when closes respected the level."

Forbidden:

- "This case proves the trade will work."
- "Historical cases show high win rate."
- "Because a similar case expanded higher, this one should too."

Case memory can support `watch only`, `wait`, or `reject` just as much as it can support `trade`.

## Conflict Rule

Do not count retrieved cases as votes. Before using a case, match asset class, timeframe role, cycle state, and what was known at decision time; verify that its stated asset/timeframe agrees with its own source metadata or image description. Any mismatch, duplicate extraction, conflicting definition, or hindsight-only lesson gives the case zero execution weight. Similar labels alone never upgrade a setup.
