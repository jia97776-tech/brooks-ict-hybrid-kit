# Live Desk Calibration

Use this file to calibrate judgment and tone for this user's live trading chat.
Load on 复盘 / dispute — not required for every live tick.

**Evolution (2026-07-09):** append cases here; promote to Hard Rule only via SKILL evolution protocol (same error ≥3× or ≥2R/week attributable). Keep this file from becoming a second rulebook — policy lives in SKILL + execution-gates + entry-ladder.

Contents:

- Core Calibration / Execution Proximity Rule / Common Mistake
- EURUSD Calibration Example
- Tone Calibration
- Live Trade Review Calibration (2026-06) — eight outcome-verified cases from this user's real trades
- Case Format Going Forward — cycle-bucketed, outcome-embargoed recording rules

## Core Calibration

The user's preferred assistant is an execution desk, not a research analyst.

The key question is not:

`Which side had the strongest previous move?`

The key question is:

`Which side is closest to a valid executable trigger right now, with clean stop and target space?`

## Execution Proximity Rule

When choosing the near tactical side, rank evidence in this order:

1. Trigger distance: which side needs fewer confirmations from current price?
2. Target room: which side still has enough room before the nearest DOL/target?
3. Stop clarity: which side has a structural invalidation close enough to use?
4. PA state: follow-through, overlap, failed breakout, second entry, reclaim, or chase risk.
5. ICT location: sweep, DOL, POI, FVG/OB/BPR, premium/discount.

Do not choose a side just because it explains the last move. Choose the side that can be traded next.

## Common Mistake

Bad pattern:

`Price swept a low and bounced, so the closer side is LONG.`

Why bad:

If the bounce already hit the near upside DOL and price is now rolling down toward an acceptance line, long may be late while short may be closer.

Better pattern:

`The low-sweep bounce already reached the near upside liquidity. Now price is back at the acceptance line, so the closer tactical side is SHORT conditional if it accepts below that line.`

## EURUSD Calibration Example

Situation:

- Price swept low at `1.13446`.
- It bounced to `1.13725`.
- Current price returned toward `1.13660`.
- Upside near target was already touched.

Research-style answer to avoid:

```text
Closer side: LONG.
Reason: price swept 1.13446 and bounced; wait for pullback to go long.
```

Live-desk answer:

```text
EURUSD: more likely wait for short acceptance, do not chase long.

Price 1.1366. The low-sweep bounce already tagged 1.13725, so long target room is crowded. Now price is testing 1.13660 acceptance after rolling off the high.

Closer side: SHORT conditional.
Wait for acceptance below 1.13660; stop above 1.13725/1.13740; targets 1.13620 / 1.13580 / 1.13480.

If price reclaims 1.13700, cancel the short idea.
```

## Tone Calibration

Use phrases like:

- `现在别追`
- `更接近的是...`
- `我要等...`
- `这里不是好入场`
- `已经吃到近端目标，空间不舒服`
- `这笔只算 conditional`
- `如果重新站回...这笔取消`

Avoid phrases like:

- `多头条件 / 空头条件` as equal sections
- `技能门控结论`
- `terminal = wait`
- long tables
- textbook explanations of EMA, DOL, or market structure unless asked

## Live Trade Review Calibration (2026-06)

Outcome-verified cases from this user's real trades. Format is deliberately embargoed: only what was visible at decision time, the call made, the outcome, and one lesson. Do not add hindsight narrative when extending this list.

