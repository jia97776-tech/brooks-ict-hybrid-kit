## slim-2026-07-16e — references 瘦身 + 回合分层 + 编辑权

Fixes: 用户反馈 skill「难用」（输出机械保守）。根因=必读包 85KB（SKILL 16 + gates 24 + ladder 25 + template 20），且 SKILL↔references 间双腿/双路径/presence/止损正文大面积重复；记账字段挤占正文。复查日期：2026-08-15（与 16d 同节点，观察输出体感+违规率）。

- **execution-gates 24KB→~11KB**：9KB 证据快照表整体迁入 `execution-aids-evidence.md`（按需加载），gates 只留 Policy digest 一句话版+「引用数字必须查表禁凭记忆」；与 SKILL 重复的止损三约束/双路径正文改指针。全部管理规则（mgmt2r 四条件/三刹车/移损锚三问/追价修复/方案锁定/多桌状态/挂单守卫/摩擦 RR/BTC 查/熔断/快慢审）零删减。
- **entry-ladder 25KB→~13KB**：删与 SKILL 重复的 presence 表/双腿表/pushable 语义表（改指针）；Tier1 深限合同、2a/2b 八前提、路径 A 字段表、not_pushable 动作、触发语法、三选一、单订单、止损外显、输出合同、明码标价、赌信号清单全保留。
- **live-desk-template 20KB→~9KB**：新增**回合分层**（下单回合=必填字段全给；聊天回合=自由说话只说变化，禁复读计划）；六个模板共用的止损块提取为【SL块】；校准例子 8→6（删冗余的 2/4/7/8 号，git 历史可查）；与 SKILL 重复的路径 B/LTF 挂单规则改指针。
- **SKILL**：Live Chat Style 加回合分层；多桌协议加**编辑权**（Codex/Grok 只提 proposal 进 CHANGELOG `## PROPOSED` 区，主桌 merge+sync；新规则必须标 case+复查日期，到期未兑现降级删除）；version → `slim-2026-07-16e`。
- 必读包合计 85KB→61KB（gates 24→14.8 / ladder 25→18.5 / template 20→9.7；SKILL 16.7→18.2 因新增回合分层+编辑权）。规则零删减（迁移+去重+指针化）；同步前做关键词丢失审计。
- Sync: claude / codex / grok（git pull）。

## slim-2026-07-16d — 2b 周期态硬门 + 数组挂 TTL + LTF touch 一次性

Fixes: 16c review 发现两个洞。①2b「地图方向已立」未含周期态硬门——TR/通道日每条腿都留 FVG，中段挂续势限价=放血（用户有通道日逆势前科）。②2b 取消线只有「穿坏数组/会话结束」，无时间 TTL——位移死了限价还挂着，等于把刚在 H4 深限修掉的逆向选择（papertrack 审计：接到 65% 同 bar 打损）原样搬到 M5。**复查日期：2026-08-15（journal `path=ltf_array` 攒 ≥20 笔后跑成交率/期望值分桶 vs `B_untouched`）。**

- **entry-ladder 2b preconditions 6→8 条：**
  - 新 #2 周期态硬门：仅突破腿/同向趋势/同向通道可挂 2b；**TR 中段禁 2b**，只留 2a 事件或 edge 反转；裁决行必须写周期态。
  - 新 #6 TTL：默认 **12 根入场 TF 收盘未触即撤**（≤20 根须写理由）；禁止仅以「会话结束」为撤单线。
  - 改 #5 LTF touch 一次性：`untouched`=可挂；**任何已触碰=数组作废**，不降半仓续挂（first touch 就是 the fill）——half-size demote 仅保留给 Tier 1 H4 深限。
  - Output shape：加周期态字段；取消行改为「N≤12根未触/穿坏数组/被触碰未成交/地图翻」。
- **SKILL：** Entry Mechanics LTF 数组挂节加三条（周期态门/TTL/touch 一次性）；Hard Rule 17；version → `slim-2026-07-16d`。
- Sync: claude / codex / grok。

## slim-2026-07-16c — 地图≠挂单价；LTF FVG/OB 默认挂；双腿入场

