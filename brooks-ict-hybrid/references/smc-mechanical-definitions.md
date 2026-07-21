# SMC Mechanical Definitions

Precise, deterministic definitions for the ICT/SMC primitives this skill already uses.
Distilled from the `smartmoneyconcepts` library (joshyattridge, v0.0.27).

## What this file is for

This is a **definition standard**, not a second engine.

- Use it to keep one consistent meaning for FVG, swing, BOS/CHoCH, OB, liquidity, PDH/PDL, sessions, and retracement when reading raw bars.
- It sharpens the **location / structure** half of the skill only. It does **not** change the Trader Identity Contract, the one-main-plan rule, target layering, or desk tone.
- It does **not** authorise a trade. PA still decides the action. The local scanner (port 8001) remains the mechanical detector; do not run a parallel detection pass that competes with it.

## Anti-hallucination guardrail (read first)

Most of these definitions need **future bars** or a **confirming close** before they are real. The confident-looking pattern on the latest bar is usually the provisional one. Before stating any of these as fact:

- **Latest swing is provisional.** `swing_highs_lows` needs `swing_length` bars *after* the candle to confirm it. The most recent swing high/low is not confirmed yet; call it "potential" until enough bars pass.
- **BOS/CHoCH is not real until a candle closes through the level.** A wick through the level is not a break. No confirming close = no structure break, no matter how clean it looks.
- **FVG / OB can already be mitigated.** A gap or block that price has traded back into is spent. Check mitigation before treating it as fresh.
- **Equal highs/lows are a target, not a trigger.** Liquidity resting above/below is a magnet, not permission to enter.

When a mechanical read is provisional, say so. Do not upgrade "potential CHoCH" into "CHoCH confirmed."

## Every mechanical signal must still pass the binary decision tree

This file feeds the tree; it never bypasses it. The `Invisible Binary Tree` in `SKILL.md` and `references/pa-agent-binary-decision-tree.md` are the anti-hallucination spine and stay in force. Map each primitive to the node it serves, then let the tree gate it:

- FVG / OB / PDA quality -> Node 2 (Location)
- Sweep of liquidity / BOS / CHoCH / reclaim -> Node 3 (Trigger)
- Swing level / OB edge / PDH-PDL -> Node 4 (Stop / invalidation)
- Liquidity pool / PDH-PDL / session high-low -> Node 5 (Target room)
- Retracement % (premium/discount) -> Node 1 and 2 (is this a discount buy / premium sell, or chasing)

A primitive that fires but fails its tree node is evidence, not a trade.

## The primitives

### FVG - Fair Value Gap
- **Definition:** a 3-candle imbalance. Bullish FVG when `high[t-1] < low[t+1]` and the middle candle is bullish (close > open). Bearish FVG when `low[t-1] > high[t+1]` and the middle candle is bearish. `Top` and `Bottom` are the gap edges.
- **Mitigated** once a later candle trades back into the gap (bullish: a low <= Top; bearish: a high >= Bottom). A mitigated FVG is spent.
- **Maps to:** PDA / FVG zone -> Node 2 Location. A zone where a signal can matter, never a trade by itself.
- **PA gate:** only matters with displacement into it and a PA trigger on the return. Unmitigated + with follow-through = usable; mitigated or in overlap = discard.

### Swing Highs / Lows (`swing_length`, default 50)
- **Definition:** swing high = highest high over `swing_length` bars before and after; swing low = lowest low likewise. Output alternates strictly high/low/high/low (the more extreme of consecutive same-type swings is kept).
- **Confirmation lag:** needs `swing_length` bars *after* the pivot to confirm. The latest pivot is provisional.
- **Maps to:** structure points -> Node 4 Stop (invalidation behind a swing) and the input for BOS/CHoCH, OB, liquidity, retracement.
- **PA gate:** use confirmed swings for stop placement. Do not anchor a stop to an unconfirmed latest pivot and call it structural.

