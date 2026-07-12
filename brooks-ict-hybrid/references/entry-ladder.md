# Entry Timing Ladder（入场时机三层）

Source policy date: 2026-07-10 (Screen Presence). Loaded on live give-plan for **sweep-reversal / MSS-class** setups. With-trend continuation (Trend H2/L2, range-edge fade, breakout-pullback/三买, D1 with-trend pullback limit) uses Entry Mechanics + cycle playbook — **do not force this ladder**.

Live answers speak desk Chinese only（挂深位限价 / 等 M1/M5 收盘破冻结价 / 已确认但不追）. Internally name the tier; do not dump Tier labels unless user asks 复盘.

**Which tier to speak first (this desk):**

| Presence | Speak first | Second line |
| --- | --- | --- |
| On-screen / 填单档 / 小级别 | **Tier 2**: confirmed + market gates pass → market; otherwise event condition/stop | No second entry expression |
| Off-screen / 挂着走 | **Tier 1** deep limit | “若盯盘改走小级别序列”一句即可 |
| Unknown | Infer from whether the user is actively watching; choose one path | Never publish two live orders in one response |

Tier 1 is **not** a better entry than Tier 2 for this user — it is the unattended substitute. Calibration: cases 10–12, 7/3 NAS long, 7/3–5 ETH/XAU journal; Fable 2026-07-10 digest.

## Core

Bare MSS/CISD is a **confirmation / management event, not an entry by itself**. A complete Tier 2 sweep → reclaim → event-defined frozen-price close is an executable sequence.

- Waiting for M15/H4 confirmation close before entry = systematically late.
- Entering without a legal path below = 赌信号 (root cause of 07-06 cluster losses).

Only three legal layers for sweep-reversal class. Decide tier internally before speaking.

## Tier 1 — Post-sweep deep limit（earliest; only pre-MSS path with replay support）

All four hard preconditions; missing any → demote:

1. **Sweep complete:** price traded through the frozen liquidity level and the entry TF closed back inside it — do not pre-enter “it should sweep.”
2. **Deep structural POI:** prior swing / swept level / OB / FVG edge; if two zones, take the deeper; shallow convenience retrace does not count.
3. **HTF alignment:** not `counter_htf`, not `counter_d1`, cycle gate allows (sweep of high inside a channel = continuation, not reversal).
4. **Stop passes all three constraints:** outside the sweep extreme by buffer, distance `≥0.5×ATR(entry TF)`, and outside unfinished stop-side liquidity. Never tighten into noise to inflate R.

All four true → place limit at deep zone. **No MSS required.** No fill is method cost, not a chase license.

**Level provenance (2026-07-10, binding):** the deep zone must be judged by the user or the desk on **raw bars**. Raw scanner `entry_ref`/POI copied into a pending order is banned — replay audit: unfilled scanner limits ran to DOL 89% of the time while filled ones stopped same-bar 65% (adverse selection). A desk-revalidated level (structure named, stop geometry checked against entry-TF bar range) is legal.

## Tier 2 — M1/M5 full turn sequence（early confirmation; LTF predecessor of MSS）

**This is the on-screen default path.** CISD/iFVG/OB may describe the sequence, but the executable decision comes from frozen prices and closes.

All three steps required:

1. Price trades beyond a previously frozen liquidity level.
2. The same entry TF closes back inside that liquidity level.
3. M1/M5 **closes** through the event-defined frozen structure price.

Wicks and single-bar appearance never decide the order. Once the sequence is complete, choose exactly one expression: objective market entry when its gates pass, otherwise a pending stop beyond the confirmation-bar extreme.

**触发语法（唯一版本 — 2026-07-12i）：主观判定词禁止进入订单合同，判定只认事件、冻结价和收盘价。**

以做空为例（做多完全镜像）：

1. 上级做空前提已成立（周期态 + 位置 + closer side）。
2. **事件唯一决定冻结价，不得二选一**：
   - MSS：使用被该次 MSS 收盘突破的 confirmed swing；
   - CISD：使用被该次 CISD 收盘突破的 delivery open；
   - MSS+CISD：使用后发生确认事件及其对应价格。
   事件形成后写下单一数字，禁止改用另一个结构价。
