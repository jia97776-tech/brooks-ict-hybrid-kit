# Execution Aids: Evidence-Gated (2026-07-02 全网调研裁决)

Source: 2026-07-02 web research sweep (academic papers, official Brooks material, GitHub, quant blogs), judged under this user's anti-overfitting rules. This file records WHAT survived, HOW to use it, and — equally important — what was checked and rejected. Nothing here predicts direction; everything here is an execution filter or reference layer on top of the existing PA/ICT read.

## Survived: usable on the live desk

### 1. Opening range as day-structure reference (strongest evidence found)

- Zarattini/Barbon/Aziz (SSRN 24-98, 7000+ US stocks 2016-23, Sharpe 2.81): 5-min opening-range breakout has real alpha ONLY with a "stock in play" filter — elevated relative volume from a real catalyst. Naked ORB on everything has none.
- Desk use: treat the first 5-15 min range of the session open (index RTH open; London/NY open for FX/metals) as a legitimate liquidity/structure level on the map — the same standing as PDH/PDL. Give a break of it more weight only when the session has a catalyst and clearly elevated activity. Never trade it as a mechanical signal.

### 2. VWAP: institutional fair-value anchor, not a signal

- Institutional execution benchmarks cluster at VWAP (Madhavan 2002; ~2/3 of institutional fills within 10bp of VWAP). The "±2SD 63% reversion" numbers circulating online have no verifiable source — do not quote them.
- Desk use: session VWAP is a secondary reference level. When a planned FVG/POI retest roughly coincides with VWAP, entry confidence rises a notch; price far above/below VWAP late in a session is mild "chasing into stretched" evidence. VWAP alone never generates a verdict.

### 3. Session volatility awareness

- Consistent multi-source statistics: index futures concentrate volatility in the first 30 min of RTH; gold and EURUSD in the London/NY overlap. Overnight drift is real in equity futures (NY Fed sr917: returns cluster around the European open) — proof that "some clock hours are special" is a real phenomenon class, NOT proof of any ICT killzone win-rate claim.
- Desk use: a breakout during the instrument's high-participation window deserves more trust than the same bar shape in dead hours. This calibrates trust; it never creates a trade.

### 4. Crypto funding/OI: crowding filter only

- Funding-rate mechanism guarantees basis mean-reversion (arXiv 2506.08573), NOT price-direction prediction (Presto Research: ~12.5% variance explained at 7d, decaying fast). Using funding to pick a side violates this desk's own rules.
- Desk use: extreme positive funding + fast OI build = crowded longs → even with an aligned HTF bias, do not chase, tighten management, prefer the pullback entry. Mirror for extreme negative funding. It changes management posture, never the side.

### 5. ATR as stop-distance sanity check (confirms existing rule)

- No credible study fixes an optimal ATR multiple; the robust part is standardization: structure picks the stop LOCATION, ATR validates the DISTANCE. A stop under ~0.5×ATR from entry sits inside ordinary noise and will be swept by a normal rotation (6/29 XAU scalp day: repeated stop-outs came from shrinking stops below noise scale). Existing rule (structure extreme + 0.25×ATR buffer) stands.

## Rejected: checked, do not adopt

- **OB/breaker/killzone win-rate numbers (63%/71%/74%/68%/85%)**: all traceable only to content-farm marketing, mutually contradictory, no data. Never cite them; if the user quotes one, say the number has no source.
- **Unicorn model / Quarterly Theory / OSOK (2025-26 ICT fashions)**: zero backtests exist, not even rough ones. Default answer when asked: narrative products, unverified, the community produces new models faster than anyone verifies them.
- **CVD / footprint delta at retail granularity**: order-flow imbalance alpha is real in academic HFT studies (seconds, full order book) and does not transfer to M1/M5 aggregated retail feeds. Not worth the screen space.
- **Volume Profile POC/VAH/VAL as an independent edge**: concept-consensus only, no rigorous validation found; existing structure/liquidity mapping already covers it.
- **TICK/ADD reversal signals**: experience-post folklore, no validation; MSS/CISD already covers reversal confirmation.
- **Funding/OI as direction predictor**: see above — crowding only.
- **"Optimal" partial-exit / trailing scheme from external studies**: none exists; the answer can only come from this user's own journal distribution (30+ trades rule applies).