User live (2026-07-16): 连续 miss 深限（XAG 不回踩、US500 7581、AUD 0.702）根因不是「挂单废了」，而是桌面默认把 **H4 POI / limit_zone** 当挂单价；用户历史默认是 **M1/M5 FVG·OB·MSS**。伪门「等进 H4 区再挂 M5」仍等于深限 miss。

- **SKILL：** 新节「地图 vs 挂单价」+「双腿入场」；Entry Mechanics / Screen Presence / ICT 翻译 / Mode Split / Hard Rule 16 对齐；version → `slim-2026-07-16c`。
- **entry-ladder：** Tier 选择表重写；Tier 2 拆 2a 事件序列 + **2b LTF array hang**；PD arrays 从「仅改善价」升级为屏前合法主挂；赌信号黑名单加地图直挂与 A/B 伪串联。
- **live-desk-template：** 挂单默认 LTF；扫单展开主推 LTF。
- 规则协调：A 腿=离屏深限；B 腿=LTF 续势；**禁止串联、禁止双挂、禁止深限下移追价**。
- **local-stack:** `limit_zone` 标明仅 A 腿/离屏；干旱定义含 LTF 数组挂。
- Sync: grok / claude / codex.

## 2026-07-16 — DXY 进扫描 + SMT 确认字段

- Scanner universe: `DXY` (Gate TradFi `USIDX`).
- SMT partners: inverse EUR/GBP/AUD/NZD/XAU/XAG↔DXY; correlated USDJPY/USDCAD/USDCHF↔DXY.
- Candidate fields: `smt` / `smt_partner` / `smt_inverse` / `smt_note` (evidence only, not auto entry).
- Skill/local-stack: DXY + SMT as desk confluence; missing SMT does not veto legal PA trigger.

## slim-2026-07-16b — 飞书多桌自然沟通（去沟通限制）

User: Feishu Grok/Claude should talk like the desktop/TUI session — remove cross-desk communication stiffness.

- Multi-desk: natural discussion when user relays Claude/Grok/etc.; still re-fetch numbers; still one plan / one SL.
- Feishu Grok `SYSTEM_PROMPT` + `feishu_proxy_runtime/AGENTS.md` + `feishu-claude-bridge/CLAUDE.md`: no format police; free cross-desk chat.
- Hard trading rules unchanged (no invent prices, one main plan, path A/B, etc.).
- Sync skill trees; restart Feishu Grok proxy for prompt reload.

## slim-2026-07-16a — ref 干旱定义对齐 15e

- **Bug:** `entry-ladder.md` / `local-stack.md` 仍写「全场 pushable=0 且无 untouched 深限 = 干旱」，与 SKILL slim / 15e 矛盾，可能再次把「机器无 pushable」误当成「没交易」并跳过路径 B。
- **Fix:** 干旱 = 路径 A 无 **且** 路径 B 已拉 M1/M5 仍空 **且** 无 untouched 合法深限；**仅 pushable=0 不算干旱**。
- `live-desk-template` 标题标注改为 15e/slim；SKILL version → `slim-2026-07-16a`。
- Sync: grok / claude / codex.

## slim-2026-07-16 — 精简 SKILL.md（400行→203行，44KB→11KB）

Root cause: Codex/Grok 7/14–15 密集加规则导致 SKILL.md 膨胀到 44KB/400 行。同一规则重复 3–4 次（confirm_bar/双路径/止损），日期标注和 case 引用占大量篇幅。模型读完规则已用掉大量上下文，输出变保守变机械。

- **规则零删减**：所有 15e 规则（双路径/pushable降级/zone_touch/干旱/anomaly/track/多桌/移损三问/追价修复等）全部保留
- **去重**：每条规则只在一处说；Hard Rules 变成 15 条一句话索引指向正文
- **删改版标注**：`2026-07-14i`、`校准 case 18` 等属于 CHANGELOG，不占主文件
- **压缩段落**：Objective Entry Override 合入 Entry Mechanics；大段散文压成表格或短句
- **references 不动**：execution-gates/entry-ladder/live-desk-template 原封不动
- Backup: `SKILL.md.bak-15e`（三端）
- Sync: claude / grok / codex

## 2026-07-15e — 恢复桌面 LTF 路径；pushable 降为提示