3. 入场 TF **收盘价低于冻结价** = 确认；影线不算。
4. 屏前先检查市价合同；全过则按现价成交，任一不过才从下一根起在确认 K 低点下方挂 sell-stop。
5. 硬损先取 `anchor=max(本次序列最高点, 止损侧未完成等高/旧高/POI上沿)`，再放 `anchor + buffer`（多单镜像；仍受止损三约束）。
6. **订单 TTL：6 根入场 TF K 未成交自动撤单**（这是订单层规则；计划层作废仍遵守 Pending Order Lifecycle 的事件式语义，两层别混）。
7. 未成交前，入场 TF 收盘重新越过冻结价 → 立即撤单。

**四种动作，没有第五种**：收盘未破 = 没有订单；屏前已确认且市价条件全过 = 现在市价；已确认但任一市价条件不过 = 确认 K 极值外 stop；已确认且用户明确不要追 = 刚破的冻结价挂回测 limit（见下方明码标价）。

**已确认事件优先级（防回退）**：当原始 bar 已经给出事件类型、冻结价和确认 K 时，步骤 3 已完成。桌面按顺序三选一：
- **market first（屏前）**：人在屏前；现价仍在确认 K `[low, high]` 内；空单现价 `< 冻结价`、多单现价 `> 冻结价`；尚未越过确认 K 触发极值；管理位距离 `≥1×ATR` 且净 RR 过门。条件全过必须直接市价，不得仅因“挂单更稳”降成 event stop。
- **event stop**：任一市价条件不满足，下一根挂确认 K 极值外 stop。
- **retest limit**：仅用户明确说不要追时可选，且仍受下方已定价限制。
不得再发明反抽区、受压区、回踩条件或第二冻结价，也不得自动切换到 struct/FVG limit。若平台 tick size 未知，触发价写“确认 K 极值外一跳”，不要编小数。

**单订单约束**：市价、event stop、retest limit 三者每回合只选一个。选市价后禁止再给“反抽加仓/更舒服再加/备用 stop”；该市价已是本次事件主单。市价成交后不再适用 pending TTL/穿回撤单条款，也不得临时增加收盘软退出，除非入场前已经明确锁定。

**市价止损算术必须外显**：先列 `anchor`、`buffer`，再算 `SL`。空单 `SL=anchor+buffer`，多单 `SL=anchor-buffer`；报价精度需要取整时只能向结构外取整。成交后不再给取消/失效线。到管理位减仓；若移损，只能移到新确认结构外加 buffer，不能直接移到 entry。

**输出合同（硬规则）**：live 禁止用主观判定词代替订单条件。pending 计划必须给全 **TF、事件类型、冻结价、触发价、硬损、有效根数、撤单价**；市价计划必须给全 **TF、事件类型、冻结价、现价、确认 K 区间、硬损、管理位、主目标**。缺字段 = 非法输出。形态强弱只能写在解释里，永不构成放行条件（`signal_bar_quality` 零结果，07-11）。

**回测 limit 与 CE 的明码标价（2026-07-12 两份 M5 重放，见 execution-gates 证据表）**：
- **破位价回测 limit**：总样本成交率约 80%，成交后胜率较低并有 8-12% missed alpha；不同切片有小幅好坏，均未达到 0.15R 改规则门槛。它买到的是不追价和纸面 RR，不是期望优势。可用，但**cisd-only 事件不给此选项**。注意：limit 挂在破位价上时「收盘穿回撤单」条款多数情况下空转——价格收回去之前通常先成交。
- **FVG/iFVG CE 限价**：总样本没有显示稳定改善，**不是** event_stop 的等价触发，**不自动获得 mgmt2r**，只能在序列确认后当可选改善价格订单。裸 CE 任何 TF 都不是入场。
- **软出场（阵列/结构被收穿即退）**：没有显示稳定改善，不设为默认；只有入场时明确锁定，持仓后才执行。

**LTF PD arrays — where FVG / iFVG / OB / MSS plug into the three steps（2026-07-10e）:**