## Checked: Three Drives / 三推 (2026-07-03 两路调研裁决)

Verdict: **real concept, real lineage, zero statistical backing — narrative/attention tool, never an entry by itself.**

- **Provenance (settles the "ICT 三推理论" question)**: ICT did teach it — 2022 Mentorship Ep5, and he himself calls it the "classic Three Drives pattern", i.e. openly borrowed. True lineage: Elliott/Prechter (1978) → Raschke《Street Smarts》"Three Little Indians" (1996) → Carney harmonic Three Drives with 1.13/1.27/1.618 extensions (1999-2010) → **Brooks "Wedges and Other Three-Push Reversal Patterns" (2012) — the version this skill already runs** → ICT liquidity reskin (2022: each drive "consumes" short-term liquidity; entry = post-third-drive displacement + FVG). The Chinese term 三推 conflates all three lineages; the popular 中文 content is actually the Brooks wedge lesson, not ICT.
- **Desk translation (no new rule needed — it compiles to existing machinery)**: 三推 = wedge/three-push into a liquidity pool. Third push toward an HTF DOL/POI on visibly shrinking momentum (= 背驰, see `chanlun-wyckoff-fusion.md`) is an exhaustion **candidate**. It is still a countertrend fade: cycle-state gate stays senior (in a channel, the third push is continuation), and the entry still requires the desk's reversal sequence — sweep failure / MSS-CISD + second entry, per the MTR rules. The one usable ICT nuance: after three drives INTO the pool, don't demand a further full sweep of the pool before considering the reversal trigger — the third drive often IS the terminal sweep. That adjusts patience, not the trigger requirement.
- **Evidence tier: 概念共识、零验证.** No academic study covers three drives or wedges (LMW 2000 tested neither). Bulkowski's adjacent samples cut both ways and are method-limited (manual selection, ultimate-high measurement, no costs): rising wedge is his WORST-ranked pattern (break-even failure 51%, rank 36/36), three-falling-peaks weak (23% hit measure), three-rising-valleys decent — none isomorphic to the three-drives definition. Brooks's own numbers ("~70% chance a good wedge ATTEMPTS a second leg") are unaudited desk estimates — quote them as his opinion, never as data. Any 中文 "三推胜率X%" has no traceable source — say so.
- **Disambiguation duty**: 三推 ≠ Power of 3/AMD (a process model, not a swing count). If the user mixes them, separate the two before answering.

## Scalp win-rate levers (2026-07-03 全网调研裁决)

Research question: any evidence-backed way to push minute-level scalp win rate toward the 67-70% survival line? **Answer: no. The evidenced path is not a better scalp — it is a longer hold.**

### The calibration numbers (use these to audit every claim)

- The most rigorously verified intraday signal in the literature (SPY first-half-hour → last-half-hour momentum, Gao/Han/Li/Zhou JFE 2018, net-of-spread significant, replicated in 12/16 developed markets) lifts win rate from 50.4% to **54.4% — about +4pp**. Its profit comes from asymmetric payoff, not hit rate. **+4pp is the benchmark: anyone claiming a 65%+ minute-level win rate owes auditable trade records; otherwise it is marketing.**
- MNQ systematic falsification (Mesfin, 947 RTH days, 14 signal families, walk-forward + costs): sub-bar mechanical scalp signals have a gross edge ceiling of **0.07-1.50 pts per trade vs ~2 pts round-trip friction** — structurally negative, a microstructure equilibrium, not a method failure.
- The only two signals that survived that study's full criteria won 61-65% — via **regime classification + 60-75 minute holds**, not 1-6 bar scalps. Same shape as Zarattini's session-aware intraday trend (SPY net +19.6%/yr, but holds to close). The message is consistent: direction information accumulates past the friction line only with time in the trade.
- Population-level (two regulator full samples): Brazil futures — 97% of >300-day persistent day traders lose net, profitability declines MONOTONICALLY with experience (no learning effect); Taiwan — <1% consistently profitable. Discipline and screen time alone do not rescue short-hold trading.
- But skill exists and persists (Taiwan top-500 by prior-year Sharpe: +28.1bps/day net the NEXT year): the persistent winners were **aggressive takers anticipating direction** (71% marketable orders) — not passive spread-collectors — and ~40bps round-trip cost was the line between their positive gross and negative net. Queue-position research (Moallemi & Yuan): on large-tick instruments, queue value ≈ the whole spread, and back-of-queue fills are an adverse-selection filter working against you — "挂在touch上" without front-of-queue is not maker economics.