User + desk root-cause (shared scanner/skill over-tightening, not Feishu): mid-July made M15/H4 map-only, required scanner `confirm_bar` for any trigger number, and treated `pushable=false` (`no_ltf_confirm_bar` / `no_confirm_bar` / `map_tf_not_entry` / `cisd_only`) as no-trade. That confused **“scanner has no executable fields”** with **“market has no opportunity.”** Old contract was: scanner maps; desk pulls fresh M1/M5 and decides.

- **Restore dual path:** Path A = quote `pushable=true` entry/ltf `confirm_bar` verbatim. Path B = when null/false (non-chase), desk **must** `GET /bars` M1/M5, name OHLC+freeze+trigger arithmetic, give conditional or post-confirm market/stop.
- **`pushable` = machine hint only** — blocks using *that candidate’s machine* `trigger_price`, not desk LTF plans.
- **Hard blocks kept:** chase / beyond trigger / news / post_target / stale / stop triple / no bar-sourced prices.
- **CISD-only:** no full-size default market; allow reduced-size conditional (`cisd_conditional`).
- **map_confirm:** still not entry; sink to path B M1/M5 instead of discarding the ticket.
- **Drought redefined:** only after path B also empty and no untouched deep limit — not merely `pushable=0`.
- **zone_touch (15d)** kept for deep limits (anti-stale hang).
- Files: `SKILL.md` 2026-07-15e; `entry-ladder.md` dual-path contract; `local-stack.md` pushable semantics; `live-desk-template.md` drought.
- Sync: grok / claude / codex. Scanner code may still emit pushable=false; skill no longer treats that as sole gate (optional later: scanner docs only).

## 2026-07-15d — zone_touch 深限价新鲜度 + 干旱协议 + 挂单接单难度

User session (Grok live): EUR C-tier / hard-to-fill hang promoted then demoted; US500 long limit recommended **after** M5 wick already printed 7548.76 — user unfilled and correctly blamed stale plan. Skill was strict on confirm_bar/chase but under-specified **whether a deep limit was still hangable in time**.

- **zone_touch_state** (Hard Rule): `untouched` | `first_touch_done` | `in_zone_now`. Only `untouched` may be the **main** deep-limit hang. `first_touch_done` → missed / optional half-size second-touch only — never packaged as fresh main hang.
- **接单三行** required on any limit main plan: distance (pts or ATR) + touch state + `易接|难接|悬空` heuristic.
- **干旱协议:** full-scan `pushable=0` and no legal `untouched` deep limit → verdict `没交易`/drought; at most one watch; ban rotating stale/C-tier/far hangs as “better tickets.”
- **C-tier:** first sentence names quality when user already hung or desk considers it — no reverse after treating as normal main.
- **Wider SL:** only if user asks buffer and size is recomputed to wide risk; default remains structure SL.
- Files: `SKILL.md` 2026-07-15d (Screen Presence + Hard Rules); `entry-ladder.md` Deep Limit §0+output; `live-desk-template.md` drought note; `local-stack.md` optional future scanner fields.
- Does **not** loosen: chase, invent triggers, CISD-only entry, post-fill widen, machine POI auto-hang.
- Sync: grok / claude / codex skill trees.

## 2026-07-15c — allow normal chat on Feishu

- Feishu channel no longer forces trading action grammar on every message.
- Non-trade chat (rewrite, meta, chit-chat) answers normally; skill only for market/position questions.


## 2026-07-15b — moderate live chat (not format police, not freeform)

- Restored practical **Live Chat Style**: lead with action, thickness by context, full plan when needed.
- Softened scan table from 强制 → 推荐; first-entry stop arithmetic required, follow-ups may compress.
- Feishu system prompt rebalanced for usable desk voice without 2–5-line / fixed-phrase / rewrite guard.
- Still no clarity rewrite pipeline and no trade-contract injection.


## 2026-07-15a — retire Feishu natural-desk format police

- Removed **Feishu / Mobile Conversation Contract** from `SKILL.md` (2–5 line cap, fixed blocked phrase, table ban, forced first-sentence grammar).
- Replaced `live-desk-template.md` **Mobile Delta-First Override** with lighter live follow-up style.
- Softened `execution-gates.md` blocked-trigger **wording** contract; kept policy: no audit trigger as executable entry; no inventing post-fill soft exit.
- Proxy already stopped clarity rewrite / trade-contract injection; skill now matches.