- **Step-2/3 描述证据：** displacement/FVG 可以描述突破形态，但不是额外机械门；没有 FVG 不会否决已经完成的冻结价收盘突破。M1/M5 MSS = step 3 的同义事件，不用再等 M15 MSS。
- **入场精化（改善价格的可选项，不是首选 — 2026-07-12 降级）：** 序列走完后，可在 displacement 留下的 FVG / 发起 OB / 翻转 iFVG 挂回踩限价改善价格，但 M5 重放没有显示 CE 限价相对确认 K 极值 stop 的稳定优势。「入场更深 → R 更高」只描述纸面 RR，不代表期望更高。**在 pending 表达内部，默认仍是确认 K 极值 stop**；屏前已满足市价合同则先市价。限价版不自动获得 `mgmt2r`。回踩不来 = 方法成本，不降价追。
- **失效判定：** 入场依据的 FVG/OB 被 M1/M5 **收盘**穿透（变成 iFVG/失效 OB）→ **撤未成交单**；已成交仓位默认以硬损为准。只有入场时明确锁定了 array 软离场，才按其 TF + 收盘价执行。反向收穿对手 array 只能作描述证据，不额外放行。
- **纪律不变：** 单独一个 LTF FVG/OB 不是入场（那是赌区）；必须先有 step 1 扫荡。机械定义见 `smc-mechanical-definitions.md`。

**Stop (two-stage, not “noise 3-tick”):**

1. **At entry (default):** choose the outermost stop-side anchor first: short `max(sequence high, unfinished equal/old high, POI upper edge)`; long uses the mirrored minimum. Then place SL one full buffer beyond that anchor. Example: old high `1.13835`, ATR `0.00080`, buffer `0.00020` → short SL at least `1.13855` before spread rounding. Distance must also be `≥0.5×ATR(entry TF)`. Size down for width; never shrink stop to inflate R.
2. **Tight-stop variant:** only a newly confirmed M1/M5 swing may replace the sequence extreme, and only when it independently passes all three stop constraints. It is never anchored to an unconfirmed wick.
3. If any constraint fails → keep the original structural stop or do not trade.

**Targets from fill:** near practical level = 主目标; far HTF DOL = runner only if HTF aligned. Counter-HTF: bank near only (cases 10–11).

**Trigger reading: desk-led by default (2026-07-10c, 2026-07-12i user ruling):** when the user is on-screen and asks about a symbol, the desk pulls M1/M5 raw bars and judges the sequence. If unconfirmed, hand over the complete event condition; if confirmed, apply market-first routing and use event stop only when a market condition fails. Do not wait for the user to read it themselves; user self-triggers remain equally legal. Whether desk reads beat manual reads is an open question — journal every close with `--source desk|user|a_watch` and refuse the comparison until ~30 per bucket. If a legal sequence fills, desk does not re-argue entry quality; immediately bind the three brakes (execution-gates §3 / §5).

`counter_htf` candidates may enter no earlier than this tier, and only to **near** liquidity (scalp management — no far DOL runner).

## Tier 3 — M15/H4 MSS/CISD close = management event

When it prints, first measure remaining distance confirmation → near DOL vs ATR.

- **Already in** (via Tier 1/2) → partial / protect signal.
- **Not in** → descend to M1/M5 and run the frozen-price grammar; the M15/H4 close itself does not authorize a market or automatic limit entry.
- **Market-chasing the confirmation close is always illegal.** No retest → missed-alpha flow.

## 赌信号 — mechanical ban list

All forbidden:

- Pre-entry before sweep completes
- Single-bar reaction without Tier 2 three-step sequence
- Tight stop stuffed into noise for high R
- Counter HTF / counter D1 demanding Tier 1 treatment
- Demoting tier after a losing streak to “make it back”

**Exemption:** whitelisted M1 sweep V-reversal scalp (single-bar reject entry) per `trade-class-contract.md` — not bound by the three-step sequence.

Demotion / illegal path = execution deviation; name it once in the answer when it happened (user or desk).

## Interaction with CONDITIONAL_READY

See `execution-gates.md`. CONDITIONAL missing MSS/CISD → default is **等触发计划 only**, unless Tier 1 (all four) or Tier 2 (full sequence) is already true on raw bars. A lone strong signal bar does not rescue the candidate.
