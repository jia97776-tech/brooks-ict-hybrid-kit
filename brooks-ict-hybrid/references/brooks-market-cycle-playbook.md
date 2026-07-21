# Brooks Market Cycle Playbook

Source: upstream PA_Agent `prompt_engineering/` (v1.4, 2026-07-01). Compressed for live desk use. Route every chart to one of the 8 cycle states FIRST, then apply that state's allowed/forbidden list. A pattern name is never a trade by itself.

## Contents

1. Cycle Classification Tree
2. The 8 Market Cycles (read / allowed / forbidden / stop-target style)
3. H1-H2 / L1-L2 Counting
4. Always-In, 20GB, Gap Bar
5. Barbwire: No-Trade Environment
6. Failed Signals Become Magnets
7. Final Flag and Trend Exhaustion
8. MTR: Major Trend Reversal
9. Double Top / Bottom Micro Structure
10. Probability Anchors
11. Scalp vs Swing Math
12. Opening Session Playbook
13. Stop and Target Defaults

## 1. Cycle Classification Tree

The single sorting key for channel width is **depth of the last pullback vs the prior leg**. Slope, visual width, tick counts are only supporting notes and never override it.

```
Ordered swing sequence (HH+HL or LL+LH, 2+ groups, coherent)?
  NO  -> range family: clear edges tested 2+ times, EMA flat -> trading_range
         direction totally lost, EMA entangled, any entry ~coin flip -> extreme_tr
  YES -> 3+ groups AND parallel channel lines drawable?
         NO  -> trending_tr
         YES -> last pullback <30%  -> tight_channel
                30%-50%             -> normal_channel
                50%-78.6%           -> broad_channel / stairs
Overlay: 2+ consecutive trend bars, body overlap <30%, near-zero tails -> spike (spike outranks micro_channel)
A new LL in an up channel (or HH in a down channel) -> immediately re-test for range.
```

HH+HL alone does not disprove range character: a rising channel is usually a tilted trading range and a HTF bear flag.

## 2. The 8 Market Cycles

### 2.1 Spike

- Read: 2+ consecutive trend bars same direction, big bodies, overlap <30% (3-5 bars with overlap <20% = standard spike), EMA pulling away, visible urgency. One giant bar alone is only a candidate — wait for the second bar.
- Climax rule: any strong sequence + one exhaustion sign (tail >50% of body, body <30% of average, or an opposite trend bar) = climax risk. 6+ bars without pullback = warning even without exhaustion.
- Allowed: SPS only — limit/pullback entry at 38.2-50% retrace or prior bar extreme after the first pause; with-trend breakout of a spike flag.
- Forbidden: chasing spike bars at market or on stops (SCS), any reversal trade inside a spike, adding after a climax bar. After climax: wait, or with-trend SPS only after the pullback digests it.
- Stops/targets: stop = pullback low / signal bar extreme +-1 tick. TP2 = leg-length measured move. After a spike: 60% channel, 30% range, 10% reversal — plan for the channel, not the reversal.

### 2.2 Micro Channel

- Read: 2-10 bars, almost zero pullback, EMA hugging price. Usually a spike seen up close; if it meets spike criteria, call it a spike.
- Key stat: the FIRST breakout attempt against a micro channel fails >80% of the time.
- Allowed: with-trend entry after that first breakout attempt fails. Nothing while it is still forming.
- Forbidden: countertrend anything; buying/selling mid-formation; assuming the first break is a reversal.
- Stops/targets: stop = failed-breakout extreme +-1 tick; target = channel-width projection or next structure.

### 2.3 Tight Channel

- Read: last pullback <30%, pullbacks 1-3 bars, EMA touches hold, clear equal-length swings.
- Allowed: with-trend pullback entries (H1 acceptable here if Always-In is clear, pullback is 1-2 bars, and signal bar is strong); with-trend entry on failed channel-line break. Strong close near extreme + 1-2 bars follow-through after a channel break -> wait for the retest, then join.
- Forbidden: fading either channel line; reversal on the first trendline break; chasing the first breakout bar.
- Stops/targets: signal bar extreme +-1 tick; targets at prior swing then MM. Remember: a rising tight channel is an HTF bear flag — take with-trend profits at structure, do not marry the runner.

### 2.4 Normal Channel

- Read: last pullback 30-50%, swings of ~10-30 bars, EMA sloped with moderate distance.
- Allowed: with-trend only — H2/L2 pullback entries at EMA/trendline, breakout-pullback continuation.
- Forbidden: channel-edge fades, reversal trades, chasing edge breakouts (they usually get a reverse move).
- Stops/targets: signal bar extreme +-1 tick; TP1 nearest swing, TP2 channel target/MM.

