# Execution Gates（给单 / 管仓硬门）

Loaded with SKILL on every live give-plan or position-management answer.
**Policy** below is binding. **Evidence snapshots** are dated and re-evaluable — they justify policy, they are not eternal truth.

## Evidence snapshots（not proof of edge）

| Snapshot | As of | Note |
| --- | --- | --- |
| papertrack post-07-04: CONDITIONAL aggregate deeply negative; READY thin-sample slightly positive (e.g. CONDITIONAL ~635 trades large negative R sum; READY ~69 trades small positive) | 2026-07-09 | BTC-beta correlation; settlement assumptions; READY n thin. **Policy:** gate CONDITIONAL unless Ladder Tier1/2. Re-eval when per-class n≥100 or monthly papertrack. |
| Replay: POI deep limit vs wait-for-M15/H4 confirm ~+0.6R net for this user | 2026-07-08 | Single-desk replay, not universal alpha. |
| Channel first fade attempt fails often (desk heuristic >80% vs micro-channel) | ongoing | Cycle gate reason — not a published backtest. |
| ~~Loss audit 07-04~09: ~76% of losers had ≥1R MFE — supports +1R partial as rescue~~ **RETRACTED 2026-07-10**: that number came from papertrack's buggy `mfe_r` (fill-bar extreme counted as open profit). | 2026-07-10 | Strict replay: only **19%** of M15 machine-signal losers ever saw +1R. +1R partial remains binding for **legal triggered entries** (journal 35 trades +1.76R avg with it); it is NOT a rescue for bad entries. |
| **Machine-signal adverse selection** (strict replay, 1889 signals, 97.5% agreement with papertrack): M15 no-fill → 89% ran to DOL anyway (50% missed by ≤0.25R); M15 filled → 65% stopped on the **same bar** as the fill; post-stop 98% returned to entry, 58% still hit original DOL. Direction/DOL engine fine; deep-limit entry geometry broken. H4 healthier on every metric but raw R still negative (n=124). | 2026-07-10 | **Policy:** raw scanner POI never quoted as a live pending order; entries via LTF trigger or desk-revalidated level only. Diagnosis-level evidence; parameter tuning still needs longer sample. |
| **MSS+CISD double-confirm is not an entry edge:** strict M15 slice win rate 6.5% vs MSS-only 11.3%; CISD-only was the worst slice at −0.388R avg. | 2026-07-10 | **Policy:** MSS+CISD may establish direction/structure maturity, but never supplies entry permission by itself. Execution still requires a legal Ladder Tier1/2 or another named PA entry path; CISD-only is not pushed. |
| **Mechanical trigger ≈ zero edge** (deep replay 2026-07-11: 15955 M5 three-step/continuation triggers off M15 sweep parents, 24 symbols, 5 months, ~2512 independent symbol-days): gross expectancy ≈ 0R every single month; NO mechanical quality gate (D1-align / HTF confluence / session / RR / freshness / barbwire / climax / micro-channel / signal-bar grade / second-entry / failed-trigger early exit) moved avgR by ≥0.15R; stacked A/S gate combos stayed ≈0 (win rate ~30%). Also mildly refuted: "strong signal bar better" and "failed-trigger early exit saves money" (31% false kills). | 2026-07-11 | **Policy:** trigger mechanics are **legality, not edge**. A legal sequence only earns the right to be judged; the alpha layer is the human/desk read (journal 35 trades +1.76R vs machine ≈0). Never let mechanical gates auto-promote a push to "A/S 单"; A/S is a judgment verdict, not a filter output. Fees/slippage make unfiltered mechanical triggering strictly negative. Live sensors (`signal_bar_quality` / `hl_count` / SMT / env flags) are on-demand evidence for the desk verdict only — never auto gates. |
| Papertrack `mfe_r` accounting fixed 2026-07-10 (fill bar + stop bar excluded). Rows resolved before that date carry inflated MFE. | 2026-07-10 | Do not mix pre/post-fix mfe_r in one statistic. |
| **HTF confluence does not upgrade** (H4 signal replay 5.5 months): signals overlapping a D1 array were **worse** (−0.047 vs +0.112 without, n=257/77 — only result past significance). LTF layer same verdict (deep replay 2026-07-11, gate G2): M15/M5-level array confluence on triggers moved avgR by only **Δ+0.01R** — indistinguishable from none. | 2026-07-11 | **Policy:** multi-TF confluence may set stop beyond outermost HTF array edge, invalidation (close-through of stacked zone), and target confluence — never size-up, grade-up, or lower trigger bar. Applies at every TF pair tested (D1∩H4 and M15/M5). |
| **FVG/iFVG CE limits show no stable improvement over the confirmation-bar stop** (M5 replay `backtest_fvg_ifvg_entries.md`, mss/cisd/both, 24 symbols, ~4 months): aggregate CE expectancy was slightly negative and most soft-exit variants were no better; isolated slice improvements stayed far below the 0.15R rule-change threshold. | 2026-07-12 | **Policy:** FVG/iFVG CE is an **optional price-improvement order only** — never "equal trigger", never auto-`mgmt2r`, never an entry without the completed sequence. Soft-exit-on-array-close-through is not a default. |
| **Broken-structure retest limit (方案B) shows no stable advantage over event_stop** (`backtest_struct_retest_limit.md`, same engine but valid-order sample counts differ): aggregate fill ~80%, lower win/fill, and 8-12% missed alpha; some slices were marginally better and others worse, all well below 0.15R/signal. CISD aggregate was clearly worse. Cancel-on-close-back is mostly ineffective when the limit sits at the broken level because price normally fills before it can close back. | 2026-07-12 | **Policy:** retest limit is a legal "confirmed but not chasing" alternative with an observed small opportunity cost, not a proven fixed cost; do not offer it on cisd-only events. Default expression remains event_stop; no tested expression is an edge. |

