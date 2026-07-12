# Live Analysis Examples

Use this file to learn how to think before writing the final live-desk answer. Do not copy these internal notes into the final answer.

The goal is to convert evidence into a trade action:

`market evidence -> scanner map -> PA execution quality -> one main plan -> natural Chinese answer`

## Core Conversion

Local mechanical scanner gives candidates and structural levels:

- POI, DOL, SL, RR
- READY / ARMED
- sweep / MSS / CISD

Treat these as the map:

- where price may enter;
- where the target may be;
- where the idea fails.

Then raw bars provide PA execution filtering:

- Is current price chasing a high or low?
- Has price already reached the near target?
- Did the pullback hold or fail?
- Is the stop easy to place?
- Is RR still clean?
- Is the trade actionable, waiting, or missed?

The final answer is a trade plan, not scanner replay.

Reclassify scanner levels:

- DOL may become management, main target, runner, or discarded.
- POI may become entry area, missed entry, or wait zone.
- SL may be structural, too wide, or unusable.
- READY/ARMED may become can act, conditional, missed, do not chase, or no trade.

## Anti-Patterns To Reject

Reject outputs like:

- `watch only，别追，多空都还差触发`
- `Closer side: LONG`
- `PA action read: WAIT_FOR_PULLBACK`
- `偏多条件...偏空条件...`
- `最终目标直接写最远 DOL`

Why:

- They sound like an analyst notebook, not a trading desk.
- They leave the user still choosing direction.
- They often blur `management`, `main target`, and `runner`.

Rewrite them into:

- one side or no trade;
- one main plan;
- one invalidation;
- layered targets.

## Example A: EURUSD Sweep High Failure

Raw evidence:

- Prior low sweep at `1.13446`.
- Rebound reached `1.13725`.
- Price later accepted below `1.13660`.
- Current price moved toward `1.1334`.
- Downside level `1.13245` is nearby.

Internal read:

- Direction after `1.13660` acceptance was short.
- Entry window was not at the low; it was the failure/retest around `1.13650-1.13660`.
- At `1.1334`, short direction can still be right, but new entry is late.
- `1.13337` is management, not main TP.
- `1.13245` is main target.
- Any lower target is runner only after follow-through.

Final style:

```text
EURUSD：现在别追，等反抽压住再空。

现价 1.1334，已经贴着 M15 新低，离 1.13245 也不远。方向还是空，但这里新开属于追在低点，止损不好放，RR 也被压缩了。

我要等 1.13420-1.13460 反抽压住再空。
止损放 1.13500 上方。
1.13337 只是管理位，主目标 1.13245；如果跌破后还有跟随，再留 runner。

如果重新站回 1.13460，这笔继续空的想法取消。
```

Why this is the right conversion:

- It chooses one side.
- It does not reopen a long case just because long had worked earlier.
- It turns the nearest low into management and the clearer next low into main target.
- It keeps any deeper extension as runner only.

## Example B: Scanner Map, PA Filters

Raw evidence:

- Scanner says EURUSD LONG candidate.
- POI `1.13245`, SL `1.13219`, DOL `1.13811`, RR acceptable.
- Current price `1.13377`.
- Price has not swept the POI yet.
- No clean sweep-low failure/reclaim yet.

Internal read:

- Scanner map is useful: POI, stop, target, RR are clear.
- But PA says execution is not ready because price is above POI and has not swept/reclaimed.
- Final answer should not say "scanner says long, buy now."
- Final answer should say "best candidate, wait for sweep-low failure."

Final style:

```text
EURUSD：最值得盯多，但现在还不能直接打。

scanner 给的地图很清楚：1.13245 是舒服位置，1.13219 是失效，1.13811 是上方目标。但现价 1.13377 还没扫到位，也没有扫低失败收回。

我要等它先扫 1.13245 附近，再站回去。那时才看小仓多。
止损放 1.13219 下方。
1.1360 先做管理，主目标 1.13811；只有站稳 1.13811 后才留 runner。

如果没扫就直接上去，这笔不追。
```

Important:

- The scanner long is not wrong.
- The live answer is still not `buy now`.
- Good live desk behavior is to preserve the map but delay execution.

## Example C: BTC Conflict But Target Tagged

Raw evidence:

- H4 had a violent drop and rebound.
- Price moved from `63200` area down through `61925`.
- Prior downside target around `61320` was tagged or nearly tagged.
- Current price is around `61250`.
- Market is volatile and can snap back hard.