### 2.5 Broad Channel / Stairs

- Read: last pullback 50-78.6%, needs 3+ HH+HL (or LL+LH) groups and drawable parallel lines; big overlapping swings; almost EVERY breakout gets a breakout test.
- Allowed: main-direction only — stairs pullback to prior extreme, breakout-test retrace entry after a break. H2/L2 strongly preferred over H1/L1 here.
- Forbidden: fading the far channel line, chasing breakouts (the test will hit your stop), countertrend scalps.
- Contracting stairs (each push smaller): momentum dying — cut confidence, never chase the last push.
- Stops/targets: pullback/test extreme +-1 tick, or swing extreme when noisy; TP1 next stair, TP2 channel far side.

### 2.6 Trending Trading Range

- Read: broad channel that failed the 3-group test — directional lean exists but sequence broken; edges drift.
- Allowed: with-lean entries at range/channel edges only; breakout signals only in the lean direction.
- Forbidden: anything in the middle third; counter-lean edge trades; treating the mild tilt as a trend to chase. **(2026-07-20 G3)** Never apply channel/spike trend-following logic mid-range — no mid-range breakout chase, no mid-range 2b array hangs; with-lean entries live at edges/pullback-to-edge only.
- Stops/targets: edge signal bar extreme +-1 tick; short targets — near structure first, opposite edge only as TP2.

### 2.7 Trading Range

- Read: heavy overlap, flat EMA crossing price repeatedly, both edges tested 2+ times, uncertainty is the point.
- Allowed: bias-side edge only — bullish bias: buy the low edge on a second entry (H2); bearish bias: sell the high edge (L2). Second edge test beats first touch. Failed breakout at an edge is the best signal in the room.
- Forbidden: both-side edge scalping when neutral; middle-third trades; chasing ordinary breakouts (~80% fail — trust the failure, not the break); trusting reversal bars in the middle (meaningless).
- Stops/targets: signal bar extreme +-1 tick (the edge itself is context, not the stop); TP1 near structure/mid, TP2 opposite edge or range-height MM after a REAL breakout.

### 2.8 Extreme Trading Range

- Read: EMA horizontal and entangled, mass overlap, tails everywhere, time passes but price goes nowhere (typical pre-news).
- Allowed: nothing. Best trade is no trade; any entry is a coin flip with costs.
- Rule: better to confirm extreme_tr a few bars late than to mislabel a normal range — the correct output here is sitting out.

## 3. H1-H2 / L1-L2 Counting

- H1 = first bar that takes out the prior bar's high after the first pullback leg; H2 = same after the second leg. L1/L2 mirror for shorts. The trigger is the break of the prior bar's extreme, not pullback bar count.
- H1/L1 is tradeable only in: strong trend / micro / tight channel, Always-In clear, shallow 1-2 bar pullback, strong signal bar. Otherwise wait for H2/L2.
- MUST wait for the second entry: MTR context, wedge/three-push, trendline-break retest, second test of a range edge, or when the first signal bar was weak.
- H3 usually = wedge flag — treat as a wedge, not another H2; beware climax at spike ends.
- Reset the count on: new confirmed swing point, Always-In flip, or a strong breakout with follow-through.
- Second entry pricing: a good second entry fills at the SAME or WORSE price than the first. A clearly better price = trap or misread — stand down.
- If the H2/L2 fails: no third attempt on the same structure. Re-diagnose the cycle instead.

## 4. Always-In, 20GB, Gap Bar

- Always-In read (last ~8 bars): majority of closes on one side of EMA, shallow counter-pullbacks, opposite reversal attempts keep failing, trend bars get follow-through.
- In a clear Always-In market the FIRST countertrend signal is low quality by definition. Countertrend only becomes discussable after trendline break + failed test of the extreme + second entry (see MTR).
- 20GB: ~20 consecutive bars without touching the EMA = very strong trend. Do not fade it because it "looks extended".
- First EMA touch after a 20GB run: high-probability with-trend entry, expect at least a retest of the trend extreme. Needs a signal bar and a small structural stop.
- Two failed attempts at the same 20GB/gap-bar structure: stop forcing it, go back to diagnosis.
- Gap bar (whole bar beyond the EMA against the trend): pullback is deep enough — expect a retest of the trend extreme; still needs a signal bar.

## 5. Barbwire: No-Trade Environment

