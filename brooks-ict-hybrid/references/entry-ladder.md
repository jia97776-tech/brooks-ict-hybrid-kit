# Entry Timing Ladder（入场时机三层）

Loaded on live give-plan for **sweep-reversal / MSS-class** and **with-trend LTF continuation** after HTF map is live. 对外只说桌面中文（M5 FVG/OB 挂 / MSS stop / 离屏深限 / 别追）；内部定层，不倒 Tier 标签（复盘除外）。

屏前/离屏怎么选表达、双腿只开一条、口令表 → **SKILL「Screen Presence Routing」+「双腿入场」**（唯一正文，此处不重复）。本文只写各层的执行细则。

- Tier 1 **不是**比 Tier 2 更好的入场——它是**离屏替代品**。用户历史默认挂 = M1/M5 FVG·OB·MSS，不是 H4 扫 POI（校准：2026-07-16 US500 7581 / XAG / AUD 0.702 miss pattern）。
- **Anti-pattern（违规）**：把 B 腿写成「等价格进 H4 区之后再挂 M5」——把 A 的成交条件伪造成 B 的开关，复现「上不去就接不到」。

## Core

裸 MSS/CISD = 确认/管理事件，**本身不是入场**。完整 Tier 2 序列（扫→回收→事件冻结价收盘破）才是可执行序列。

- 等 M15/H4 确认收盘再入 = 系统性晚。
- 不走下面任何合法路径就进 = 赌信号（07-06 连亏根因）。

扫荡-反转类只有三层合法。开口前内部定层。

## Tier 1 — 扫后深限价（最早；唯一有重放支持的 pre-MSS 路径）

四硬前提全齐，缺一降级：

1. **扫荡已完成**：价格穿过冻结流动性位且入场 TF 收盘收回——禁「应该会扫」抢跑。
2. **深结构 POI**：前 swing/被扫位/OB/FVG 边缘；两区取更深；浅便利回撤不算。
3. **HTF 对齐**：非 `counter_htf`、非 `counter_d1`、周期态门放行（通道内扫高=延续非反转）。
4. **止损过三约束**：扫极外+buffer、距离 ≥0.5×ATR(entry TF)、损侧无未处理流动性。禁为 R 收紧进噪音。

四条全真 → 深区挂限价，**不需要 MSS**。挂不到 = 方法成本，不是追价许可。

**位置溯源（2026-07-10，binding）**：深区必须由用户或桌面在**生 bar**上判定。scanner `entry_ref`/POI 原样抄进挂单 = 禁（逆向选择审计，数字见 gates policy digest）；桌面复核位（结构点名+止损几何对入场 TF bar 区间核过）合法。

### 深限价 Live 合同（离屏输出 — 2026-07-13；07-15d 补新鲜度）

对任何 live **挂深位限价**回答有约束力；Tier 1 四前提照常适用。目的：离屏限价一眼可挂——不贴 scanner、不给两个入场表达、不与持仓相撞、**不在 first touch 已发生后再挂**。

#### 0) zone_touch_state（报挂前强制）

用**入场 TF 生 bar**（默认 M5/M15）判本 session 相对拟挂区：

| 状态 | 定义 | 可否主挂深限价 |
| --- | --- | --- |
| `untouched` | 区高低未被本 session 影线/实体触及 | **是**（唯一主挂态） |
| `first_touch_done` | 区已被触及并离开（含长影扫完弹走） | **否**。输出 `missed alpha` 或「二次回踩半仓降级」 |
| `in_zone_now` | 现价在区内 | **否**。转 LTF 确认/合法市价 |

- touch 态未知 → **禁报限价数字**，先拉 bar。
- `limit_zone` 算术 ≠ 可挂：scanner 出区后仍须本表+接单三行。
- journal：主挂 `path=B_untouched`；二次降级 `path=B_second_touch`（半仓）；first_touch 后误主挂 = `stale_limit_plan` 违规。

#### 1) 何时给深限价