### BOS / CHoCH (Break of Structure / Change of Character)
- **Definition:** read off the last four alternating swings.
  - **BOS = continuation:** structure breaks in the direction it was already going (bullish: higher high taken out inside an up-sequence; bearish: lower low taken out inside a down-sequence).
  - **CHoCH = reversal:** the **first** counter-trend break (bullish CHoCH = first higher high after a down-sequence; bearish CHoCH = first lower low after an up-sequence).
- **Only confirmed on a CLOSE through the swing level** (`close_break=True`). Unbroken structure breaks are discarded entirely. `BrokenIndex` is the candle that confirmed it.
- **Maps to:** trigger candidate -> Node 3 Trigger. In PA terms: BOS = trend continuation break; CHoCH = first sign of character change / possible reversal.
- **PA gate:** valid only with a confirming close, a real stop, and target room. A wick-only "break" is not a trigger. CHoCH against a strong Brooks trend with deep follow-through is suspect — downgrade. Timeframe split (`references/entry-ladder.md`): an M1/M5 confirming close is a Tier 2 entry trigger; an M15/H4 confirming close is a confirmation/management event, never a fresh market entry.

### OB - Order Block (needs volume)
- **Definition:** bullish OB = the down candle with the lowest low immediately before a close that takes out the prior swing high; bearish OB = the up candle with the highest high before a close that takes out the prior swing low. `Top`/`Bottom` are that candle's range. `OBVolume` = sum of its and the two prior volumes; `Percentage` = relative strength.
- **Breaker:** an OB that price violates flips role (failed OB -> breaker), consistent with the skill's existing `Breaker` concept.
- **iFVG (inversion FVG):** an FVG that price CLOSES through flips role — a bullish gap violated on a close becomes resistance interest, and vice versa. Same family as the breaker; in Brooks language: failed level becomes the other side's magnet. Evidence tier: concept-consensus, zero independent backtests (post-2023 ICT vocabulary) — a location marker only. Desk use: a violated FVG is not dead, it is flipped — a failed retest AT the flipped zone is a trigger candidate, but only through the full sequence; an iFVG alone is never a trade.
- **Maps to:** PDA / OB zone -> Node 2 Location; OB edge -> Node 4 Stop.
- **PA gate:** OB is a zone where a signal can matter, not an entry. Requires displacement that created it plus a PA trigger on the retest. Needs a volume series; if volume is missing or unreliable for the symbol, treat OB as lower-confidence and lean on FVG / swing structure instead.

### Liquidity (equal highs / lows, `range_percent`, default 0.01)
- **Definition:** multiple swing highs within `range_percent` of the full range of each other = buy-side liquidity (equal highs); multiple lows = sell-side liquidity (equal lows). `Level` = average; `Swept` = the candle that pierced the pool.
- **Maps to:** DOL / liquidity -> Node 5 Target (magnet) and Node 3 Trigger (the sweep + reclaim). In PA terms: equal highs/lows = a draw; the sweep = failed breakout / liquidity test.
- **PA gate:** resting liquidity is a target, not a reason to enter in its direction. The trade is the **sweep failure + reclaim**, confirmed on bars, not the approach.

### Previous High / Low (`time_frame`, e.g. 1D / 1W)
- **Definition:** prior period's high and low (PDH/PDL, PWH/PWL). `BrokenHigh`/`BrokenLow` flip to 1 once price takes them out within the current period.
- **Maps to:** named DOL -> Node 5 Target; also Node 1 HTF bias context.
- **PA gate:** a clean named liquidity target (Five-Gate node 2 in `ict-v16-core.md`). Once broken, it can flip to support/resistance — re-read, do not keep using a consumed level as the target.

