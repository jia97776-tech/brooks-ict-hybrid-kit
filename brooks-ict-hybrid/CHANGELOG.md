# brooks-ict-hybrid CHANGELOG

## 2026-07-12j — stop-scope lock / no post-fill widening / file-position isolation

- Initial stops now declare one scope before entry: `M1/M5 触发损`, `M15 结构损`, or `H4 POI 整层损`. The desk must enumerate every relevant 候选锚 inside that scope before selecting the outermost anchor and adding buffer.
- Clarified relevance: HTF background confluence does not automatically force an H4-wide stop. A remote POI edge enters the formula only when the trade thesis explicitly requires that whole layer to hold.
- Removed the remaining top-level and evidence-table wording that automatically pushed any confluence stop beyond the outermost HTF edge.
- Any omitted relevant anchor or ambiguous stop scope invalidates the pre-fill plan and requires `重新计算 entry / size / management / RR`.
- The initial hard stop is locked after fill. It may remain or tighten behind newly confirmed structure, but it may never widen into loss. A scope/anchor mistake is corrected by reducing or closing; a wider stop belongs to a newly sized new ticket.
- HYPE calibration: `66.45 - 0.04 = 66.41` was arithmetically correct; the pre-entry audit question is whether `66.45` was the correct anchor for the declared scope. After fill, `66.31` cannot be relabeled as a replacement structural stop.
- Added `文件操作 ≠ 仓位操作`: editing, optimizing, reverting, validating, or backing up the skill does not mutate a live position unless the user explicitly names the symbol and position action.
- Closed the remaining pending-order loopholes: every market, event-stop, retest-limit, and deep-limit plan must print stop scope, all relevant candidates, anchor, buffer, and SL before fill.
- Split deviation repair by lifecycle: pre-fill orders may be cancelled and rebuilt; filled tickets may never restore a wider price stop, even after reducing size.

## 2026-07-12i — confirmed LTF market-first routing

- User ruling: market entry is not merely tolerated after a legal M1/M5 confirmation. When the user is on-screen and all objective market conditions pass, market is the first execution choice; event stop is the fallback when any condition fails.
- Removed stale `Pending First` / `event stop default` wording from the loaded policy and entry ladder. Unconfirmed events still cannot be entered at market.
- Kept the one-order contract: market, event stop, or user-requested retest limit, never two simultaneous entry expressions. Switching from on-screen to off-screen requires cancelling the old pending expression before a deep limit replaces it.
- No change to stop triple constraints, outermost anchor arithmetic, management/target layering, or the replay finding that FVG/iFVG limits have no stable expectancy improvement.

## 2026-07-12h — objective live compiler cleanup

- Removed subjective hold/rejection language from preferred live vocabulary and examples. Conditional plans now print TF + event type + frozen price + trigger + hard SL + TTL + cancel price.
- Fixed the event-to-price mapping: MSS uses its broken confirmed swing, CISD uses its broken delivery open, and MSS+CISD uses the later event's price. Desks may not choose whichever level looks better.
- Soft exit is no longer a mandatory management field. It exists only when explicitly locked at entry; array close-through otherwise cancels pending orders but does not override the hard stop on a filled trade.
- Replaced stale dual-stop wording with the full triple constraint in loaded references.
- Narrowed replay claims to what the reports support: no stable improvement and no rule-changing difference, rather than universal underperformance.
- Synced the live compiler with the 07-12g trigger grammar; displacement/FVG is descriptive evidence, not an extra mechanical gate.
- Added confirmed-event precedence after pressure testing: once event type + frozen price + confirmation bar exist, the desk must choose only between the objective market-entry contract and confirmation-bar stop contract; it may not regress to a subjective pullback zone or unsolicited limit.
- User correction: market entry remains legal after a confirmed M1/M5 event when price is still inside the confirmation bar, on the correct side of the frozen price, before the trigger extreme, and management/RR gates pass. Event stop remains the default; subjective pullback zones remain banned.
- Stop geometry made explicit: apply buffer outside the outermost of sequence extreme and unfinished stop-side liquidity.
- Third pressure test hardened market execution: one order expression only; no pullback add-on or backup order after choosing market, no pending TTL/cancel line on a filled market order, and no improvised soft exit. Added an explicit outermost-anchor-plus-buffer calculation example.
- Fourth pressure test made market management arithmetic mandatory: print anchor, buffer, and outward-rounded SL; no post-fill cancellation line; management means partial, while stop movement still requires a newly confirmed structure outside buffer rather than entry-price BE.

## 2026-07-12g — single trigger grammar (方案A) + order-expression price tags