| 场景 | 给限价？ | 备注 |
| --- | --- | --- |
| 用户明确 `挂着走`/`深限价`/`离屏` 且 `untouched` | **是**（主表达） | 可附一句「若盯盘改走小级别序列」 |
| 扫单结束、用户像要离开 且 `untouched` | **可**（标「可挂地图/离屏」） | 非「现在市价」；屏前默认仍 LTF |
| `first_touch_done` | **否**为主挂 | 可一句 missed/二次半仓；禁「去挂刚扫过的价」 |
| 屏前盯盘/连问小级别触发 | **否**为主表达 | 只给 Tier 2；禁顺手再挂深限 |
| 同品种已有持仓（任何方向） | **否** | 先管仓；flat 前禁同品种新挂限价 |
| `counter_htf`/`counter_d1`/中轴 chase | **否** | 逆结构不做深限；用户已自开逆势单 → 只近端管，无 runner，不另挂同向深限加仓 |
| CISD-only 机器信号 | **否**主动推 | 不因「有 POI」破例 |
| 干旱（定义见 SKILL） | **否**轮换假主推 | |

#### 2) 位置几何（生 bar 复核，禁机器直贴）

1. **先点名锚**：扫极/被扫前 swing/H4·M15 结构高低——写清 TF+价+（能写则写）bar 时间。例：GBP 今日低 1.33664，回踩带 1.3375–1.3385。
2. **限价用结构带**：默认给区（上/下沿）；用户要单点 → 带内 CE(50%) 或中点作**可选精化**，不是第二张单。
3. **禁止**：limit 往现价挪「跟上」；scanner `entry_ref`/POI 原样当挂单价；中轴浅回撤冒充深结构；first_touch 后仍报主挂。
4. **损**：扫极外 + `max(0.25×ATR, 点差垫)`，且 ≥0.5×ATR；写明级别（深限默认 M15 结构损或 H4 POI 整层损，按 thesis 不混用）。宽损仅用户明确要缓冲且按宽距缩仓。
5. **目标**：管理位/主目标/runner 分层；`counter_*` 无 runner；非加密主目标略提前、RR 报净成本。

#### 3) Live 输出硬格式（缺字段 = 非法限价计划）

```text
{SYMBOL}【级别】：离屏深限价{多|空}（可挂|不可主挂）。
zone_touch_state：{untouched|first_touch_done|in_zone_now}（{bar 时间/简述}）。
接单：距现价 {点或 ATR}；粗标 {易接|难接|悬空}。
区 {low}–{high}（锚：{TF} {结构描述} {价}；生 bar 复核）。
限价：{点或子区间}。
止损级别：{M15 结构损|H4 POI 整层损}；候选锚：{全部相关候选}；anchor {最外层相关锚}。
止损算术：buffer {max(0.25 ATR, 点差垫)}；硬损 {anchor±buffer，只向外取整}。
管理方案：+1R减（锁定）；管理位 {mgmt}；主目标 {main}；runner {条件或无}。
取消：{收盘穿坏入场区 / 周期态翻 / 目标耗尽 / 会话结束}；挂不到 = 方法成本，不降价追。
```

- **接单粗标**：距离 ≤0.35×ATR 且 untouched → `易接`；≤1×ATR → `难接`；>1×ATR 或无回归结构/C 层远挂 → `悬空`（悬空不得当扫单主推）。
- 管理方案给单当下写死（默认 `+1R减`；深限宽损**禁**默认 `mgmt2r`）。
- 扫单迷你计划同形状可压一行，但 touch 态/接单粗标/区/损/管理/主目标/取消不能省到让人误以为可主挂。

#### 4) 成交后 / 生命周期

- 触价未确认 → `触价待确认`，先问成交；不按持仓算，也不再当「还在等」。
- 确认成交 → 立即管仓四要素（硬损/已锁软离场/减仓价/下一根盯什么）；撤同向备用单。
- 未成交作废：入场区被**收盘**完整穿坏、方向/周期态变、新闻/闭盘约束、或计划写明的会话窗结束。深限**不**套 6 根 TTL（那是 event-stop 层）。
- 屏前↔离屏切换：先撤旧再挂新；**每回合只保留一张入场单**。

#### 5) 与用户行为边界

- 桌面主计划「回踩多限价」而用户已持**反向**仓 → 主桌改管仓，原限价暂停/作废；不一边拿空一边挂多。
- 成交后损与软离场都没到就砍 = `fear_early_exit` 点名记账；+1R 减半是正确执行不是早走。
- 半仓后移损走三问；用户选了合法宽档 → 跟用户，不另塞更紧货架损。