### Sessions / Kill Zones
- **Definition:** session windows and kill zones with running session High/Low — Sydney, Tokyo, London, New York, plus Asian / London-open / New-York / London-close kill zones. **Default times are UTC**; convert to the user's session view before quoting.
- **Maps to:** timing context for sweeps and DOL; session high/low are intraday liquidity.
- **PA gate:** timing is supporting context only. A kill-zone window never creates a trade without location + trigger. Do not invent session levels; only use them when the bar timestamps actually cover the session.

### Retracements (premium / discount)
- **Definition:** current and deepest retracement % of the active swing leg. ~50% = equilibrium. Below 50% of the leg = discount (for longs), above = premium (for shorts).
- **Maps to:** premium/discount -> Node 1/2. Discount + bullish bias = better long location; premium + bearish bias = better short location.
- **PA gate:** entering at premium for a long (or discount for a short) is chasing — this is exactly the `do not chase` case. Use retracement depth to confirm the entry is on the right side of equilibrium, not to override a PA `do not chase`.

### Sweep 双类判别 — IDM vs Turtle Soup（2026-07-21，S6/F2）

Sweep 不是一类事件，是两类，方向含义相反。判别键 = **被扫的是哪一级摆动 + 有没有位移**：

- **IDM / inducement（延续燃料）**：被扫的是**趋势回调里的次级/内部摆动点**，且发生在有效 BOS **之前**。这是真行情启动前清掉的燃料——**顺势延续信号，禁止当反转素材去 fade**（通道日接刀的机械形态）。微观证据：Osler 订单簿研究（止损簇触发→cascade 加速延续）；破前日高后 67-81% 当日收阳（延续，非反转）。
- **Turtle Soup（弱反转候选）**：被扫的是**主摆动 / 区间极值**，影线刺穿后**收盘收回区间内**，且**无同向位移跟随**——套牢突破客的失败突破。只有这一类才是反转素材，且原始含量 sub-friction（Mesfin：0.2-0.8pt，bar-close 机械执行 T=-14 必死）——**只能靠 LTF 触发+管理兑现**，永不机械挂深位限价。
- 扫描器打标：`env_sweep_scope = major|internal`（major=区间极值级，internal=内部摆动级）。**记录性标签，不放行不否决**；桌面裁决时 internal 级 sweep 的"反转计划"默认降级。
- 判别不确定时按本文件守则：说"scope 未定"，不硬归类。

### FVG 最小位移门槛（2026-07-21 补充）

- FVG 需 **gap 高度 ≥ 0.2×ATR** 才算有效位移产物；小于该门槛的微 gap 是噪声，不当 Node 2 位置素材（源：OpenMobius kb_klines `min_size_atr=0.2`；LuxAlgo 用"位移K实体≥2×平均实体"同义）。
- **部分缓和度**：价格回补 gap 的百分比可分级（首触近端 / 到 CE 50% / 完全填补三种口径，引用时必须点名用哪种，禁止混用）。

### OB 两段生命周期（2026-07-21 补充，替代单一 breaker 标志）

- **mitigated（被触碰）**：价格首次触到 OB 近端边——OB 已被使用一次，新鲜度降级但未作废。
- **broken（作废）**：**收盘**越过 OB 远端边——OB 失效并翻转为 breaker（对侧兴趣区）。
- 影线穿远端不算 broken（与 BOS 同规矩：收盘才算）。CISD 验证口径：收盘穿越 delivery 序列**第一根** K 的开盘价（非最后一根）。

## Precedence (how this stays conflict-free)

1. **PA decides the action.** These definitions supply precise location, structure, and invalidation only.
2. **The binary decision tree and Five-Gate model are not overridden.** A mechanical signal that fails a node is downgraded, never promoted.
3. **Scanner is the live detector.** This file is the shared meaning of the terms, not a second runtime pass. If a hand read of raw bars disagrees with the scanner, say so and re-check; do not silently run a competing detection engine.
4. **Provisional stays provisional.** Unconfirmed swing, unclosed break, mitigated zone, unswept liquidity — name the uncertainty instead of asserting a clean signal.
