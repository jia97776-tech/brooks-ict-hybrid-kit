# Live PA Action Gate

Use this internally before every live trading answer. The final answer should be concise Chinese, but this checklist is not shown unless the user asks for the reasoning.

## Core Rule

PA decides the action. ICT supplies location, destination, and invalidation.

The binary tree is hidden in normal chat. Use it to decide; do not display it.

Do not output PA as a long explanatory section in normal live chat. Convert PA into one action:

- `DO_NOT_CHASE`
- `WAIT_FOR_PULLBACK`
- `WAIT_FOR_SWEEP_FAILURE`
- `RECLAIM_ACTIVE`
- `SHORT_CONDITIONAL`
- `LONG_CONDITIONAL`
- `MANAGE_POSITION`
- `NO_TRADE`

## Five Internal Questions

Run these in order:

1. Market state: trend, range, transition, breakout mode, or failed breakout?
2. Location: edge, midrange, POI, after target hit, or chase zone?
3. Follow-through: strong closes and entry bars, or overlap/tails/no expansion?
4. Trigger: sweep failure, reclaim, MSS/CISD, second entry, or breakout-pullback?
5. Trade equation: clear stop, target room, and acceptable RR from current/entry price?

If any answer is unclear, downgrade the action. Do not fill missing evidence with story.

## Binary Verdict Contract

Every live answer must end internally at exactly one verdict:

- `TRADE`: entry/stop/target are defined and current price is comfortable.
- `CONDITIONAL`: side is clear but needs a specific trigger, pullback, failed retest, or reclaim.
- `WAIT`: setup has a side but the trigger is not here yet.
- `DO_NOT_CHASE`: direction may be right, but price is late or target is crowded.
- `MANAGE_POSITION`: user already has a trade; manage it first.
- `MISSED_ALPHA`: the planned move worked before entry or before the answer.
- `NO_TRADE`: no side has a clean location, trigger, stop, and target.

Do not finish internally with `maybe`, `both sides`, `watch only`, or `needs confirmation` when a more precise verdict is available.

Translate verdicts into natural Chinese:

- `CONDITIONAL` -> `可以等...再小仓`, `这笔只挂条件`, `等反抽压住/回踩守住`.
- `DO_NOT_CHASE` -> `方向没错，但现在别追`.
- `MISSED_ALPHA` -> `这笔已经走出来了，算 missed alpha`.
- `NO_TRADE` -> `现在没有舒服的单，只等...`.

## Action Mapping

- If price already hit the near DOL/target and current entry would chase into crowded space, use `DO_NOT_CHASE`.
- If price is midrange and both sides need multiple events, use `NO_TRADE`.
- If price sweeps a high and returns to an acceptance line with stop above the sweep and room below, the nearer side can be `SHORT_CONDITIONAL`.
- If price sweeps a low, reclaims, and still has room to the next upside DOL, the nearer side can be `LONG_CONDITIONAL`.
- If the sweep-low bounce already reached the near upside DOL, do not keep calling it long just because the prior move was up.
- If price reclaims a broken level and holds with follow-through, use `RECLAIM_ACTIVE`.
- If the user is already in a position, skip fresh-direction analysis and use `MANAGE_POSITION`.
- If scanner gives a side but PA shows target consumed, overlap, no trigger, or poor stop, downgrade to wait/do-not-chase.

Do not over-wait for formal confirmation:

- Missing M15/H4 MSS is not an automatic veto — but the early entry must be one of the Entry Timing Ladder's legal paths (`references/entry-ladder.md`): Tier 1 post-sweep deep POI limit (all four preconditions) or Tier 2 complete M1/M5 reversal sequence (sweep -> reclaim/failed retest -> close through the nearest LTF swing). A single strong entry bar or one-bar bounce alone is 赌信号, not a trigger (whitelisted M1 sweep V-reversal scalp excepted, per trade-class-contract).
- A slow fusion review is not the entry gate for fast M5/M15 moves. It can confirm, downgrade, or manage after entry.
- If scanner says the right side but RR is poor, first check whether the actual PA trigger gives a tighter structural stop. Use the tighter stop only if it is real AND acceptance back through the swept level is complete: above the failed retest high for shorts, below the failed retest low for longs. Before acceptance, the stop stays beyond the sweep extreme.
- If a setup has direction, location, stop, and first target but lacks one secondary confirmation, output a conditional small-size plan instead of neutral `watch only`.

## Important Brooks Filters