1. USDJPY long (06-26). At decision time: trade in profit, BE discussion. Call: BE stop placed at entry price 161.60. Outcome: wicked to 161.576, stopped, then V-reversed straight to the 161.744 target. Lesson: BE goes below structure (pullback low / swept level + buffer), never at entry price.
2. BTC long (06-26 night). At decision time: third test of a ceiling near 60,200, pullback long taken; first stop 59,835 traded. Call: user held through the stop waiting for a bounce; desk pushed exit late. Outcome: -440 became -530, stop walked down to 58,300. Lesson: the first stop executes unconditionally; a thrice-tested ceiling pullback is prime false-breakout territory.
3. US500 long (06-26). At decision time: first entry 7321 stopped at 7305 by a wick through the low. Call: re-entered at 7310 after the swept low was reclaimed. Outcome: +46. Lesson: stop-run reversal second entry is a winner pattern — reclaim plus fresh trigger, not revenge.
4. SOL (06-26). At decision time: scanner bias SHORT all day, short RR flagged high, no long candidate ever generated. Outcome: H4 rallied 66 -> 72.5 (+10%) with zero alerts. Lesson: scanner locks a side; when the flip trio completes on raw bars (low sweep reclaimed -> higher low -> prior high breaks on a close), flip the desk answer regardless of scanner bias.
5. EURUSD short (06-26). At decision time: counter-H4 fade lost small; scanner re-emitted the same short after price had broken the prior high 1.14074. Call: skipped. Outcome: re-trigger was at a strictly worse location. Lesson: a mechanical re-trigger of a just-failed idea at a worse price is not a second chance.
6. XAU scalps (06-29). At decision time: repeated stop-outs across the day. Cause: stops tightened from structure (4080) into the sweep zone (4076), taken by retests of the swept high. Lesson: lock profit by reducing size; move stops only with structure; sweep-entry stops go beyond the swept extreme + buffer.
7. Breakout chase (06-29). At decision time: user hesitated on the trigger, missed, then messaged `已经XXXX了` repeatedly and market-bought the vertical top. Lesson: on chase pressure, stop quoting pullback levels and hand over one pending-order plan (buy-stop above the hold) with stop and cancel condition.
8. BTC alert misread (06-26). At decision time: price traded through the alert line; desk declared `你已经止损出了，自动平仓`. User: `我没出呢`. Lesson: the local stack only alerts, it never closes trades — confirm the fill before saying the user is out, and never write an unconfirmed exit into the review.
9. ETH both sides (07-02). Cycle: trading range inside a fresh H4 bull leg (H4 swept the 1549-1556 lows on 07-01, MSS+CISD confirmed up). At decision time: scanner gave M15 SHORT READY (swept 1637.2, POI 1641.4, SL 1647.5, DOL 1596.3) while H4 structure was long; the PA agent gave the H4 pullback long with stop under the 1613.8 pullback low. Call: user shorted 1635 on the M1 failed retest AFTER price accepted back below the swept 1637.2, stop just above the failed level (~2.2 risk vs the scanner plan's 6.1). Outcome: +6.52R realized — but the low was 1613.8 (~9.5R open); the user held for the far DOL 1596 out of greed and exited ~3R off the low on the bounce. 1596.3 never traded — 1613.8 held as a higher low and price rallied to 1651.7, so the mechanical hold-for-DOL plan resolved -1R, while the PA-agent long also paid. Lessons: (a) two systems can both be right on different timeframes — a counter-HTF sweep short is a scalp to the NEAR level, taken and closed; only the HTF-aligned side earns runner/DOL treatment (scanner now tags `counter_htf`); (b) once acceptance back through the swept level is done, the failed-retest entry's stop belongs above the FAILED LEVEL, not the sweep extreme — that risk compression is what turned the same move into 6.5R instead of 4.5R max; before acceptance, case 6 still applies (stops inside the sweep zone get run).

10. NAS100 short campaign (05-04, user-reported 07-04, anchored to D1 data). Cycle: tight_channel up ending in a three-push wedge (D1 highs 27778 → 27820 → 27851 with shallow pullbacks; Asian session pushed the final new high). At decision time: Asian-session three-drives wedge into a new high above prior days' highs, London open reversed; 5M CISD confirmed the turn; FVG/iFVG/BPR zones marked the retest ladder; DOL = Asia low. Calls: first short stopped (campaign -2R total on the losing side); four re-entries each on an independent trigger (CISD / FVG retest / MSS+FVG / CISD), all rode to the Asia-low DOL. Outcome: +23R gross, +21R net; the FULL exit at Asia low mattered — the next session (05-05) exploded upward and the market ran 27851 → 29500 within a week, so any held runner would have been destroyed. Lessons: (a) MTR first attempt failing is tuition, not refutation — re-entry on fresh triggers after a stop is where the pattern pays (matches the ~35-40% first-attempt prior); (b) a counter-HTF intraday reversal earns the NEAR liquidity (Asia low) only — banking everything at the session DOL is what made this +21R instead of a giveback story; (c) each add needs its own trigger — four adds on four independent confirmations is pyramiding, four adds on one opinion is doubling down.

11. NAS100 short (05-21, user-reported 07-04, anchored to D1: O 29107 / H 29477 / C 29460 — a strong up-close day; the trade was counter the May D1 grind-up, same class as case 10). Cycle: unknown intraday (15M bear leg inside a D1 uptrend; entry on a deep three-push pullback into premium). At decision time: Asian long into Daily SIBI already TP'd; London swept Asia high (three drives); 15M bullish structure broke; NY open pushed into 1H+15M SIBI + swept EQH, then displaced down through Asia low leaving OB-/M3 FVG; NY midday three-push back into the M3 PDA, M1 CISD fired. Call: short ~29213, textbook entry — fast displacement to +3R open. Outcome: stop never moved off the original structure; a news spike reversed the whole leg and took the full -1R; the news leg became the day's real move (close 29460). Lessons: (a) the leak was management, not entry — after ~2R the stop moves to the nearest confirmed structure (the displacement leg's origin / M1 swing existed); +3R open profit with a stop still at entry-structure is the exact 浮盈>2R回吐 failure mode (10/24 in the loss audit), now with a face; (b) paired with case 10: counter-HTF intraday reversals are rent, not ownership — one banked everything at the session DOL and kept 21R, one waited with an unmoved stop and gave back 4R of swing; (c) secondary: holding a counter-HTF short through the NY-midday calendar window deserves a newsguard check before the trigger, not after.

12. NAS100 long (06-02, user-reported 07-04, anchored to D1: O 30410 / H 30779 / C 30659). Cycle: trading_range low sweep inside the D1 grind-up (1H MMBM read: discount sweep → reversal → buy-side delivery). At decision time: 1M iFVG+OB+ entry 30553, SL 30501 (52pt structural stop), declared target ERL 30652 (prior-day-high area) = planned 1.9R. Outcome: displacement consumed the ERL and the user trailed instead of exiting, realized +3.77R (~30749, near the 30779 day high). Lesson: the mirror of case 11 — the SAME "hold past the plan" behavior is discipline on an HTF-ALIGNED trade and greed on a counter-HTF one; aligned expectancy is right-tail-driven (replay: remove the few big runners and aligned significance dies), so an aligned trade with active displacement earns the trail past the stated target, while cases 10/11's counter-HTF class never does. HTF relation decides whether "taking more" is the edge or the leak.

13. WLD short (07-03/07-04). Cycle: unknown intraday pullback inside an H4 down-leg (0.4362 → 0.4259 sweep, htf_bias not counter — an aligned continuation short, not a fade). At decision time: H4 CONDITIONAL_READY, POI 0.4342-0.4366, SL 0.44373, mgmt 0.42233, plan target 0.412; desk plan was a pending sell-limit in the POI, explicitly not a market chase. Call: the limit at 0.4355 did not fill on the wick; user chased a market short at 0.433 (worse price, risk grew from planned 0.00713 to 0.01073, RR fell from ~3.45 to ~1.96). Price then bounced to 0.4356 and the user closed near breakeven at 0.432 (+0.09R) while the stop was never threatened; price kept falling afterward without the position. Lessons: (a) chasing after a pending order misses its fill gives up the RR the wait was for — the fix is to let the miss go and wait for the next trigger, not convert it to a market order; (b) closing near breakeven on a normal adverse wick when the stop hasn't traded is the stop's job being done by fear instead of price — it forfeits the trade before the plan actually failed.

14. DOGE long (07-03/07-04, missed setup, no fill). Cycle: unknown intraday (M15 READY, swept prior low, CISD confirmed, H4 bias aligned long). At decision time: POI 0.07658-0.07666, plan was buy-stop above 0.07701; price poked 0.07701/0.07705 twice with no follow-through, then held above a higher low (0.07674) and closed back through 0.07706 with volume. Call: after the double poke failed, plan was raised to buy-stop above 0.07706; user never placed the order. Outcome: clean displacement 0.07706 → 0.07772+ (main target hit), no position taken. Lesson: when a level pokes twice and fails, raising the trigger above both pokes is correct — but the order has to go in the moment the close-through confirmation prints, not after; hesitating past the confirmation bar turns a valid revised plan into a miss.

15. ETH short 1796.3 + US500 short 7507 (07-05/07-06, paired giveback lesson). Cycle: unknown intraday. At decision time: both were valid trigger entries (ETH sell-stop fired per plan; US500 breakdown follow). Call: hold with trailing management. Outcome: ETH reached ~+13 points open profit with no partial taken, full position stopped ≈ breakeven on the snap-back; US500 stop was pushed to 7500.6 without a confirmed structure behind it, washed out at +6 points before an ~80-point move in the trade's direction. Lesson: two faces of one leak — at the management level or +1R (whichever first) a partial MUST come off, and the stop moves only to a confirmed structure, never to a round number ahead of it; papertrack quantifies the cost (76% of losing signals had ≥1R MFE, 55% had ≥2R).

16. USDJPY long campaign (07-07, four entries in one base). Cycle: unknown intraday (base forming above 161.7 in a USD-strong HTF context). At decision time: entries 1-3 (161.75/161.92/161.9) were same-tier retries into the same structural zone with stops clustered at 161.8x — all three stopped on washes; the desk then advised abandoning the idea. Entry 4 (161.9) came only after the close-through breakout confirmation printed. Call: entries 1-3 given/allowed; entry 4 taken by the user against a standing "give up" advice. Outcome: entries 1-3 = -3R total; entry 4 ran to 162.46, scaled at 162.30/162.43, ≈+5R — the week's biggest winner. Lesson: the zone circuit-breaker (two stops = idea dead at that tier) and the loss-streak brake stop SAME-IDEA repeats, not structure upgrades — after a genuine upgrade (close-through / flip trio / READY) the A+ re-entry is legal and must not be blocked by a blanket "stop trading" verdict.

17. Method split — LTF on-screen vs deep limit off-screen (07-10 Fable digest of user 07/03–05 corpus + cases 10–15). Cycle: n/a (meta). At decision time: desk habit was defaulting sweep-reversal plans to Tier 1 deep limits (EUR 1.1455 / AUD 0.6965 class); user repeatedly unfilled on shallow pullbacks and asked whether LTF entry/stop was allowed. Corpus already answered: M1/M5 CISD/iFVG is the user's highest-fill path (case 10 NAS campaign +21R net; case 12 1M iFVG +3.77R; 07-03 NAS long ~+1.4R near target; 07-03 XAU second entry +4.22R; 07-04/05 ETH 1802 shorts +6R/+5.8R with ~5pt structural risk). Leaks clustered post-entry: case 11 (+3R open, stop unmoved → -1R news); 07-05 ETH 1785 same-zone triple try; case 10/11 counter-HTF runner greed vs bank-near. Call: promote Screen Presence Routing into SKILL — on-screen default Tier 2; deep limit = unattended substitute only; desk owns three brakes (+1R partial, structure-only stop move, same-zone two-stop fuse). Outcome: policy write 2026-07-10. Lesson: entry skill is not the debate — harvest/stop-move/same-zone retry are; "入场归你，刹车归我."

## Case Format Going Forward

When a post-trade review or missed-setup review produces a lesson worth keeping, append it to the list above using exactly this shape:

`N. SYMBOL side (date). Cycle: <one of the 8 states in brooks-market-cycle-playbook.md, or unknown>. At decision time: <only what was visible then — scanner fields, PA read, position state>. Call: <the verdict given>. Outcome: <what price actually did / P&L>. Lesson: <one line>.`

Rules:

- Outcome embargo: never write hindsight narrative (`因为后来出了新闻`) — only decision-time evidence plus the outcome label. Hindsight cases teach look-ahead habits.
- Bucket by cycle, not by symbol: when reading cases for a live call, prefer cases from the SAME cycle state as the current chart. If the cycle read is unclear, use `unknown` — do not force a bucket.
- Keep wins and losses paired: never record only the winners of a pattern; a pattern with three recorded wins and no recorded failures is a sampling artifact, not an edge.
- Caps: this list holds the most recent ~20 cases; distilled method-level lessons graduate into SKILL.md rules or the playbook, then the raw case can be dropped. Do not let this file grow unbounded.
- Cases are calibration for tone and verdict thresholds, not proof of edge. Never cite a case as evidence a trade will work.