## 2026-07-14j — chase / DOL / stop-contract / API alignment

- Scanner: `beyond_trigger_extreme` now yields `pushable=false`, `not_pushable_reason=chase`, `ltf_status=chase`; ledger maps it to `do_not_chase`.
- Drilldown: no forward H4 liquidity in trade direction means no candidate; the swept level is never reused as a reverse DOL. Ledger adds target-direction anomaly defense.
- Entry contract: market, event stop, retest limit, and deep limit all print `stop_scope / candidates / anchor / buffer / SL`.
- Post-fill correction no longer permits widening after reducing size: keep the original stop and reduce, or close and open a newly sized ticket.
- Local stack is Gate-only and documents only implemented routes, including `GET /openapi.json` and `GET /signals?limit=N`.
- Synced Codex / Claude / Grok / kit; restored calibration case 19 to Codex.

## 2026-07-14i — 三层宪法 + anomaly 定长筛单 + track 分桶

- **系统三层宪法**：判定归代码 / 怀疑归模型 / 决定归用户。代码只做合法性与算术，不做最终 alpha 裁决。
- **anomaly** 短码枚举（`none|data_inconsistent|price_jump|cycle_vs_pa|multi_source|visual_dissent`）；≠none → 强制等触发，禁止编触发价。
- **扫单定长裁决表**强制：`品种|track|周期态|位置|五查|anomaly|裁决|理由≤30字`；主筛桌 + 他桌只审计；分歧向保守 tie-break。
- **track** 双轨轻量：`cashflow` 默认 / `asymmetric`（confluence|drilldown 预填）；中途换轨禁止；asymmetric 预算 ≤2 笔/≤2R；journal 分桶。
- **ledger**：`track` / `model` / `anomaly` 列 + 迁移；`infer_track` / `attach_protocol_fields`；stats 按 track/anomaly。
- live-desk-template 扫单表；Hard Rules 同步。Design-time 强模型岗位仍为流程说明，本轮不写扫描器新模块。

## 2026-07-14h — improve_fill（v2 §六；算术层收官）

- `confirm_bar.improve_fill` optional subfield: zone_tf / zone / limit_price (upper edge, not CE) / fallback_bars=3 / fallback=market_if_still_ok.
- Only when entry TF (M1/M5) + market_ok + FVG overlaps confirm range. Map TF → null.
- **Not default path** (`default_path=false`, `requires_user_opt_in=true`); user must ask for shallow improve.
- Wired via `improve_fill.py` + `scan_symbol` / drilldown attach. entry-ladder Tier 2 addendum + Hard Rule.
- **Scanner v2 core arithmetic modules complete** (①–⑥). Track dual-rail / multi-model desk protocol remain protocol-layer follow-ups.

## 2026-07-14g — limit_zone（v2 §五 深结构挂单区）

- Optional candidate field `limit_zone`: zone / CE refine / sl_anchor+bar / buffer / sl / mgmt / target / invalidate / valid_until.
- Preconditions: completed sweep, HTF not counter, not stale/news, price already left zone (deep retest geometry).
- `zone_source` = sweep_extreme ± map-TF FVG/OTE only; **no M1/M5 micro arrays**.
- **`requires_desk_review=true` + `never_auto_hang=true` always** — scanner arithmetic only; desk pipeline + user confirm before hang.
- Wired in `scan_symbol` via `limit_zone.py`. Hard Rule + local-stack field note. Tests: `test_limit_zone`.
- Next: improve_fill (confirm-window shallow limit with market fallback).

## 2026-07-14f — drilldown_chain + poi_scaled（v2 §8.2 / §七）

- New setup type `drilldown_chain`: H4 structure event → same-direction M5 confirm → M1 MSS/CISD entry. **M1 CISD legal only inside complete H4+M5 chain** (isolated CISD-only still banned).
- `drilldown.py` + `server._scan_drilldown`; candidates carry `chain` + `poi_scaled` + optional M1 `confirm_bar`.
- Statuses: `awaiting_m5` | `awaiting_m1` | `chain_complete` | `m1_confirm_stale`. H4 age >6 bars drops. C-tier skipped.
- `poi_scaled`: multi-tranche metadata (total risk ≤1R, declare before first fill, independent trigger each, forbids unplanned add). Always `requires_desk_review=true` — never auto-order.
- Desk: quote M1 `confirm_bar` numbers only when chain complete; otherwise event-level pending only.
- Tests: `test_drilldown` + server counts include extras. Next: limit_zone / improve_fill.