## Tier 2 — M1/M5 事件序列 + LTF 数组挂（屏前默认）

屏前默认路径（含用户说「挂」未点名深位）。两种合法子表达；**只出一张单**。

### 2a — 完整转向序列（MSS/CISD 事件）

CISD/iFVG/OB 可描述序列；可执行决定只来自冻结价与收盘。三步全要：

1. 价格穿过先前冻结的流动性位。
2. 同一入场 TF 收盘收回该位内。
3. M1/M5 **收盘**破事件定义的冻结结构价。

影线和单 bar 观感永不触发订单。完成后：市价条件全过 → 市价；否则确认 K 极值外 pending stop。

### 2b — LTF 数组挂（M1/M5 FVG·OB · 用户默认挂法 · 16c/16d）

地图方向已立 + 本段位移腿在 M1/M5 留下数组 → 可在数组挂限价，**不需要**先回 Tier-1 深 POI。

**Hard preconditions（全部）：**

1. **地图 thesis live**：与 HTF/地图同向（非 counter_htf 追价）；scanner 行或桌面 H4/M15 读明确方向。
2. **周期态硬门（16d）**：8-state 读数必须是**突破腿/同向趋势/同向通道**。**TR 中段禁 2b**——震荡日每条腿都留 FVG，中段挂续势限价 = classic bleed；TR 里只允许 2a 事件或 edge 反转合同。裁决行必须写周期态。
3. **位移已存在**：清晰位移腿已打印（不是任何扫/动之前的抢跑）。
4. **数组在入场 TF 上**：点名 bearish/bullish **FVG** 或 **OB**，带 bar 时间+区 `[low, high]`，来自生 M1/M5 bar——非 scanner `limit_zone` 粘贴。
5. **zone_touch 判在 LTF 数组上**（非 H4 POI），**LTF 一次性（16d）**：`untouched` = 可挂主仓；**任何已触碰 = 该数组作废**——first touch 就是 the fill，回头的是二手货；不降半仓续挂，换新数组或走 2a。
6. **TTL（16d）**：默认 **12 根入场 TF 收盘未触即撤**（≤20 根须写明理由，如跨时段等开盘）。位移死了还挂着 = 深限逆向选择在 M5 复活。禁止仅以「会话结束」为撤单线。
7. **止损**：默认 M1/M5 触发损——数组极值或最近确认摆动外+buffer；≥0.5×ATR(entry TF)；禁为纸面 R 收紧进噪音。
8. **只一条腿**：用户已挂 Tier-1 深 POI → 先撤再挂 2b（或拒绝第二张单）。

**不要求**：价格先回访 H4/`poi`/`entry_ref`。

**输出形状（live 中文）：**

```text
{SYMBOL}【级别】：M5{多|空} · LTF {FVG|OB} 挂（非H4深限）。周期态：{突破|趋势|通道}。
数组 {low}–{high}（bar … 生K复核）；zone_touch：untouched。
限价：{点或子区间}。
硬损：{SL}（M5触发损；锚…+buffer…）。
管理：+1R减 → {mgmt}；主目标 {…}；runner {…或无}。
取消：{N≤12}根M5收盘未触 / M5收盘穿坏数组 / 数组被触碰未成交 / 地图方向翻。
```

journal：`path=ltf_array`；`source=desk` 或 `desk+scan_map`。

**与 2a 关系**：MSS 序列已完成且 market_ok → 优先市价/stop（2a），不降级成数组限价。数组挂用于**位移后的续势回补**、2a 尚未再触发时。**与深限关系**：2b 成败不依赖 Tier 1 是否成交；禁「先 A 后 B」串联。

### 双路径合同（补 SKILL「双路径入场」的机器字段细则）

**路径 A 引用字段**（`pushable=true` + entry/ltf `confirm_bar` 非 null 时**逐字**引用，禁改写挑 K）：