- Read: range width <25% of average swing height, or 3+ heavily overlapping bars with a doji, or 10+ overlapping bars; dojis and tails around a flat EMA; ii/ioi patterns firing with no direction; sitting mid-range.
- Barbwire OVERRIDES every apparent signal inside it: H2s, outside bars, ii/iii — ignore them all. Default action: no trade.
- Never buy above a barbwire high or sell below its low on an ordinary breakout — that is the single most expensive habit here.
- Never park a stop 1-2 ticks beyond a barbwire edge.
- Only exceptions (all conditions must be stated): second entry at a CLEAR edge (not middle) with the bias; one side visibly trapped + strong entry bar with follow-through; post-barbwire spike-grade breakout with follow-through — and even then enter on the retest.
- 25-35% tightness = transition zone: breakout-wait only, no edge fades.

## 6. Failed Signals Become Magnets

- Magnets: failed signal bar extremes, failed trades' entry prices, entry bar extremes, stop clusters, breakout points. Price gets drawn back to test them.
- The extreme of a FAILED countertrend signal is a natural with-trend target — use it as TP1 before any R-multiple.
- Near a magnet, directional odds decay toward 50/50: do not initiate a fresh trade straight into one, and do not set stops just in front of round-number/tick-trap zones (5t/9t/17t/41t style traps).
- Repeated failed signals at one price build the next range edge.
- Invalidation should quote structure: "back through the failed signal's far side" = the read is wrong, re-diagnose — not just "broke support".

## 7. Final Flag and Trend Exhaustion

- Final flag: a horizontal 10-20+ bar pause LATE in a trend, near a measured-move target or prior extreme, volatility shrinking inside.
- FF breakouts in trend direction often FAIL and reverse. Late in a trend, do not chase a flag breakout — that is the tuition trade.
- Failed FF (break, no follow-through in 1-2 bars, back inside) = the highest-value early reversal evidence, but it only upgrades to a reversal trade when the MTR components complete.
- Tight FF can look like barbwire — barbwire rules win: nothing in the middle, wait for the edge failure.

## 8. MTR: Major Trend Reversal

Four components, all required before "reversal" is a plan and not a story:

1. A real prior trend (clear HH+HL or LL+LH).
2. Trendline / channel-line break on a CLOSE (not a wick).
3. Trend fails to resume (no strong follow-through, no new extreme).
4. Test of the old extreme fails (double top/bottom, lower high / higher low).

- Even a complete MTR's first attempt succeeds only ~35-40% — take the SECOND entry, not the first reversal bar.
- One reversal bar alone, or an FF failure without the extreme test, is an attempt, not an MTR. In a spike or micro channel it is nothing at all.
- Minor reversals (MRV) usually become pullbacks or ranges — do not size or narrate them as trend reversals.

## 9. Double Top / Bottom Micro Structure

- Valid: two tests at nearby extremes (small overshoot on wicks fine, no confirming close beyond), a clear pullback (neckline) between them, and a reversal signal bar on the second test.
- Invalid: second test makes a decisive new extreme (that is continuation); "double tops" inside barbwire/mid-range noise; a single long tail with no second structured test.
- Trade the SECOND test / neckline-pullback second entry, never the first touch. A micro double top/bottom on the last 10 bars often IS the failed extreme test of an MTR (component 4).
- Invalidation: a close beyond the second extreme kills the idea.

## 10. Probability Anchors

- Range breakouts: ~80% fail. Trend reversal attempts: ~80% fail into flags.
- Spike aftermath: 60% channel / 30% range / 10% reversal.
- Micro channel first breakout attempt: >80% fails (with-trend fuel).
- Complete MTR first attempt: ~35-40%; second reversal attempt: ~40% — hence second entries.
- Measured move: ~60% reach after a VALID range breakout; 70%+ on strong with-trend legs.
- H2/L2 > H1/L1 everywhere except strong tight/micro channels.
- Day-type mindset (Brooks, Ask Al 2016): on a trend day assume 80% of reversal attempts fail; on a range day assume 80% of breakouts fail. Classify the day first, then borrow the matching prior.
- Range-day panic dip: 4-5 strong bars down inside an established range, then a reversal bar → ~70% return toward the top of the range. Do not let a range-day flush read as a fresh trend.
- Most long/short probability reads live in 40-60%: early entry = small risk / lower odds, confirmed entry = higher odds / worse price. Say which trade-off the plan is taking instead of pretending certainty.

## 11. Scalp vs Swing Math (Brooks 2021 scalping rules)