### Desk rules derived (all five, each with its source condition)

1. **Session windows stay the first gate** (existing rule, now stronger): index RTH open/close segments are the only evidenced windows; identical triggers in dead hours have no evidence behind them.
2. **Upgrade the scalp, don't polish it**: when a whitelisted scalp trigger fires WITH HTF alignment, the evidence-backed move is to hold ≥60 min / to a session objective instead of grabbing the near target — trigger early, hold longer. The near-target grab remains only for counter_htf scalps where holding is forbidden anyway.
3. **Friction pre-check before any scalp**: expected gross move to target must be ≥2× round-trip cost (spread+fees+slippage for that symbol, that hour). If it fails the arithmetic, the trade does not exist — regardless of the pattern's beauty.
4. **Entry style**: this desk's pending-order-at-structure entries are fine (they anticipate; the stop/limit at a level is not passive spread-harvesting). Do not add a "must be maker" rule — the evidence says persistent winners take liquidity with anticipation; on crypto perps prefer post-only where the queue allows, pay taker when the level is running away.
5. **Audit line for external claims**: quote "+4pp" whenever a signal seller, backtest screenshot, or the user's own hope says a filter pushes scalp win rate to 65-70%. Crypto note: BTC intraday predictability exists in peer-reviewed work (Wen 2022) but is 30-min-rebalance, gross-of-cost, sample ends 2020 — session-timing evidence, not a scalp-entry edge.

Bottom line for the Trade Class Contract: the honest answer to "how do I raise my scalp win rate" is usually **reclassify the trade** — same trigger, intraday-class hold. A true scalp (in-and-out at near liquidity) stays whitelist-only and cost-audited.

## In-house replay evidence (2026-07-02, one-month backtest + blind replay)

- Scanner signal layer (33d × 17 symbols, lookahead-fixed, paper terms): unfiltered candidates have zero edge; HTF-aligned + non-crowded is the only positive bucket (avgR ≈ +0.4, t ≈ 3.2) and it is tail-driven — remove the 10 best wins of the month and significance dies. Counter-HTF hold-to-DOL is negative. The mechanical gates ARE the signal-layer edge.
- Blind LLM re-review (180 settled candidates, decision-time data only): reviewers correctly enforced the gates (TAKE rate 59% aligned / 10% neutral / 3% counter) but showed NO within-pool discrimination — inside the good bucket their TAKEs did not outperform their SKIPs (n=120, direction slightly negative, reviewer-to-reviewer variance large). Consistent with the chart-reading audit prior: static-chart preference is not edge. Desk implication: enforce gates and manage trades; do not sell within-pool chart preference as alpha, and do not let a confident chart read override position sizing rules.
- Mechanical LTF entries (Model B replay, both whole-window and confirmed-swing stop anchors): LTF triggers time entries well (win rate ~3× the POI model on the same parents) but mechanized stops stay ~3-4× wider than the live playbook's at-touch stops (swing-confirmation lag + break-close entry), and both variants significantly underperform the plain POI limit model. The LTF layer's value is discretionary at-touch execution with tight stops — it did not survive mechanization; Model B stays disabled.

## The falsification anchor (why this desk trades the way it does)

Mesfin 2026 (arXiv 2605.04004, MNQ 5-min, 947 days, walk-forward + t≥2 + costs): 14 families of naked intraday OHLCV signals — including liquidity grabs, ORB variants, gap plays, session momentum — ALL fail strict testing. Meanwhile the study's own multi-factor composite signals (T≈5-6) show detectable edge.

Desk translation: no single pattern label (FVG, sweep, killzone, OB) carries alpha by itself. The edge this user validated lives in the joint condition — HTF bias × real sweep × MSS/CISD × precise POI retest × cycle-state permission × execution discipline. This is the standing scientific reason behind two existing hard rules: "no automatic trade call from one pattern alone" and "cycle state gates the trigger". When tempted to shortcut the stack because one ingredient looks great, this file is the reminder that the ingredient alone has been tested to death and found empty.