Internal read:

- The short target worked, but current price is already in the target zone.
- This is not a fresh short. It is either take-profit/management or missed alpha.
- BTC needs stricter execution than EURUSD because rebounds are violent.
- New short requires a failed pullback, not a chase into the low.

Final style:

```text
BTC：目标到位后别追，等反抽失败。

现价 61250 附近，之前 61320 一带的下方目标已经被打到。方向上空头计划没错，但现在不是舒服的新空，容易追在目标区。

我要等反抽 61600-61900 压住，或者跌破后回抽 61300 不上，再看下一段空。
```

Important:

- Once price is already in or near the target pocket, the correct output is usually `do not chase` or `missed alpha`.
- Correct direction does not rescue a bad late entry.

## Example D: Scanner Says Ready But Price Is Late

Raw evidence:

- Scanner says READY short.
- Price already moved from entry to first target.
- Stop from current price is wide.
- Next target is close.

Internal read:

- The signal may have been good earlier.
- Current execution is bad.
- Mark as missed or wait for pullback.

Final style:

```text
这笔信号可能是对的，但现在已经晚了。

价格已经从入场区走到第一目标附近，现在追进去止损不好放，RR 被压缩。不要因为 scanner 还显示 READY 就硬追。

我要等回抽到原入场区附近压住，再考虑；不回抽就放过。
```

This is the key target-layering rule:

- first executable level = management;
- practical next structure = main target;
- farther HTF level = runner only.

## Example E: Build A Conditional Order Plan

Raw evidence:

- Scanner gives a clean POI, SL, DOL, and RR.
- PA says the current price is not executable yet.
- The missing event is clear: sweep failure, reclaim, pullback hold, or acceptance.

Internal read:

- Do not just say "wait".
- Convert the missing event into a conditional plan the user can set alerts around.
- Keep the plan conditional; do not imply automatic entry before the trigger.

Final style:

```text
EURUSD：这笔只能挂条件，不追现价。

我要的触发是先扫 1.13245，然后 M15 收回并站稳 1.1330 上方。
入场看 1.1328-1.1331，止损放 1.13219 下方。
1.1360 先做管理，主目标 1.13811；只有站稳 1.13811 后才留 runner。

如果没扫 1.13245 就直接上去，或者跌破 1.13219 不收回，这笔取消。
```

## Example F: Missed Setup Review

Raw evidence:

- User says they slept or missed the trade.
- The planned target was reached.
- Current price is no longer at the entry area.

Internal read:

- Do not chase.
- Judge whether the original plan worked.
- Identify the true entry window.
- Convert the lesson into a future conditional order plan.

Final style:

```text
EURUSD：这笔算 missed alpha，现在不追。

原计划是对的：1.13725 扫高失败后跌回 1.13660，下方目标兑现了。真正舒服的入场窗口在 1.13650-1.13660 反抽不过，不是现在贴着低点追。

以后同类结构要提前写成条件单：
触发是扫高失败后跌回接受线。
入场看接受线反抽压住。
止损放扫高点上方。
管理位先处理一部分，主目标拿近端结构位，runner 只有继续跟随才留。
```

## Example G - Far magnet stays runner

Market evidence:

- XAGUSD made a sweep-high and started failing back below the trigger zone.
- There is a visible far H4 magnet around `55`, but several nearer downside structure levels sit in between.

Trade-plan translation:

```text
XAGUSD：55 可以看，但不是这笔空单默认第一目标。

如果扫高失败空成立，57.26 先做管理，56.93 当主目标，56.52 当延伸目标。55.6-55.0 只有跌破 56.52 后还压得住反抽，才留 runner 去看。
```

Why:

- Far HTF DOL stays on the map.
- Nearer practical structure levels control the live trade plan.
- The answer must not jump straight from entry to the far H4 magnet as if the path in between does not matter.

## Example H: XAGUSD Sweep-High Failure Short

Raw evidence:

- Scanner side is `SHORT`.
- POI around `57.68`, far H4 DOL around `55.575`.
- Price spiked from the entry area into `58.99`, then failed to hold.
- Price accepted back below `58.70`, then below `58.40/58.25`.
- Scanner RR may look weak if it keeps a wide stale stop near `59.10`.

Internal read:

- This is not a neutral watch-only case after the spike fails.
- The actionable idea is short on the failed retest/acceptance back below the spike zone.
- Use the actual failed retest high for stop, not the stale wide scanner stop.
- `55.575` is runner only. It is not the default first TP.

Final style:

```text
XAGUSD：这笔应该等反抽压住做空，不是多空观察。

58.99 扫高后没有站住，重新跌回 58.40/58.25 下方，空头重新接管。没仓不能追低，但如果反抽 58.20-58.40 上不去，可以空。

止损放反抽高点上方，通常 58.50 上方；如果反抽到 58.70 才失败，就放 58.75-58.85 上方。
57.68/57.52 先管理，57.26/56.93 看主目标；55.575 只当 runner。

如果重新站回 58.70，这笔空取消。
```

Wrong conversion:

`XAGUSD: watch only. RR is low and target is 55.575.`

Why wrong:

- It ignores that PA already gave a sweep-high failure.
- It lets stale scanner RR hide a tighter failed-retest stop.
- It treats the far H4 DOL as default TP instead of runner.

## Example I: NZDUSD Conditional Short At Range Top

Raw evidence:

- H4 is bearish or low-range after a larger decline.
- M15 swept or tested the upper edge around `0.56512/0.56523`.
- Scanner says `CONDITIONAL_READY SHORT`, POI `0.56512`, invalidation around `0.56535`, DOL `0.56308`.
- MSS may be missing; sweep and location are present.

Internal read:

- This is closer to short than long.
- Do not answer with equal long/short conditions.
- If current price is below the POI but still near it, the plan is to wait for a small pullback to fail.
- `0.56380-0.56340` can be management before the scanner DOL.

Final style:

```text
NZDUSD：等反抽压住做空，不追低。

现价在 0.5646 一带，刚从 0.5651/0.5652 上沿压下来。H4 还是偏弱，M15 不是干净多头，是反抽到上沿后的压制盘。

我要等 0.5649-0.5652 反抽上不去再空。
止损放 0.56535 上方，保守 0.56550 上方。
0.56380-0.56340 先管理，主目标 0.56308；跌破后还能压住，才看 0.56284。

如果 M15 重新站稳 0.56535 上方，这笔空取消。
```

Wrong conversion:

`NZDUSD: watch only, long if 0.56590 breaks, short if 0.56420 breaks.`

Why wrong:

- It makes the user choose direction.
- It ignores the scanner's usable short map and the upper-edge failure.
- It hides the actual nearest tactical side.

## Example J: BTC Target Worked And Extended

Raw evidence:

- Scanner or prior plan had BTC `SHORT` from around `61925`.
- DOL around `61150/61320` was reached.
- Price later broke below `60000` and traded around `59160`.
- The best entry was near the high/POI, not after the target broke.

Internal read:

- The short idea worked. Mark it as target tagged or missed alpha.
- Do not chase new shorts after a 2000+ point dump.
- The next trade is a failed pullback short, not a late market short.
- This is also a process lesson: slow review cannot be the only entry gate when fast scanner plus PA gave the setup.

Final style:

```text
BTC：这笔空已经兑现并延伸了，现在别追。

61925 一带就是舒服空位，61150/61320 目标已经打穿，现在 59k 附近再空是追在低点，止损不好放。

我要等反抽 60000-60300 压住，或者更舒服等 60800-61150 回抽不过，再看二次空。
如果在 60000-60300 压住，止损放 60500 上方；如果到 60800-61150 才失败，止损放 61300-61600 上方。
59000 先管理，继续弱才看 58000/57200。

如果重新站回 61150 上方，这笔继续空先取消。
```

Wrong conversion:

`BTC: REJECT/WATCH because sweep is missing or slow fusion conflicts.`

Why wrong:

- The market already voted: entry-to-DOL worked.
- Missing slow confirmation after the move is not a reason to erase the fast setup.
- The correct live answer is missed alpha / wait for pullback, not a late neutral report.

## Compression Rules

When converting analysis to final answer:

- Replace "liquidity target" with "目标".
- Replace "near DOL" with "离目标不远".
- Replace "poor trade equation" with "RR 被压缩 / 止损不好放".
- Replace "confirmation missing" with "还差触发".
- Replace "acceptance below/above" with "跌回后压住 / 站回后守住".
- Replace "conflict" with "不舒服 / 容易被来回扫".
- Replace "scanner signal" with "scanner 给的地图".
- Replace "scanner approved" with "地图清楚，但还要看 PA 能不能下手".
