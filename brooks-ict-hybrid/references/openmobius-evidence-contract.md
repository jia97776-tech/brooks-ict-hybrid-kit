# OpenMobius Evidence Contract Extract

Source: local clone of `https://github.com/MobiusQuant/OpenMobius-skill` at `work\OpenMobius-skill`.

Use this as an evidence contract for live or data-assisted analysis. It does not replace the fused PA + ICT decision chain.

## What This Adds

OpenMobius contributes five useful pieces:

1. Knowledge-base retrieval discipline.
2. Fresh-data discipline.
3. SMC structural field semantics.
4. Term alias normalization.
5. Optional chart/data tooling ideas.

Use these to ground evidence. Do not import OpenMobius' mandatory output format or make Mobius API a hard dependency.

## Knowledge-Base Retrieval Discipline

When an ICT/SMC concept is a decisive part of the analysis, normalize the user's words to a known rule card before reasoning:

- `fair_value_gap`
- `change_in_state_of_delivery`
- `liquidity_sweep`
- `order_block`
- `breaker_block`
- `balanced_price_range`
- `premium_discount`
- `a_ict_entry_checklist`
- `accumulation_manipulation_distribution`
- `optimal_trade_entry`
- `smt_divergence`
- `killzone`

Then translate that concept into the fused PA + ICT chain:

1. Is it destination, location, trigger, timing context, or confirmation?
2. What exact evidence would confirm it on the current chart?
3. What exact evidence would invalidate it?
4. Does it pass the binary tree, or does it only create a watch condition?

Do not let concept labels become conclusions. A labeled FVG, OB, BPR, sweep, SMT, or killzone only matters after PA context and evidence gates agree.

## Freshness Principle

When the user asks about a current market, asset + timeframe, or "now/today/latest" style setup:

- Do not answer from memory.
- Use fresh local/user-provided data when available.
- If using external live data, include the data timestamp and whether it may be stale.
- If no fresh data is available, state that the read is screenshot-only or scenario-only.
- Do not invent exact prices, timestamps, pivots, BOS/CHoCH events, or freshness labels.

For screenshot-only analysis, phrase conclusions as:

- `visible chart suggests...`
- `if this is the current chart...`
- `exact levels need fresh OHLCV confirmation`

## SMC Structural Field Semantics

If an SMC indicator or structured data source provides these fields, translate them into the fused chain:

| Field family | Meaning | Fusion use |
| --- | --- | --- |
| `swing_trend` / `internal_trend` | HTF/LTF structure bias | PA market state + directional gate |
| `BOS` | Continuation structure break | Displacement/follow-through evidence |
| `CHoCH` | Potential reversal structure break | Reversal candidate, needs PA confirmation |
| `swing_pivots` HH/HL/LH/LL | Swing map | Market state and invalidation |
| `equal_highs` / `equal_lows` | Liquidity pools | DOL/magnet candidates |
| `order_blocks` active/mitigated | Candidate structure zones | PDA/location, not trigger |
| `fair_value_gaps` active/mitigated | Imbalance zones | PDA/location or target space |
| `premium_zone` / `discount_zone` / `equilibrium_zone` | Range valuation | Correct side for long/short |
| `Strong High` / `Strong Low` | Likely protected pivot | Invalidation / reversal confirmation |
| `Weak High` / `Weak Low` | Likely breakable pivot | DOL / target candidate |
| `alerts_last_bar` | Most recent fired event | Fresh trigger candidate, not final verdict |

Priority:

1. CHoCH after sweep can matter more than a prior BOS.
2. Strong/Weak labels help define DOL: weak pivots are more likely draw targets; strong pivots are invalidation/reversal references.
3. Active zones matter more than mitigated zones; mitigated zones are context unless price reclaims them.
4. Data-derived structure takes precedence over blurry visual price levels, but still needs PA context.

## Term Alias Normalization

Normalize user language before analysis:

- `sweep`, `stop run`, `liquidity grab`, `raid`, `stop hunt` -> Liquidity Sweep / failed breakout test.
- `FVG`, `imbalance`, `BISI`, `SIBI`, `liquidity void` -> Fair Value Gap.
- `CISD`, `CSD`, `change in delivery`, `closure through opposing candles` -> Change In State Of Delivery.
- `OB`, `order block`, `opposing candle series` -> Order Block.
- `BPR`, `balanced price range`, `opposing FVG overlap` -> Balanced Price Range.
- `OTE`, `optimal trade entry`, `0.62-0.79 retracement` -> OTE.
- `premium`, `discount`, `EQ`, `equilibrium` -> range valuation.
- `MSS`, `CHoCH`, `BOS`, `structure shift` -> structure transition/break family.
- `AMD`, `Power of Three`, `accumulation manipulation distribution` -> session/delivery narrative.

Keep common English technical abbreviations in output: FVG, OB, BPR, OTE, CISD, MSS, BOS, CHoCH, SMT.

## Optional Tooling Boundary

OpenMobius has useful tool patterns:

- `kb_retrieve.py`: retrieve concept/case cards by keyword.
- `kb_klines.py fetch/indicators/chart/render`: fetch OHLCV, SMC structure, and render charts.
- `kb_draw_annotation.py`: draw zones/levels on a chart image.

In this skill, tools are optional:

- Use them only when available and useful.
- If unavailable, continue with screenshot/user data and mark limitations.
- Do not require Mobius API for every analysis unless the user asks for current market data.
- Do not let auto-generated overlays become the trade decision; they are evidence inputs.

## Evidence Hierarchy

Use this hierarchy when sources conflict:

1. Fresh OHLCV / structured data with timestamp.
2. Clear screenshot labels and visible chart structure.
3. Retrieved concept rules.
4. Case memory analogies.
5. General market knowledge.

Case memory and general knowledge can never override fresh chart evidence.

## Retrieval Conflict / Provenance Guard

Retrieval rank and occurrence count are not consensus. OpenMobius preserves `definition_per_source`, records hundreds of alias conflicts, and has removed cases whose screenshot asset contradicted the card label. Therefore:

- Never vote by top-K count, duplicate cards, alias frequency, or number of similar cases.
- For concept conflicts, use the mechanical definition that matches the current chart; preserve source-specific differences instead of averaging them into a stronger rule.
- A case may influence execution only when asset class, timeframe role, cycle state, and decision-time information match. A ticker/timeframe/image mismatch disqualifies it.
- Duplicate, contradictory, provenance-poor, or outcome-only cases cannot upgrade grade, size, entry permission, stop tightening, or runner permission.
- When unresolved, downgrade the case layer to `no weight`; fresh bars + PA structure still decide.

## What To Preserve In Final Reasoning

Internal reasoning or explicit full-report requests only — never shown in normal live chat (Trader Identity Contract hides `evidence basis`). When relevant, keep a compact evidence line internally:

`Evidence basis: visual-only / user OHLCV / fresh OHLCV as of <timestamp> / SMC fields / case memory.`

Do not add a long data-source footer unless the user asks for data provenance or live data was actually used.