- A scalp typically risks more than it makes (RR ≈ 1:2 reversed): breakeven needs 67%+ win rate, survival needs ~70%+. A swing at RR ≥ 2 lives on 30-40%.
- Desk translation: when `counter_htf=true` or a neutral-HTF condition caps the trade to scalp class (take the near liquidity and leave), the required trigger quality RISES — a scalp cannot afford a mediocre entry the way a 2R+ swing can. If the trigger is not clearly better than average, the scalp is a pass, not a small try.
- Minimum practical scalp span (below this, spread/slippage eats it): Emini ≥1pt, FX ≥10 pips — check the equivalent for the symbol before calling anything a scalp.

## 12. Opening Session Playbook (Brooks, ES RTH 5-min statistics)

Scope: these numbers come from ES RTH 5-min charts. Apply directly to index RTH opens; treat London/NY session opens on FX/metals as an analogy (weaker confidence); for 24h crypto use only the day-open/session-open logic, not the bar counts, and say so.

- Opening breakout: the first breakout/test of the open has ~50% reversal odds NO MATTER HOW STRONG it looks. Never load heavy on the first move of the day continuing.
- When is the day's high/low already in? By bar 1 close: ~20%. Bar 12 (~1h): ~50%. Bar 18 (~90min): ~90%. Bar 80: ~99.9%.
- Bar-18 decision point: if no direction has resolved by ~90 min, stop waiting for a story — the tradeable events left are a breakout of the 18-bar range or a reversal at its edge. A close-through of the 18-bar range: ~90% the day ends as that-direction trend day or a range day, not an opposite trend.
- Opening range under ~10 bars of history: wait for more bars or a follow-through bar before trusting any break of it.
- Opening reversal trigger: a FAILED breakout of yesterday's high/low early in the session, entered on the second entry, is the highest-quality opening reversal — better than any first-touch fade.
- Gap day: large gap + price far from EMA → RAISE the bar for joining trend-from-the-open. Two same-color bars are not enough there; demand consecutive strong trend bars (big bodies, small tails) plus context. (Official BTC materials conflict internally here; the live-room standard is the stricter one — use it.)
- One good swing: ~90% of days offer one reasonable swing trade in the first 1-2 hours of the main session. The opening scan's job is to find THAT one, not to catalog every candidate.

## 13. Stop and Target Defaults

- Default stop: signal bar extreme +-1 tick. Broad channel / noisy edges: nearest swing extreme +-1 tick. Never a fixed tick count instead of structure.
- Signal bar >1.5x average length: the structural stop is too big — skip the trade, do not shrink the stop into noise.
- Pricing order: entry -> TP1 (nearest real structure: edge, prior swing, magnet; must clear RR >= 1 on TP1 alone) -> TP2 (measured move / far edge) -> stop at the structure-failure point.
- Do not pull TP1 closer to force the equation, and do not use TP2 to justify a trade TP1 cannot.
- Layer targets desk-style: management level / main target (TP1) / runner (TP2-MM) — a far HTF magnet is a runner, never the default main target.

## 9. 日型量化判据（2026-07-21 · gate 非 signal）

外部验证收敛的可编程判据（arXiv:2605.11423 VVG 日分类器 / IBS 文献 / 趋势日阈值汇总）。**铁律：日型分类只当 gate（过滤/降级），永不当独立信号**——VVG 研究里 8 个基于日型的方向策略全部证伪，但分类器作为上下文过滤统计有效。

**趋势日判据（满足越多越确信）**：
- 日 range > **2×ATR20**（多头趋势日均 ≈2.1×，空头 ≈2.8×）
- 收盘落在当日 range **顶/底 10%**（IBS>0.9 或 <0.1）
- 开盘 30min 内价格与 VWAP 分离 ≥**0.3%**；首个回撤 <**25-50%** 开盘冲量
- **80% 的趋势日在开盘 30min 内定型**；趋势日最大回撤通常 18-20%

**IBS 均值回归门**：IBS=(C−L)/(H−L)；<0.2 次日偏涨、>0.8 次日偏跌——**但仅在判定为区间日时放行反转交易；趋势日/通道日 IBS 极值失效**。这就是「通道日禁逆势 fade」的量化形态：fade 之前先过日型 gate。

**与 8 态周期的关系**：本节是 session/日锚定视角（含 VWAP/RTH），8 态是时间框架无关的周期频谱——两套并行使用不互替。扫描器 `env_cycle` 标签（trend/channel/range/chop 粗分类，record-only）是 8 态的机械近似，desk 裁决仍以本 playbook 判定树为准。