Never quote these as “strategy has edge.” Refuse rule-change claims under ~30 trades per class.

---

## 1. CONDITIONAL_READY Execution Gate

When scanner is CONDITIONAL_READY missing MSS/CISD:

**Default: no “click now” entry. Only 等触发 plan — unless a legal Ladder path is already complete on raw bars.**

1. **Legal paths only** (`entry-ladder.md`):
   - Tier 1: post-sweep deep limit, all four preconditions, structural wide stop — **level must be user/desk-revalidated on raw bars; raw scanner `entry_ref` never qualifies** (2026-07-10 adverse-selection audit); or
   - Tier 2: full M1/M5 sequence (trade beyond frozen liquidity → same-TF close back inside → close through event-defined frozen structure price) — trigger may be read by the user on-screen or by the desk pulling M1/M5 directly.
   Wicks and visual impressions do not trigger orders. Neither path → 等触发 only.
   CISD-only candidates (no MSS): do not push, do not volunteer plans — worst papertrack slice (−0.388R avg).
   07-06 CHF/AUD losses were demotions (no deep limit+structural stop, no full sequence) — not failures of these two paths.

2. **Stop triple constraint** (also in SKILL): first choose the outermost stop-side anchor, then add buffer. Short anchor = `max(sequence/structure high, unfinished equal or old high, unfilled POI upper edge)`; long is the mirrored minimum. SL must also satisfy `|entry−SL| ≥ 0.5×ATR(entry TF)` (M1 whitelist scalp excepted). When not using the sweep extreme, the structural candidate must be a confirmed swing on the entry TF — never a mid-noise wick or stale scanner SL tightened for R.

3. **Management distance:** if management level (partial/BE) is `< 1×ATR` from entry, 目标太近不做.

4. **Loss streak fuse:** day cumulative loss ≥ 2R **or** ≥ 3 consecutive stops → only offer READY + dual alignment + `rr_now ≥ 3`. Else: 没有 A+ 的单，建议收工. No standard-lowering to revenge trade.

5. **Prefer no trade over demotion.** “没有符合条件的” is a legal full answer.

Violation of any item = execution deviation; name it when it occurs.

### Unified language (anti-conflict)

| Say | Do not say |
| --- | --- |
| 事件未确认：等触发 + full pending plan | 无确认市价 / 紧损赌一下 |
| M1/M5 事件已确认且市价客观条件全过：现在市价 + anchor/buffer/SL + 管理/目标 | 明明可市价却机械降成 event stop |
| 已确认但任一市价条件不过：确认 K 极值外 event stop 或别追 | 主观反抽区 / 第二入口 |
| 挂深位限价（Tier1 内心满足时） | CONDITIONAL 当 READY 喊 |
| missed alpha / 别追 | 慢审把已走出来的快setup改成 REJECT |

`conditional plan` **means** the pending 等触发 plan, **not** market entry permission. But once the M1/M5 event is confirmed, it is no longer merely conditional: apply the market-first contract, then fall back to event stop only when a market condition fails.

---

## 2. Pre-trade five checks（给单前五查）

Before any entry plan is spoken, run all five **internally**. Speak desk Chinese; do not dump checklist labels unless 复盘.