### Why
User ruling after two M5 order-expression replays (`backtest_fvg_ifvg_entries.md`, `backtest_struct_retest_limit.md`): 压住/撑住 stayed subjective even with the zone-based compile rule; CE-limit "preferred" claim (07-10e, amplified 07-12f) refuted by data; struct-retest limit tested and priced.

### Changes
- **entry-ladder.md**: zone-based 压住 compile rule replaced by the frozen-structure-price grammar — freeze one M1/M5 structure price → entry-TF close through (wicks don't count) → stop beyond confirmation-bar extreme from the next bar → sequence-extreme buffered hard SL → 6-bar order TTL (order layer only; plan-layer invalidation stays event-based) → cancel on close back through. Three actions only: no close-break = no order / broken = event_stop (sole default) / confirmed-but-not-chasing = broken-level retest limit (priced, not offered on cisd-only). Output contract hardened: 压住/撑住/强势/干净 are narrative words; live usage must ship TF + frozen price + trigger + hard SL + TTL + cancel price.
- **entry-ladder.md 07-10e paragraph fixed at source**: CE retest limit demoted from "preferred" to optional price improvement (expectancy worse than event_stop, ~−0.02/signal); soft-exit-on-close-through not a default (twice refuted); limit variants never auto-mgmt2r.
- **SKILL.md** version `2026-07-12g`: Entry Mechanics line replaced with the single grammar + three actions; PD-Array CE line downgraded to observation anchor / optional improvement.
- **execution-gates.md**: two new evidence rows — FVG/iFVG CE limits underperform event_stop; struct-retest limit milder but ≤ event_stop everywhere, expression ordering event_stop > struct_limit > fvg_ce, all < 0.15R.
- Synced to Codex and Grok.

### Non-goals
- No new mechanical filters or patterns; no edge claim for any expression (all ≈0R gross). Alpha layer remains zone/cycle selection + desk judgment; journal `--source` sample collection continues.

## 2026-07-12f — 压住 macro: LTF FVG CE limit as equal trigger expression

- User ruling: no reason HTF CE can take a limit while LTF CE cannot. entry-ladder 压住/撑住 compile rule now states the failure-leg displacement FVG **CE(50%) limit** is an equal (and preferred-when-available) expression of the trigger, same stop, deeper entry, mgmt2r-eligible; invalidation = opposing close-through of the FVG.
- Guardrail kept explicit: CE legality comes from the completed sweep→reclaim→close-through sequence, never from TF — naked CE at any TF stays illegal (adverse-selection twin of raw scanner deep limits).
- Synced to Codex and Grok.

## 2026-07-12e — 压住/撑住 de-subjectivized (macro, not verdict word)

### Why
User ruling: 「反抽压住再空 / 回踩守住再多」 was too subjective — TF unstated, wick vs close undefined, no expiry, desks could each mean a different bar.

### Changes
- **entry-ladder.md**: 压住/撑住 compile rule — three same-TF conditions (touch into zone / close back beyond zone edge, wicks don't count / stop order beyond failure-bar extreme with buffered SL), event-based invalidation (close back through zone edge = failed hold, cancel), and an output contract: live use of 压住/撑住 must ship TF + zone + trigger price + invalidation price in the same turn.
- **SKILL.md** version `2026-07-12e`: Entry Mechanics line upgraded — 压住/撑住 is a macro that must expand to the four numbers; bare usage = illegal output.
- Synced to Codex and Grok.

### Non-goals
- No new entry pattern, no edge claim — this is language/legality precision only (mechanical gates remain null-edge per 07-11).

## 2026-07-12d — G2 LTF-confluence evidence restored

- execution-gates.md HTF-confluence row now also records the LTF layer result (deep replay 2026-07-11 gate G2: M15/M5 array confluence Δ+0.01R, indistinguishable) so the no-upgrade rule is explicitly covered at every tested TF pair.
- Synced to Codex and Grok.

## 2026-07-12c — restore double-confirm semantics / three-desk parity

- Restored the live Hard Rule: MSS+CISD double-confirm establishes direction/structure maturity only and never becomes an entry trigger by itself.
- Restored the supporting execution-gates evidence: 6.5% MSS+CISD vs 11.3% MSS-only; CISD-only −0.388R average.
- Reordered the misplaced 2026-07-12 entry and synchronized the complete current skill to Codex, Claude, and Grok.

## 2026-07-12b — upstream source audit: order lifecycle / retrieval conflict / failed-entry magnets

### Why
- PA_Agent source code has a real continuity layer beyond conversational `revision`: it distinguishes untouched, touched, filled, stale, invalidated, and revised plans. The hybrid previously lacked an explicit touched-but-unconfirmed state and could duplicate or misclassify pending risk.
- OpenMobius preserves per-source definition conflicts and its latest asset-consistency review removed six mislabeled duplicate cases. Retrieval count and alias frequency are therefore not consensus.
- PA_Agent's failed signal/entry magnets can improve target management when tied to a concrete bar, without adding a new entry pattern.

### Changes
- **SKILL.md / execution-gates.md:** added a provider-neutral pending-order lifecycle and continuity guard. Fixed three-bar expiry was rejected; expiry is event/TF/plan-window based.
- **openmobius references:** added conflict/provenance guard; duplicate or mismatched cases get zero execution weight and cannot upgrade a setup.
- **Target Method:** concrete failed-entry prices / failed signal extremes may serve as management or near main targets; mechanical measured moves remain runner candidates.

### Non-goals
- No new pattern library, mechanical A/S promotion, fixed three-bar expiry, or automatic case voting.

## 2026-07-12 — stop liquidity / multi-desk state / headline contract / equivalent compression

- `SKILL.md` version `2026-07-12`: stop rule upgraded from two to three independent constraints; added stop-side liquidity-pool/HTF-POI exam and banned prewritten tight fade stops before the sweep prints.
- Replaced Claude/Grok-only wording with a provider-neutral multi-desk state protocol covering Codex, Grok, Fable, Claude, and a_watch: one main desk, live refetch before audit, explicit old-plan invalidation/cancel propagation, revision semantics, and one journal row.
- Split scheduled red-news handling from unscheduled geopolitical/headline shocks. Headline alone cannot flip direction; pause new market/breakout orders until the first M15 close, while existing deep limits may only remain unchanged or be cancelled.
- Conservatively compressed duplicated evidence and repeated Hard Rules from `SKILL.md`; detailed mechanics remain in references. No pattern library expansion.

## 2026-07-11g — collab-desk seams (USDCHF / SOL / DOGE / HYPE)

### Why
User + Grok/Claude collaborative closes (4 trades, +4.59R): management mid-trade scheme wiggle (SOL), chase-then-repair without a contract (DOGE), Friday flat mislabeled as early exit + theoretical RR vs Bitget net (USDCHF), dual-bot plan drift risk + soft-exit TF must match (HYPE trail language).

### Changes
- **SKILL.md** version `2026-07-11g`: 管理方案锁定; 已追价修复合同; Bitget 摩擦进报 RR + `friday_flat` vs `fear_early_exit`; 双通道主桌; Hard Rules +4 bullets.
- **execution-gates.md**: chase-repair / scheme lock / Friday flat / dual-desk / venue friction sections under position management.
- **live-desk-template.md**: locked scheme line + net-cost RR + Friday wording in four-element block.
- **Ops:** `telegram_proxy/grok_upstream.SYSTEM_PROMPT` aligned; skill rsync to claude/codex/grok.

### Non-goals
- No new mechanical filters. No a_watch auto rules in this pass. Sample still thin — no desk-vs-user verdict.

---

## 2026-07-11 — mechanical trigger null-edge + skill hygiene

### Why
- Deep replay (15955 M5 three-step/continuation triggers off M15 sweep parents, 24 symbols, ~5 months): gross expectancy ≈ **0R every month**. No mechanical quality gate moved avgR by ≥0.15R; stacked A/S filter combos stayed ≈0.
- H4∩D1 array confluence was **worse**, not better (−0.047 vs +0.112). Textbook multi-TF upgrade myth rejected on local data.
- Sensors (`signal_bar_quality` / `hl_count` / SMT / env flags) verified as implementation — value is desk evidence language, not auto admit/deny.

### Changes
- **SKILL.md**: version stamp → `2026-07-11`; Hard Rules +3 bullets (跨 TF 重合不升级 / 传感器不当自动门 / LTF 拉取失败禁编触发价). PD Array 分层 + 现场传感器段 already present from 10f/same-day user rulings.
- **execution-gates.md**: evidence table row-merge **fixed** (adverse-selection Note was truncated into the 07-11 mechanical-trigger row); mechanical-trigger and HTF-confluence-no-upgrade snapshots added as clean 3-column rows.
- **Ops alignment (same pass):** Feishu `grok_upstream.SYSTEM_PROMPT` realigned to 07-11 bullets; `a_watch.format_push` no longer brands pushes as edge-grade「A单」— wording is **合法触发候选（待裁决）**; dual mgmt schemes + `--source a_watch` kept.

### Non-goals
- No new mechanical filters. No claim that desk/human journal edge is statistically proven (n still thin). Freeze policy while collecting `--source` / `mgmt2r` samples.

---

## 2026-07-10b — machine-signal audit (adverse selection) + output contract

### Why
- Strict M15 replay of 1889 papertrack signals (97.5% agreement) exposed papertrack `mfe_r` bug (fill-bar extreme counted as open profit): "88% of losers saw +1R" was false — real number **19%**.
- Adverse selection on raw scanner deep limits: unfilled → 89% ran to DOL anyway; filled → 65% stopped same-bar. Direction/DOL engine fine; deep-limit entry geometry broken.
- MSS+CISD double-confirm win rate 6.5% < MSS-only 11.3%; CISD-only worst slice (−0.388R). Scalp leg on machine signals −0.097R.
- Weekly live friction: management answers incomplete (4–8 follow-up questions per position), conditional exits booked as executed, RR not recalculated after SL moves.

### Changes
- **papertrack.py**: `mark_mfe` strict accounting — fill bar and stop bar excluded; pre-2026-07-10 rows flagged inflated. Tests updated, 64 pass.
- **SKILL.md**: version 2026-07-10b; raw scanner POI banned as direct pending order (desk/user must revalidate on raw bars); desk may pull M1/M5 raw bars and hand over triggers itself; MSS+CISD = direction only, never entry trigger; CISD-only not pushed; +1R partial is discipline for legal entries, not a rescue; stop-distance audit warning under Dual Constraint; rule 11 conditional-statement ≠ executed; **rule 10 amended (user ruling): no Friday freeze for non-crypto — trade Friday normally, hard requirement is flat before Friday close**; management reply must carry all four elements.
- **execution-gates.md**: 07-09 loss-audit row RETRACTED (buggy mfe_r); adverse-selection evidence row added; Three brakes retitled (trigger from user or desk raw bars); CISD-only do-not-push.
- **entry-ladder.md**: Tier 1 level provenance binding (raw scanner entry_ref banned); trigger reading shared user/desk.
- **local-stack.md**: symbol quality tiers (A: XAUUSD/XTIUSD/US500 + H4; C: ZEC/EURUSD/US30/PEPE not pushed); `mfe_r` accounting warning; Friday-freeze note clarified as data-fact only.
- **trade-class-contract.md**: machine signals never qualify as scalp; intraday day-end rule = Friday non-crypto flat before close (no freeze).
- **live-desk-template.md**: active-position answers must include all four elements in one shot (hard stop / soft exit with M5-or-M15 close named / partial price / next-bar watch); RR re-quoted after any SL/entry change; price source named.

### Addendum 2026-07-10c — desk-led triggers by default + provenance tracking
- User ruling: on-screen trigger reading is **desk-led by default** (desk pulls M1/M5 itself and hands over the trigger order); user self-reads stay legal.
- "Desk LTF read beats manual" is a hypothesis, not a finding — `journal.py` gained `--source desk|user|a_watch|mixed`; stats bucket by source; no comparison verdict until ~30 closes per bucket.
- Friday rule (same day, user ruling): non-crypto has **no Friday freeze** — normal trading all Friday, hard requirement = flat before Friday close.

### Addendum 2026-07-10d — LTF tight-stop `mgmt2r` variant (user ruling)
- Tier 2 LTF triggered entries (stop at trigger-bar extreme, risk ≪ one M15 bar) may pre-write first partial at **+2R or first opposing M15 structure** instead of +1R.
- Conditions: written at entry (`mgmt2r` in journal note), structure-trailing mandatory from +1R, mid-trade scheme change illegal, counter_htf/counter-D1 excluded.
- Rationale: +1R on a tight LTF stop is noise-distance; halving there sells the asymmetry the tight stop paid for. No data verdict yet — mgmt2r vs default pools compared at ~30 closes each.

### Addendum 2026-07-10e — LTF PD-array mechanics in Tier 2
- entry-ladder Tier 2 now spells out where FVG/iFVG/OB/MSS plug into the three steps: displacement+FVG as step-2/3 quality evidence; retest limit into the M1/M5 FVG/OB/iFVG as the preferred (deeper) entry expression after the sequence completes; array closed-through = soft-exit event; lone LTF array without a sweep stays a no-entry.

### Addendum 2026-07-10f — PD-array TF layering + upstream backfill
- SKILL.md new `PD Array 分层` section (user ruling): M1/M5=trigger layer, M15=structure layer, H1=consistency-check layer (no native H1 in local API — aggregate from M15, never from memory), H4/D1=map layer (D1 arrays set bias: discount→longs, premium→shorts), confluence=upgrade to A-grade waiting zone (stop beyond outermost HTF array edge; close-through of a stacked zone = whole-layer invalidation), naked array never an entry.
- Upstream backfill (OpenMobius-skill + PA_Agent review): CE(50%) as the universal retest anchor for refined limits; invalidation requires a full-range close-through (wicks don't count), second close-through kills the iFVG itself; OB+FVG geometric overlap (Unicorn) = strongest single-TF confluence; Brooks measured-move targets overlapping ICT arrays = target-grade confluence.
- Ops side (same day): Grok feishu channel SYSTEM_PROMPT realigned to 2026-07-10 rules + session rotated + service restarted; Friday-close flat reminder cron live (Sat 04:00/04:45 CST, dynamic minutes-to-close); papertrack stats exclude 1933 pre-fix inflated-mfe rows; a_watch now tier-filtered (A-tier any TF, others H4-only, C-tier never) and pushes both management schemes + `--source a_watch` bookkeeping line.

### Non-goals
- Manual (user-analyzed) off-screen deep limits untouched — journal 35 trades +1.76R avg shows human-picked levels are a different population.
- No change to dual stop constraint numbers; audit added as warning, not new formula.

## 2026-07-10 — Screen Presence Routing (LTF on-screen default)

### Why
- User + Fable digest of 07/03–05 journal and calibration cases 10–15: **M1/M5 CISD/iFVG is this desk's highest-fill entry path**.
- Live habit of always quoting Tier 1 deep limits caused systematic unfills (EUR/AUD shallow pullback miss) and false debate ("can we enter on LTF?").
- Money leaks were post-entry (no +1R partial, stop not trailed to structure, same-zone third try) — already in Hard Rules; needed operational **routing + division of labor**.

### Changes
- **SKILL.md**: new `Screen Presence Routing` (屏前 Tier2 / 离屏 Tier1 / 双挂先成交为主); Entry Mechanics no longer implies deep limit is the only default; Hard Rules +2 bullets.
- **entry-ladder.md**: which-tier-first table; Tier 2 marked on-screen default; two-stage stop (sweep extreme → failed level after acceptance).
- **execution-gates.md**: `Three brakes` section + "user Tier2 while desk quoted Tier1 is not a deviation."
- **live-desk-calibration.md**: case 17 method-split meta case.

### Non-goals
- No new indicator/method religion.
- No weakening dual stop constraint or same-zone fuse.
- Deep limit remains fully legal for off-screen.

## 2026-07-09b — four holding classes + Feishu→Grok desk

### Changes
- Trade classes renamed/centered: **剥头皮 / 日内 / 趋势 / 周线** (`scalp|intraday|trend|weekly`).
- Live line-1 must tag `【级别】`. Full rules in `trade-class-contract.md`.
- Journal accepts new names; `swing`/`position` kept as aliases.
- Feishu Codex channel upstream switched to **Grok** (`grok_upstream.py`) for multi-day live desk trial.

## 2026-07-09 — final restructure (v2)

### Goals
- Shrink always-loaded contract surface; one decision pipeline; kill soft conflicts; separate policy vs evidence.

### Changes
- **SKILL.md** rewritten as Identity + unified pipeline + dual stop constraint + output + Hard Rules bullets + Load Map (~contract only).
- **New** `references/entry-ladder.md` — Entry Timing Ladder full text.
- **New** `references/execution-gates.md` — CONDITIONAL gate, five checks, fuses, +1R, BTC check, position management; evidence as dated snapshots.
- **New** `references/local-stack.md` — API, universe, journal/watch commands (host paths live here).
- **WORKFLOW_CN.md** marked **legacy / do not load for live** (dual-source risk).
- Live vocabulary: prefer `等触发/别追/没交易/管仓`; hide READY/CONDITIONAL/Tier/rr_now in user-facing live answers.
- CONDITIONAL unified: conditional plan = pending 等触发 plan, not market permission.
- Stop rules unified: structure ±0.25×ATR **and** |entry−SL|≥0.5×ATR.

### Skill evolution protocol
- Append durable cases → `live-desk-calibration.md` (Case Format).
- Promote to Hard Rule: same error ≥3 times **or** ≥2R attributable in one week.
- Demote/delete: monthly re-eval or per-class n sufficient with counter-evidence → note here.

### Non-goals this pass
- No new methodology layers.
- No rewrite of deep refs (cycle playbook, examples, calibration diary content).
