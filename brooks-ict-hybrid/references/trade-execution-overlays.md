# Trade Execution Overlays

Use this reference when the user asks about live scanning, second review, fast/slow review design, order-flow or volume-profile confirmation, position management, or post-trade critique.

Contents:

- Role In The Hybrid Skill / Fast-Slow Review Split
- Local Live Data Source (endpoints, source discipline, scanner limits, field vocabulary)
- Scanner Map -> PA Filter -> Trade Plan / Single-Symbol Live Desk Analysis / Live Desk Output Style
- Fast Review Hard Kills / Pass Conditions / Slow Review Outcomes
- Conditional Order Plan / Missed Alpha Review
- PA Execution Additions / Order Flow Overlay / Volume Profile Overlay
- Live Trading Discipline / Post-Trade Critique

## Role In The Hybrid Skill

Keep `brooks-ict-hybrid` as the primary decision spine. Use external skills only as source material:

- `al-brooks-price-action`: reinforces market cycle, Always-In, signal-bar quality, follow-through, failed breakout, second entry, and scenario output.
- `trading-assistant`: reinforces live-trading discipline, order-flow/volume-profile overlays, and management language.

Do not output multiple expert opinions. Collapse everything into one fused verdict.

## Fast / Slow Review Split

When a scanner or live setup must be judged quickly, do not wait for a slow fusion review before producing a tactical alert.

## Local Live Data Source

For this user's local trading stack, use the local API before giving live-market opinions. Two route generations exist; probe `GET /healthz` or `GET /openapi.json` first and use whichever set responds — if a route 404s, switch generation instead of retrying.

- Base API: `http://127.0.0.1:8001`
- Compat scanner routes:
  - Latest price: `GET /price/{SYMBOL}` (examples: `EURUSD`, `USDJPY`, `XAUUSD`, `NAS100`, `US500`, `btc`, `eth`, `sol`)
  - Raw bars: `GET /bars?symbol={SYMBOL}&tf=M1|M5|M15|H4|D1|W1`
  - Scanner refresh: `POST /scanner/run-once`
  - Scanner candidates: `GET /scanner/status`
- Dashboard routes (newer generation): `POST /scan/run` + `GET /scan/status/{job_id}`, `GET /signals`, `GET /signal/{id}/bars`, `GET /signal/{id}/review`, `GET /signal/{id}/deep_pa`, `GET /review/live`. Candidate fields there are `fvg_entry_zone` (≈POI), `dol_target`/`tp` (≈DOL), `ltf_mss` (trigger), `daily_bias_aligned`, `ict_levels.sl`; `RR` may be absent and must be derived from sourced numbers.

Data source discipline: non-FX (crypto, metals, indexes, oil) must price from the MEXC-backed source; FX from the Gate TradFi adapter. Never take a non-FX live price from a Gate ticker — the source gap (gold 5-6 USD) can flip an entry/exit read. Crypto aliases `btc`/`eth`/`sol` are USDT perpetuals.

Compat scanner capability (rebuilt 2026-07-01 on real structure):

- `READY` = sweep + MSS and/or CISD confirmed on a close + clean planned RR. `CONDITIONAL_READY` = sweep with something missing (`reason` says what). `ARMED` = no sweep, liquidity map only.
- `mss`/`cisd` are independent close-through confirmations; `dol`/`dol_runner` are real untaken swing liquidity; `sl` = sweep extreme + ATR buffer.
- `rr` = planned RR from the POI retest; `rr_now` = chase-RR from current price; `late=true` -> plan the retest, do not chase; `target_crowded=true` -> near target consumed, do not chase.
- `mode=intraday|swing|both` selects M15/H4/both; the scanned universe and the not-scanned watchlist symbols are listed in SKILL.md `Local Data First` — use that list, do not invent candidates.
- M1/M5 bars are available for fast execution and Tier 2 triggers (Entry Timing Ladder).

Use this order for live questions:

1. Read the current price from the correct source for the asset class.
2. For a single-symbol analysis, read raw `M15` and `H4` bars and make your own Brooks + ICT judgment before looking at scanner conclusions.
3. Trigger a rescan when the user asks "scan", "anything to open", or asks about current opportunities.
4. Read the candidates and filter to the user's active liquid watchlist.
5. Prefer `READY` (close-confirmed trigger); for `CONDITIONAL_READY` the `reason` field names the missing piece — check it on raw bars.
6. Scanner flags are evidence, not entries. Even READY must pass the PA reclassification and current-bar read before becoming a verdict; `late`/`target_crowded` candidates default to wait-for-retest / do-not-chase.
7. Scanner bias can lock one side and stay silent through a strong counter move. If the flip trio completes on raw bars (low sweep reclaimed -> higher low -> prior high breaks on a close, or the mirror), answer from the bars and say the scanner is blind here.