- Strong trends favor continuation until there is exhaustion plus credible reversal evidence.
- Most breakouts in ranges fail; require follow-through before trusting them.
- A good signal bar closes near its extreme and has small opposite tail.
- A good entry bar gives immediate follow-through.
- Tight overlap near the middle of a range kills most ICT-only ideas.
- EMA is secondary. Do not let EMA override target room, location, and trigger distance.

## Output Rule

After this gate, answer with the Live Desk Output Compiler:

1. Action verdict first.
2. Nearest tactical side or no trade.
3. One plain Chinese reason that translates the gate into trader language.
4. Trigger, entry area, stop, targets, and cancellation condition if tradable.

Never return an equal long/short menu for normal live chat.
Never show gate names, `PA action read`, `Closer side`, or `Evidence basis` in the final answer unless the user asks for internal reasoning.


## Direction Versus Execution

A direction call is not the same as an executable trade.

- If the direction was right but price already reached the near DOL, the live verdict can still be `DO_NOT_CHASE`.
- If the entry area was missed, do not force a late entry. Wait for a new pullback, reclaim, or sweep failure.
- If the stop must be placed too wide or too awkwardly from current price, downgrade even when the directional thesis is plausible.
- If the next target is too close, downgrade unless a better entry appears.

The final answer should be controlled by execution quality, not by whether the previous directional read was correct.

When the move worked before the answer:

- Say `missed alpha` or `target tagged`, not `reject`.
- Name the true entry window.
- Give the next re-entry condition.
- Do not restart a balanced long/short analysis after the market has already resolved.

## Position Mode

If the user already has a position, skip fresh opportunity mode.

Manage:

- current price versus entry
- stop / invalidation
- first management or partial level
- BE condition
- main target
- runner only if follow-through remains active

Never answer an active position with `watch only` as the main verdict.

## Target Selection Rule

Targets must be layered by trade purpose. Do not list every visible liquidity level as if all are equal take-profit targets.

Use this hierarchy:

1. `T0 / management level`: nearest acceptance line, EMA area, micro swing, or range midpoint. This is for partial/BE decisions, not necessarily final TP.
2. `T1 / practical target`: nearest clean liquidity or structure level with enough room after spread/slippage. This is the default target for a live desk answer.
3. `T2 / extension target`: next DOL only if PA follow-through is still active after T1.
4. `Runner target`: HTF DOL only when the market state supports trend continuation or expansion. Do not make it the default target in a choppy M15 trade.

Important translation rule:

- Scanner DOL is a map destination, not an automatic take-profit.
- If there is a nearer practical structure target, that nearer level should be the default `主目标`.
- A farther H4/HTF magnet should usually be described as `后面还有更远目标` or `runner`, not as the main target of the fresh live trade.

For countertrend, failed-breakout, or range-edge trades:

- Prefer conservative T1 at the opposite side's first acceptance/support/resistance area.
- Mention far HTF DOL only as runner/bonus.
- If T1 is too close for clean RR, say no trade or wait for a better entry.

For breakout/reclaim continuation trades:

- T1 can be the nearest untouched DOL.
- T2 can be the next swing/DOL if follow-through remains strong.
- Move BE/partial around the first management level before discussing runner targets.

When in doubt, answer with fewer targets:

`管理位 / 主目标 / runner`

Example:

`55 可以看，但不是默认第一目标。57.26 先管理，56.93 主目标，56.52 延伸；只有继续弱，才留 55 一带 runner。`

instead of three equal-looking take-profits.

## Execution Additions (from upstream PA_Agent v1.4)

1. Context-driven limit order gate. When the signal bar is unqualified, do not collapse straight to `wait`. If the cycle state is normal/broad channel, trading range, or trending trading range AND price is near a real anchor (edge, EMA, with-trend retrace level, support/resistance), a planned limit-order entry is allowed WITHOUT an independent signal bar — but only on the Always-In / bias side. Mid-range or barbwire with no anchor: hard no. This is the mechanical version of the `conditional` verdict.
2. Reversal cooldown. While the previous plan is not invalidated on a close, do not issue a new plan. Do not flip to the opposite side within ~3 closed bars of the last plan unless a close confirmed the structure failure. One bar must never flip the desk.
3. RR asymmetry. RR is computed on T1 and must clear the minimum on T1 alone. If RR is short: tighten the stop to a real structure or improve the entry — never widen the stop outward, never pull T1 closer, and never use T2 to justify a trade T1 cannot.
4. Weak trigger bar fallback. If the trigger bar is a doji/outside bar, pre-write the next bar's trigger condition and re-anchor the stop to the tighter prior-bar extreme once triggered, instead of abandoning the idea.