## 2026-07-14e — confluence_retest（v2 §8.1）

- New setup type: multi-layer confluence zone (≥3 of asia/london range, M15/H4 FVG, OTE 0.618–0.79, prev day H/L), must be **swept into**, then wait M5 signal bar in zone.
- `confluence.py` + scan hook; candidates carry `confluence_zone` + optional `signal_bar` (confirm-like trigger numbers). `requires_desk_review=true` always — not auto-entry.
- pushable only when non-weak M5 signal bar present (still desk five-check). C-tier skipped.
- Next per spec order: drilldown_chain + poi_scaled.

## 2026-07-14d — 候选全量落库（scanner v2 §8.3）

- Spec draft-2026-07-14b module order: after confirm_bar, log every candidate each scan.
- **candidates_ledger.py** → `data/candidates.db`: snapshot JSON + setup_type + pushable + ltf_status + optional machine-hint `desk_verdict`/`veto_reason` + outcome placeholders.
- Wired in `run_scan` (never blocks trade path). Design status: `trading_scanner_service/docs/SCANNER_V2_SPEC.md`.
- Still no auto-order. Next modules per spec: confluence_retest → drilldown_chain → limit_zone/improve_fill.

## 2026-07-14c — 父单自动 LTF confirm_bar

- Scan path: eligible map parents → fetch M5 (US500/NAS100/US30 → M1) → `apply_ltf_confirm_bar` → `ltf_confirm_bar` + recompute `pushable`.
- Eligibility: sweep + READY/CONDITIONAL + not C-tier + not CISD-only parent + not stale/crowded + map TF only. Not full-universe LTF.
- Fields: `ltf_confirm_bar`, `ltf_tf`, `ltf_status`, `entry_confirm_bar`. Map `confirm_bar` preserved.
- pushable still ≠ auto A-ticket. Tests +39. Server attach in `run_scan`.

## 2026-07-14b — pushable + map/entry TF + entry-ladder 只读

- Follow-up to 14a review: production hardening for confirm_bar.
- **scanner**: `confirm_bar.role` (`entry_confirm`|`map_confirm`), `map_tf`, `entry_tf_hint`; candidate `pushable` / `not_pushable_reason` (`cisd_only`|`map_tf_not_entry`|`no_confirm_bar`|`stale_data`).
- **entry-ladder.md**: Tier 2 `confirm_bar` 只读合同 + pushable 动作表；Tier 3 明确 map_confirm 不可入场。
- **SKILL.md** `2026-07-14b` Hard Rule: 入场触发价必须 pushable+entry_confirm；深限价不走 confirm_bar.
- Tests: map M15 not pushable; M5+MSS pushable; confirm_tf_role. 36 passed.

## 2026-07-14a — confirm_bar（触发价离开模型措辞层）

- Spec draft-2026-07-14 (Feishu desk): move confirm-K / freeze / trigger / TTL / cancel into scanner `confirm_bar`; desk may only quote, never invent.
- **scanner_service**: `structure.build_confirm_bar` + wire into `scan_symbol`; fields `confirm_bar`, `rr_from_trigger`. Null when no closed MSS/CISD, TTL≥6, or frozen reclaimed. `market_ok` / `market_fail` enums. SL stays desk-side.
- **tests**: `ConfirmBarTest` (READY has fields; long mirror; no-confirm null; TTL expiry; reclaim null). Full `test_scanner` green.
- **SKILL.md** version `2026-07-14a`: trigger-syntax Hard Rule + Hard Rules bullet `confirm_bar` 溯源; ban words include 回抽失败/回踩确认后进. Synced grok + claude skill trees.
- **local-stack.md**: field semantics for `confirm_bar` / `rr_from_trigger`.
- Audit: weekly grep 禁词 + trigger prices must trace to non-null `confirm_bar`; journal flag `subjective_trigger`. File/scanner write only — does not mutate live tickets.