### Scanner Map -> PA Filter -> Trade Plan

The local mechanical scanner gives candidates and structure:

- POI, DOL, SL/invalidation, RR
- READY/ARMED state
- sweep/MSS/CISD trigger flags

Use those as the map: possible entry, target, invalidation, and side to watch.

Then use raw bars for PA execution filtering:

- Is current price chasing high/low?
- Has price already reached the near target?
- Did the pullback hold or fail?
- Did the retest fail?
- Is the stop usable from the planned entry?
- Is RR still clean?
- Is the idea actionable, waiting, or missed?

Final output is a trade plan, not a scanner replay. Reclassify scanner levels:

- DOL -> management / main target / runner / discard.
- POI -> entry area / missed entry / wait zone.
- SL -> structural stop / too wide / unusable.
- READY/ARMED -> can act / conditional / missed / do not chase / no trade.

If price is already sitting on the DOL or first target, do not chase.
If scanner shows a distant HTF DOL plus several nearer structure levels, do not jump straight to the far DOL as the default target. Turn the nearer levels into management/main target first, and leave the HTF DOL as runner unless PA has already cleared the nearer path.

### Single-Symbol Live Desk Analysis

When the user says "analyze EURUSD/NZDUSD/BTC/XAU" or asks for an opinion on one instrument, scanner status is the map and fresh raw bars are the execution filter.

Do not produce a research report by default. Hide the data plumbing unless the user asks for evidence. The normal output is a live trade plan:

- Verdict first: wait for long, wait for short, do not chase, manage position, missed alpha, or no trade.
- One tactical side. Do not present equal long/short menus unless both sides are genuinely unusable.
- Current price/location in trader language.
- Entry/wait zone, stop/invalidation, management level, main target, runner condition, cancellation.

Internal evidence to check:

- Fresh `/price/{SYMBOL}` plus M15/H4 bars.
- Scanner side, POI, DOL, SL/invalidation, RR, sweep/MSS/CISD.
- Current location: range edge, POI, target zone, midrange, or chase zone.
- Trigger status: sweep failure, reclaim, failed retest, second entry, breakout-pullback, or target already consumed.
- Trade equation: usable stop, target room, and enough practical RR after reclassifying levels.

Do not let `scanner/status` override the raw-bar read. Also do not let a missing scanner flag erase obvious PA. If scanner says `CONDITIONAL_READY` and raw bars show sweep/failure/retest behavior with a defined stop and target room, answer as a conditional trade plan, not `watch only`.

Reserve `watch only` for genuinely midrange, no side, no stop, or no target cases. If one side is closer but still incomplete, say `wait for short` or `wait for long` and give the exact trigger.

### Live Desk Output Style

For normal live trading chat, compress the raw-bar analysis into a trading-desk answer. Do not default to a report/table.

Use this style:

```text
NZDUSD：等扫高失败再空，不追现在。

现价 0.56495，顶到 M15 区间上沿 0.5650 附近，H4 偏弱。这里直接空太早，追多又是买在区间上沿。

我要等扫 0.56526 后跌回 0.56440 下方再空。
止损放扫高点上方 0.56535/0.56550。
0.56420 先管理，主目标 0.56370/0.56335；跌破还压得住反抽才看更低。

如果 M15 强收站稳 0.56590，这笔空取消。
```

Rules:

- Lead with the action: `别追`, `等`, `可以小仓`, `减仓/BE`.
- Keep only the levels needed for the immediate decision.
- Avoid broad educational explanation unless asked.
- Avoid large tables in live chat.
- If the user missed the entry, say so directly and give the next re-entry condition.
- Do not ask the user to choose direction. Decide which side is closer to triggering from the current PA + ICT evidence, and say that side first.
- Avoid equal long/short menus in live chat. Only mention the opposite side briefly as invalidation or backup.
- Do not lead with "both long and short are waiting" unless there is genuinely no active edge. Pick the nearer tactical side, or say no trade and name one next event.
- If the user already has a position, answer as trade management, not as fresh-entry analysis.
- When scanner/raw bars identify an active conditional side, discuss that side first and downgrade/confirm it; do not bury it inside a symmetric scenario list.