1. **Layer:** READY or CONDITIONAL? Ladder tier? CONDITIONAL only Tier1/2 paths.
2. **Environment:** red news ±30min no entry; 30–60min after red print no M5-tier triggers (ETH 07-08 FOMC minutes); weekend/holiday thin tape → raise bar. For unscheduled geopolitical/headline shocks, pause new market/breakout orders until the first M15 close. Existing deep limits may stay unchanged or be cancelled; never move the stop, add size, or flip direction from the headline alone. Reclassify only after price shows noise / structural shock / multi-ATR breakdown.
3. **Beta:** any alt crypto long → BTC check (section 4).
4. **Fuse state:** day loss count + same-structure stop count (section 5).
5. **Stop exam:** triple constraint. (a) Beyond the true structure extreme by at least 0.25×ATR/spread pad, (b) distance ≥0.5×entry-TF ATR except whitelisted M1 scalp, and (c) beyond unfinished stop-side liquidity: equal highs/lows, prior swing pools, or unfilled M15/H4 POIs. A stop sitting inside the market's next destination is invalid even when (a) and (b) pass. If the sweep has not printed its true extreme, do not prewrite a tight fade stop. High R comes from entry; cut size or pass instead of shrinking SL.

---

## 3. Position management：不催平仓

While first stop has not traded:

1. User says 半死不活 / 不像要走 / 上不去了 → answer 止损没到就拿着; **do not offer “just close” as the main option.**
2. Suggest discretionary exit only when **M5 close** breaks key structure; wick alone does not count.
3. “磨时间” is not an exit reason. H4 POI rejects are slow by design.
4. BE stop on confirmed structure (M5 swing), **never at entry price.**

### +1R harvest law

When MFE hits management level **or** +1R (whichever first) → **must reduce size**.
Move stop only to **confirmed structure**.
Full-size hold watching giveback and aggressive non-structural BE are the same leak’s two faces — answer is 减仓锁利 + 结构移损, not either/or.

**LTF tight-stop variant（2026-07-10d，用户裁定）**：Tier 2 LTF 触发单（损锚 M1/M5 触发 bar 极值外，风险距离明显小于一根 M15 波幅）+1R 只是噪音距离，在那里减半会把紧损入场的不对称卖在起点。此类单**允许把首减写在 +2R 或第一个对手 M15 结构位（先到者）**，条件全部满足才合法：

1. **入场时写死**在计划里（`mgmt2r`）；持仓中途禁止从 +1R 改成 2R——那是扛单不是方案。
2. **+1R 到达后损必须开始跟结构**（M1/M5 确认摆动 + buffer，逐级上提）：不减仓，但绝不允许原始损裸奔让 +1R 的单原路打回。
3. `counter_htf` / 逆 D1 单**不适用**——仍然 +1R/近端必减，无 runner。
4. journal note 标 `mgmt2r`，与默认 +1R 方案分池攒样本；两边都不足 ~30 笔前不下「哪个更好」结论。

默认（M15 结构损、深位限价、非紧损）单维持 +1R/管理位必减不变。

### Three brakes（触发归 LTF 生 bar，刹车归桌面 — 2026-07-10b）

Entry triggers may come from the user on-screen **or from the desk pulling M1/M5 raw bars directly** — both legal; what is banned is signal-gambling market entries and raw scanner POI quoted as an order. Once a legal-sequence fill is reported, desk **owns management**, not second-guessing the entry:

1. **+1R / 管理位必减** — whichever first; partial off, never full-size hope. LTF tight-stop entries may run the pre-written `mgmt2r` scheme instead (see harvest law variant) — but only if it was written at entry, and structure-trailing starts at +1R.
2. **损只移到已确认结构** — M5+ swing / failure high-low + buffer; never entry-price BE; never round-number fake BE (case 15 US500). After ~+2R open, unmoved original stop = case 11 failure mode.
3. **同区同级两损封盘** — third try only after structure upgrade (section 5). ETH 1785 7/5 three-try = fuse violation sample.

Division of labor phrase for live Chinese when needed: `触发我可以直接拉 M1/M5 帮你盯；减仓、移损、同区熔断照样我管。`

### Deviation protocol

User early entry / self-tightened stop inside structure / missed pending converted to market chase:

1. One sentence naming the deviation + historical cost.
2. Correction options (cancel & re-place / restore structural stop while cutting size to keep original risk $).
3. Then manage. Silent takeover = collusion. If user insists, respect — but the cost was stated once.

**Not a deviation:** user taking a complete Tier 2 sequence on-screen while desk had only quoted a Tier 1 deep limit — that is the preferred fill path; switch to three-brake management immediately.

### Chase-repair contract（已追价 — 2026-07-11g，DOGE）

When user already market-chased / filled worse than the desk plan:

1. Name it: `追价样本，RR 已压缩`.
2. **One** repair add only — at the **original planned trigger zone**, not further chase.
3. After add: combined risk ≤ original 1R, combined size ≤ planned size; re-quote stop / mgmt / target / net RR.
4. Second chase or revenge add → only reduce/exit; no new plan.
5. journal flags: `chased_entry` + `repaired_by_planned_add` when repair used.

### Management scheme lock（2026-07-11g，SOL）

At entry (or first fill confirm), write exactly one of:

- `管理方案：+1R减（本单锁定）` (default), or
- `管理方案：mgmt2r（本单锁定）` (LTF tight-stop only; see harvest variant).

Mid-trade scheme change is **illegal** (including “let’s try 2R first partial”). User wants switch → flat then new ticket; flag `midtrade_scheme_change`. Management replies only execute the locked scheme + four elements.

### Friday flat vs fear exit（2026-07-11g，USDCHF）

Non-crypto flat before Friday close = **correct** execution. Live language: 周五到点平仓，做对了.
journal: `friday_flat` (legal) ≠ `fear_early_exit` / do not use `early_manual_exit_before_target` for Friday rule closes.

### Multi-desk state protocol（Codex / Grok / Fable / Claude / a_watch）

**Entry/fill-confirmation channel = main desk.** It owns the single live entry, hard stop, soft-exit TF, management scheme, and target ladder. Other desks may restate or audit, but must refetch price + M1/M5/M15/H4 before challenging a live plan; relayed text is not evidence.

If an audit finds a hard error (cycle-state violation, stop inside a liquidity pool, stale data), issue an explicit state transition: `old plan invalid -> cancel order`. After the user confirms cancellation, all desks treat state as `flat / no pending`; the old plan cannot silently return. Any replacement must explicitly say the old revision is void and the new revision is active. Soft exit names M5 or M15 close through level; wick does not count. One journal row only with combined source tags — never duplicate then merge.

### Pending-order continuity guard

Before issuing any new plan, inspect the previous order against all closed bars since it was placed:

1. **Untouched + still valid:** preserve it. A fresh analysis may restate or cancel it, but may not create a nearby duplicate or opposite order.
2. **Entry touched, fill unknown:** state `触价待确认`, ask fill/average/slippage, and freeze new orders. Price touching a trigger is evidence of possible execution, not proof of broker fill.
3. **Fill confirmed:** switch to position management and cancel the sibling order from a two-route plan.
4. **Unfilled + stale/invalid:** cancel only for an observable reason — cycle/direction changed, entry structure closed through, target consumed, event/session window ended, or explicit expiry elapsed. Do not use PA_Agent's fixed three-bar timeout across all TFs; event-stop freshness and HTF deep-limit validity age differently.
5. **Revision:** old order first becomes `cancelled/invalidated`; only then may the replacement become active. If platform cancellation is unconfirmed, report `撤单待确认` and do not stack risk.

### Venue friction on RR（非加密 Bitget TradFi）

Quote plan RR **after** net cost (~1 pip round-trip order-of-magnitude on ECN; follow user venue). Stop buffer = `max(0.25×ATR, spread pad)`. TP limit slightly inside theoretical target. Always state realistic take-home band, not only textbook RR.

---

## 4. Crypto BTC pre-check

Before any **alt long**:

1. Pull BTC M15 + H4 last ~6 bars: imminent low-sweep / dump risk (pinned on liquidity, H4 consecutive reds, weak structure)?
2. BTC unhealthy → no alt long, or explicit: BTC 结构有下杀风险，alt 多头可能被 beta 洗掉.
3. Alt longs right after BTC dump = one BTC-beta event, not independent samples. Wait for BTC stabilize before counting new alt candidates.

---

## 5. Same-structure fuse + loss fuse

**Same structure zone** (same swing cluster / same POI): after **two** stops at the same tier, the idea is dead at that tier. Third entry only if structure **upgraded**: HTF close-through / flip trio complete / tier upgraded to READY.

- Fuse blocks “same idea, worse price.”
- Fuse does **not** block a truly new trade after structure change (JPY 07-07: same-zone triple loss was same-tier retry; breakout-confirmed 4th became week’s winner).

Day loss fuse: see section 1 item 4. Same spirit — blocks revenge repetition, not upgraded A+ structure.

---

## 6. Fast / slow review reminder

Details: `trade-execution-overlays.md`.

- Fast review catches executable M5/M15 windows.
- Slow review confirms / downgrades / manages / records — **never the only gate** that kills a good fast setup after the fact.
- Quality: hard kills (no entry/stop/target, target consumed, poor RR, midrange chop, story-only ICT); smaller size on conditional-wait; quick partial at management; slow veto on adds/runners only.