## 2026-07-13a — Deep Limit Live Contract（离屏限价整理）

- User request (Feishu live): consolidate the deep-limit / 回踩限价 desk language used in the 07-13 scan + GBP session into skill policy.
- **entry-ladder.md** Tier 1: new `Deep Limit Live Contract` — when to speak a limit; raw-bar zone geometry (band + optional CE/mid refine); hard live output fields; fill/lifecycle; conflict with open tickets and counter-structure.
- **SKILL.md** version `2026-07-13a`: Screen Presence bullet + Hard Rules bullet pointing at the contract.
- **live-desk-calibration.md** case 19: GBP short vs desk long-limit map + XAU fear_early_exit contrast (same session).
- No change to Tier-1 four preconditions, scanner-POI ban, +1R lock, or trail-anchor three questions. File write only — does not mutate live GBP remain-half.

## 2026-07-12l — session trade matrix as pipeline step 2

- New `references/session-trade-matrix.md`: session windows (Asia/pre-London/London open/LDN-NY overlap/NY RTH open/dead hours/late session/crypto active-dead) × preferred work × default execution × target permission × avoid list; opening rules, trade-class effects, news/Friday/weekend recap, desk-Chinese output examples.
- **SKILL.md**: Unified Decision Pipeline inserts step 2 `时段许可`（时段只负责允许/降级/缩目标，不单独创造信号）, steps renumbered 2→9; Load Map adds `session-trade-matrix.md` as on-demand read for opening/session/dead-hour/news/Friday/weekend questions.
- Session is context, never a standalone signal; no change to triggers, stop rules, or management contracts. (Changelog entry backfilled by Claude during review — change authored by Codex.)

## 2026-07-12k — trail-anchor three questions / no equal-low shelf stops

- User ruling (HYPE manage, multi-desk conflict 66.87 vs 67.03): after +1R/partial, raised stops must pass **移损锚三问** before a price is quoted — confirmed structure? thesis-critical if broken? buffered outside?
- **Equal-low / equal-high shelves are illegal hard-stop trail anchors** (first liquidity swept on normal pullback). Confirmed double-tap / sequence HL-LH that started the move is legal.
- Trail output contract: `锚价 + bar 时间/TF + 确认理由 + buffer 算法 + 最终 SL`. Missing field = invalid trail.
- Multi-desk: different raised SLs → compare anchor bar first; structure floor wins, shelf loses; only one active SL. User-chosen anchor that passes three questions is followed.
- **SKILL.md** version `2026-07-12k`: stop-discipline + Hard Rules + multi-desk §6. **execution-gates.md**: new `Trail-anchor protocol`. **live-desk-calibration.md**: case 18 HYPE.
- File write only — does not mutate any live position (current HYPE remain half @ hard 66.87 / target 67.83 unless user says otherwise).

## 2026-07-12j — stop-scope lock / no post-fill widening / file-position isolation

- Initial stops now declare one scope before entry: `M1/M5 触发损`, `M15 结构损`, or `H4 POI 整层损`. The desk must enumerate every relevant 候选锚 inside that scope before selecting the outermost anchor and adding buffer.
- Clarified relevance: HTF background confluence does not automatically force an H4-wide stop. A remote POI edge enters the formula only when the trade thesis explicitly requires that whole layer to hold.
- Removed the remaining top-level and evidence-table wording that automatically pushed any confluence stop beyond the outermost HTF edge.
- Any omitted relevant anchor or ambiguous stop scope invalidates the pre-fill plan and requires `重新计算 entry / size / management / RR`.
- The initial hard stop is locked after fill. It may remain or tighten behind newly confirmed structure, but it may never widen into loss. A scope/anchor mistake is corrected by reducing or closing; a wider stop belongs to a newly sized new ticket.
- HYPE calibration: `66.45 - 0.04 = 66.41` was arithmetically correct; the pre-entry audit question is whether `66.45` was the correct anchor for the declared scope. After fill, `66.31` cannot be relabeled as a replacement structural stop.
- Added `文件操作 ≠ 仓位操作`: editing, optimizing, reverting, validating, or backing up the skill does not mutate a live position unless the user explicitly names the symbol and position action.

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