Watchlist and scanned universe: use the list in SKILL.md `Local Data First` (24 scanned symbols; UK100/HK50/USDCNH/XBRUSD watched but NOT scanned). The user has asked to avoid non-USD FX crosses and low-liquidity/odd commodities such as cotton unless explicitly requested.

If the local API cannot be reached, state that fresh local data is unavailable and give only scenario framing. Never invent live price, scanner state, or levels.

Use two layers:

1. `fast_review` within seconds: decide whether the idea is executable now.
2. `slow_review` later: decide whether to confirm, downgrade, hold only, add, reduce, or record as missed/false-positive.

Fast review may only pass narrow, managed setups. It should kill obvious bad trades without trying to prove an A+ thesis. But it must not kill a good entry window just because slow review, MSS, or far-target RR is incomplete.

### Fast Review Hard Kills

Return `WAIT`, `REJECT`, or `MISSED` if any are true:

- No explicit entry area or trigger.
- No structural invalidation or stop.
- No nearby target or DOL.
- Current price has already reached or crowded the first target.
- RR is below the minimum after realistic spread/slippage and cannot be repaired by a tighter structural stop from the actual PA trigger.
- Price is in the middle of a range with no edge, POI, sweep, or reclaim.
- The idea is only a DOL, FVG, OB, or case-memory analogy without a PA trigger.
- The idea fights a strong Always-In trend without exhaustion, failed breakout, and second-entry evidence.
- Stop distance is unrealistic for the instrument.
- News/spread/volatility makes execution unreliable.
- Directional evidence conflicts and no side owns the chart.

Do not hard-kill solely because:

- M15/H4 MSS is missing while a legal Entry Timing Ladder path exists (`references/entry-ladder.md` + `execution-gates.md`): Tier 1 post-sweep deep POI limit (all four preconditions) or Tier 2 complete M1/M5 reversal sequence (sweep -> reclaim/failed retest -> close through the nearest LTF swing). A single strong entry bar or one-bar bounce alone is 赌信号 and does NOT rescue the candidate.
- Scanner RR is low because it uses a stale/wide stop, while PA gives a tighter structural stop at the failed retest.
- The far DOL is too far or too ambitious. Reclassify it as runner and use nearer structure for management/main target.
- Slow review is pending. Slow review confirms, downgrades, or manages; it must not be the only entry gate for M5/M15 windows.

### Fast Review Pass Conditions

Allow `FAST_CONDITIONAL` only when all are true:

- Direction is clear enough for the timeframe.
- Entry/POI is defined.
- SL or invalidation is defined.
- T1/DOL is defined and not already consumed.
- RR still passes with realistic execution, or can pass after using the actual failed-retest/reclaim stop instead of a stale scanner stop.
- PA has a live trigger that satisfies its own rule set: for sweep-reversal/MSS-class setups, a legal Entry Timing Ladder path (Tier 1 / Tier 2 — a lone signal bar or entry bar is not enough); for with-trend continuation (H2/L2, breakout-pullback, range-edge fade), the Entry Mechanics / cycle-playbook trigger for that pattern.
- ICT/SMC contributes location or destination: POI, sweep, DOL, premium/discount, OB/FVG/BPR, or liquidity pool.

`FAST_CONDITIONAL` means small size, quick BE/partial management, no add until slow review confirms.

`FAST_CONDITIONAL` is the correct output when the direction/location are usable but one confirmation is incomplete. Say it in desk language:

`可以小仓条件空/多`, `等反抽压住`, `等回踩守住`, or `这笔只算 conditional`.

Do not say only `watch only` when the setup has a clear side, trigger, stop, and management plan.

### Slow Review Outcomes

Use slow review for quality and management, not for the initial entry window:

- `CONFIRMED`: keep or manage toward runner targets.
- `DOWNGRADED`: no add, reduce risk, or take only quick target.
- `HOLD_ONLY`: existing trade can be managed, but no new entry.
- `EXIT_OR_BE`: PA failed or target consumed; protect capital.
- `MISSED_REVIEW`: the idea worked before review finished; record missed alpha.

## Quality Without Missing Fast Moves

Quality is preserved by three constraints:

- Fast review rejects structurally dangerous trades.
- Conditional setups use reduced size and faster BE/partial rules.
- Slow review has veto power over adding or holding runners.