| 字段 | 桌面用法 |
| --- | --- |
| `role` | `entry_confirm`=可作入场源；`map_confirm`=地图/管理，禁用其 trigger 当入场 |
| `map_tf` / `entry_tf_hint` | 地图 TF vs 建议入场 TF（屏前默认 M5） |
| `event` / `frozen_level` / `frozen_source` | 事件与冻结价 |
| `bar_time` + OHLC | 确认 K，必须带时间戳 |
| `buffer` / `buffer_calc` / `trigger_price` / `trigger_side` | 触发侧 stop 价 |
| `market_ok` / `market_fail` | 市价三条件 |
| `expiry_bars` / `bars_since_confirm` / `cancel_level` | TTL 与穿回撤单价 |

**路径 B 触发原因集**：`confirm_bar=null` 或 `pushable=false` 且 `not_pushable_reason` ∈ `{no_confirm_bar, no_ltf_confirm_bar, map_tf_not_entry, cisd_only, direction_mismatch, awaiting_m5, awaiting_ltf_confirm, ltf_cisd_only, …}`（**不含** `chase`/`stale_data`）。步骤：①`GET /bars` 拉 M1/M5（指数 M1）新鲜 K，不得以「机器没 confirm」结束；②按三步走/触发语法自判，写出 `bar_time`+OHLC、冻结价来源、`trigger=极值±buffer` 算式；③事件未完成 → 完整条件单；已完成 → 市价或 stop（同一套市价三条件）；④journal `source=desk` 或 `desk+scan_map`；CISD-only 条件单标 `cisd_conditional` 默认半仓/小仓。

**`not_pushable_reason` 动作**：`chase`/`stale_data` → 硬拦；`cisd_only` → 路径 B 小仓条件单或等 MSS，禁满仓市价主推；`map_tf_not_entry` → 地图保留+下沉 M1/M5；其余 → 路径 B。

**动作表（屏前 Tier 2）：**

```text
pushable && market_ok     → 路径 A 市价
pushable && !market_ok    → 路径 A trigger stop（非 chase）
chase / stale             → 别追；禁复活旧 trigger
其余 false/null           → 路径 B 拉 M1/M5；条件单或确认后市价/stop
路径 B 也无结构           → 等触发 / 没交易（真干旱）
```

**improve_fill 附则（07-14h，非默认）**：仅路径 A 且 `market_ok` + 用户点名浅改善时用。

**分层纪律**：M15/H4 `map_confirm` = 地图非入场许可 → 下沉路径 B；屏前入场必须落在 M1/M5 生 bar；Tier 1 深限不走 confirm_bar（走 zone_touch 合同）。

### 触发语法（做空为例，做多镜像）

1. 上级做空前提成立（周期态+位置+closer side）。
2. 冻结价与确认 K：路径 A 认机器 confirm_bar；路径 B 认桌面生 bar 标注（MSS=confirmed swing；CISD=delivery open；MSS+CISD=后发生事件价）——不得无源乱挑。
3. 入场 TF **收盘**破冻结价 = 确认；影线不算。
4. 屏前：市价三条件全过 → 市价；否则确认 K 极值外 stop；越过极值 → 别追。
5. 硬损走三约束。
6. 订单 TTL 默认 6 根入场 TF（路径 A 可用 `expiry_bars`；2b 数组挂用自己的 12 根 TTL）。
7. 未成交前收盘穿回取消价 → 撤单。

**已确认事件三选一（防回退）**：确认 K 锁定后按序——①market first（屏前，market_ok+五查过 → 市价）；②event stop（market_ok=false → 报 trigger+market_fail）；③chase → 别追，不报旧 trigger。retest limit 仅用户明确不要追时给；**cisd-only 不给**。不得再发明反抽区/受压区/回踩条件/第二冻结价。

**单订单约束**：市价、event stop、retest limit 每回合只选一个。选市价后禁再给「反抽加仓/备用 stop」；市价成交后 pending TTL/穿回撤单条款失效，也不得临时加收盘软退出（入场前锁定的除外）。

**止损算术必须外显**（所有入场表达）：先列 `止损级别/候选锚/anchor/buffer` 再算 SL。空单 `SL=anchor+buffer`，多单 `SL=anchor−buffer`；取整只向结构外。成交后不再给取消/失效线；到管理位减仓；移损只到新确认结构外+buffer，不移入场价。例：旧高 1.13835、ATR 0.00080、buffer 0.00020 → 空损至少 1.13855（点差取整前）。紧损变体：仅新确认 M1/M5 摆动可替代序列极值，且须独立过三约束；永不锚未确认影线。级别模糊/候选漏列/任一约束失败 → 无单，重算或不做。成交后初始硬损锁死，只许向利润方向收，永不放宽（更宽级别 = 先 flat 再新票）。