A slow review that takes several minutes is a confirmation and management tool, not an entry gate for M5/M15 opportunities.

## Conditional Order Plan

When a setup is not executable now but has clear scanner levels and a clear missing trigger, do not stop at "wait".

Convert it into a conditional order/alert plan:

- Trigger: sweep failure, reclaim, acceptance below/above, pullback hold, or failed retest.
- Entry/wait zone: the area where action becomes valid.
- Stop: structural invalidation from that planned entry.
- Management: first partial/BE/reduce-risk level.
- Main target: practical objective.
- Runner: only if follow-through remains active.
- Cancel: what invalidates the idea before entry.

Target translation example:

- XAG sweep-failure short with a far H4 magnet near 55:
  - Management: `57.26`
  - Main target: `56.93`
  - Extension: `56.52`
  - Runner: `55.6-55.0` only after price breaks `56.52` and keeps failing on pullbacks

The plan is conditional. Do not imply the user should enter before the trigger.

## Missed Alpha Review

When the target is reached while the user was away or the entry window was missed:

- Do not recommend chasing at the target side.
- Mark it as `missed alpha`.
- State whether the original plan worked.
- Name the true entry window.
- Say whether scanner/second review was too slow or whether the user simply was away.
- Convert the lesson into a future conditional order plan.

## PA Execution Additions

Integrate these Brooks rules into the binary gates:

- PA is the action gate. Do not summarize it as a separate report section in live chat; translate it into `trade / wait / do not chase / manage / invalidate`.
- For live chat, run `live-pa-action-gate.md` before the response template. The gate decides the action; the template only formats it.
- Market state first: trend, range, breakout mode, or transition.
- Strong trends favor continuation until there is exhaustion plus credible reversal evidence.
- Most breakouts in ranges fail; require follow-through before trusting them.
- Good signal bars close near their extreme and have small opposite tails.
- Good entry bars show immediate follow-through.
- Lack of Always-In does not mean no trade; it may mean range-edge, failed-breakout, or second-entry logic.
- If the chart is overlapping and in the middle of a range, even beautiful ICT zones downgrade.

## Order Flow Overlay

Use Order Flow only when the user provides ATAS/footprint/DOM/tape data or local exports. Never invent OF evidence.

OF is a confirmation layer, not a direction engine:

- Delta divergence at a key level can confirm absorption or exhaustion.
- Stacked imbalance in the trade direction upgrades trigger quality.
- Opposite stacked imbalance, aggressive sweep against the idea, or support/resistance wall being consumed downgrades or rejects.
- DOM walls can be support/resistance only while they remain; pulled walls reduce confidence.
- Aggressive trades in the trade direction improve confidence; aggressive trades against the trade at a key level warn of failure.

Without OF data, do not wait by default. PA + ICT can still produce B-grade or conditional decisions.

## Volume Profile Overlay

Use VP only when the user provides VP levels, ATAS data, screenshots, or local exports. Never invent POC/VAH/VAL/HVN/LVN.

VP translations:

- POC = accepted fair value / magnet; useful as target or chop warning.
- VAH/VAL = range edges; breakout or failed-breakout decision zones.
- HVN = acceptance area; price often slows or rotates.
- LVN = thin area / vacuum; price can move quickly through it if accepted.
- Naked POC = magnet until touched.

VP should refine entry/target/management, not replace PA/ICT context.

## Live Trading Discipline

For actionable trade framing:

- User places orders; do not auto-trade.
- For normal live chat, use `live-desk-template.md` exactly: Opportunity Template for new ideas, Position Management Template for existing trades.
- Every idea needs direction, entry, invalidation/SL, target, RR, and management.
- Default conditional setup size is reduced; adding requires confirmed PA and slow review.
- Never add to a losing floating position.
- Move stops only toward lower risk, never wider unless the user explicitly reframes the trade before entry.
- Reverse only after a fresh completed bar or clear opposite trigger, not from frustration.
- If T1 is reached, discuss partial/BE before distant targets.

## Post-Trade Critique

Judge process, not outcome alone. A profitable trade can be poor process; a losing trade can be valid process.

Evaluate:

- Was the market state identified correctly?
- Did the idea have at least two independent reasons?
- Was entry supported by location plus trigger?
- Was SL structural and realistic?
- Was target space meaningful?
- Was management consistent with the thesis?

Be direct and specific. Friendly tone does not mean soft grading.