**输出合同（硬规则）**：live 禁用主观判定词代替订单条件。pending 必须给全 TF/事件类型/冻结价/触发价/止损级别/候选锚/anchor/buffer/硬损/有效根数/撤单价；市价必须给全 TF/事件类型/冻结价/现价/确认 K 区间/止损级别/候选锚/anchor/buffer/硬损/管理位/主目标。缺字段 = 非法输出。形态强弱只能写在解释里，永不构成放行条件（signal_bar_quality 零结果，07-11）。

**retest limit / CE / 软离场明码标价**（数字见 gates policy digest）：破位价回测 limit = 合法「不追价」替代非 edge，cisd-only 不给，「收盘穿回撤单」条款在破位价 limit 上多数空转（收回前通常先成交）；FVG/iFVG CE = 序列确认后的可选改善价，非等价触发、不自动 mgmt2r，裸 CE 任何 TF 不入场；数组/结构收穿软离场非默认，仅入场时锁定才执行。入场依据的 FVG/OB 被 M1/M5 **收盘**穿透 → 撤未成交单；已成交默认走硬损。displacement/FVG 可作 step-2/3 描述证据，没有 FVG 不否决已完成的冻结价收盘突破；M1/M5 MSS = step 3，不用再等 M15 MSS。裸 LTF FVG/OB（无地图方向、无本段位移语境）仍禁（赌区）；机械定义见 `smc-mechanical-definitions.md`。

**目标从成交价搭**：近端实用位 = 主目标；远 HTF DOL = runner（仅 HTF 对齐）。Counter-HTF 只吃近端（cases 10–11）。

**触发读取默认桌面主动（07-10c/07-12i 用户裁定）**：用户屏前问某品种 → 桌面自拉 M1/M5 判序列；未确认给完整事件条件，已确认走 market-first。不等用户自读；用户自触发同等合法。桌面读 vs 人肉读孰优未验证——journal 记 `--source desk|user|a_watch`，各池 ~30 笔前拒绝对比。合法序列成交后桌面不回头争论入场质量，立即绑三刹车（gates §3/§5）。

`counter_htf` 候选最早只能从本层进，且只打**近端**流动性（scalp 管理，无远 DOL runner）。

## Tier 3 — M15/H4 MSS/CISD 收盘 = 管理事件

打印时先量剩余距离（确认→近 DOL vs ATR）。

- scanner 标 `confirm_bar.role=map_confirm` + `not_pushable_reason=map_tf_not_entry`。
- **已在场内**（Tier 1/2 进的）→ 减仓/保护信号。
- **不在场内** → 下沉 M1/M5 等新的 entry_confirm；M15/H4 收盘本身**不**授权市价或自动限价（即使 trigger_price 有值，那是审计字段）。
- **市价追地图 TF 确认收盘永远非法**。无 LTF confirm → 事件级等待或 missed-alpha 流程。

## 赌信号 — 机械禁单清单

全部禁止：

- 扫荡完成前抢跑（无任何扫/位移语境）
- 单 bar 反应，既无 Tier 2 三步序列也无合法 2b 前提集
- 紧损塞噪音凑高 R
- Counter HTF/counter D1 要求 Tier 1 待遇
- 连亏后降层「捞回来」
- scanner H4 `limit_zone`/`entry_ref` 原样主挂（地图当挂单价）
- 「必须先回 H4 POI 才允许 M5 FVG/OB 挂」（A/B 伪串联）
- 深限 miss 后把限价往现价挪「跟上」

**豁免**：白名单 M1 扫荡 V 反 scalp（单 bar 拒绝入场）按 `trade-class-contract.md`——不受三步序列约束。

降级/非法路径 = 执行偏差；发生时（无论用户还是桌面）在回答里点名一次。

## 与 CONDITIONAL_READY 的交互

见 `execution-gates.md` §1。CONDITIONAL 缺 MSS/CISD → 默认只给等触发计划，除非 Tier 1（四前提）或 Tier 2（完整序列）已在生 bar 上为真。单根强信号 bar 救不了候选。
