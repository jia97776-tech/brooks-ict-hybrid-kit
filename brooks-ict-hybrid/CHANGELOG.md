# brooks-ict-hybrid CHANGELOG

## PROPOSED（Codex/Grok 提案区 — 16e 起生效：非主桌对 skill 的修改先写这里，主桌审核合并后才进正文）

- **[Codex 2026-07-16，主桌待审] 撤销 desk-data 子agent 默认分流，改「本地过滤」**：称 Feishu 单轮 3-6 分钟延迟源于 Agent 起子进程+等待；主张主桌直接 curl+同命令内 python3/jq 过滤（只留判断字段、扫描先按 READY/pushable 收窄），仅超大批量才临时派子agent 且放后台。修的 case：飞书实盘问答延迟（2026-07-16）。复查日期：2026-07-24。主桌批注：延迟另有已证实因子（feishu 桥当时跑 fable-5，生成占 140s+，已改 sonnet-5+前缀路由）；「本地过滤」部分与主桌现行做法一致可先采纳为习惯，「撤销 desk-data 默认」需用户裁定后才动正文。原 diff：session scratchpad `codex_proposal_deskdata.diff`（2026-07-17 从 codex 克隆未提交改动收编）。

### [Opus 2026-07-20c] PA_Agent 完整深读 G1–G5 — **已裁决**（G2-G5 收、G1 收半，详见 `adjudication-2026-07-20c`）

Opus 亲读 PA_Agent 全系统（二元决策 1101 行 / 提示词大纲 / 市场诊断框架 8 态 / 文件17 止损 / 逐棒检查单逐字 + 全 28 prompt 文件概念索引核对）+ OpenMobius 726 概念名单。**结论：系统本体我们吸收得不错（四硬禁令/SPS-SCS/climax/8 态/背景限价 §9.0P/反手冷却/K0/RR 纪律都在 live-pa-action-gate + brooks-market-cycle-playbook）。** 真金=下列 A 层执行精度补丁；B/C 层（三角形/抛物线楔/微双底顶/ii-iii/失败的失败/6 句口诀）是低价值形态覆盖，数据（13 门全废）说非 edge，**只可当 cycle-playbook 识别词汇，不进扫描器**。锚定「edge 在裁决+管理」。

- **G1 · 计划限价 K1 对照（🔴 高，治「限价老接不到/误判失效」）**：计划型限价单失效判定——只检查 entry 在 K1.close 正确一侧（多 entry<K1.close / 空 entry>K1.close）；**禁止因 K1 影线曾触及 entry 就判失效**（限价是等未来回撤，不要求 K1 未路过）；仅 K1 **收盘穿越** entry 反侧或 **触及 stop** 才作废。修的 case：限价被影线误杀（2026-07-19~20 限价主题）。上游：二元决策 §9.0P。复查 2026-09-20：limit 单 ≥20 笔看误杀率。
- **G2 · 各周期止损「过大」上限过滤（🟡 中高）**：止损三约束补上限——结构损 > 2×ATR / > 通道宽 40–50% / > 区间宽 10% / > 尖峰高 50%（按 cycle）→ 判过大，缩仓或不做，禁向内取整/扩损凑；8 跳 / 信号棒 60% 高度只作过滤阈值不当止损价。修的 case：噪音级紧损凑 R（XAU$1/AUD1.7pip/US500 3点反面）+ 结构损过大硬做。上游：文件17 / 二元决策 §10.2。复查 2026-09-20。
- **G3 · trending_tr 中部陷阱（🟡 中）**：§14 明列——趋势型交易区间禁止按通道/尖峰逻辑做**中部趋势跟踪或追突破**，只顺主方向在边界/回撤入场。修的 case：trending_tr 被误当通道在中部追。上游：二元决策 §14。复查：遇样本 +3 评。
- **G4 · 跳数陷阱（🟡 中，仅 tick 制非加密：金/银/指数/FX）**：止损/entry 别放在「整数目标差 1 跳」处（5t=差1跳到1点 / 9t=2点 / 17t=4点 / 41t=10点），这些位置常被扫。非加密挂损避开。修的 case：非加密止损被整数关口前一跳精准扫掉。上游：文件22。复查：遇样本评。
- **G5 · 四类 Measured Move + 两目标纪律（🟡 中，锐化 target/runner=右尾）**：MM 四算法（①区间突破=区间高度投影 ②通道=波段高度 ③楔形=楔高从突破投影 ④尖峰/趋势 leg=leg 高度从回撤位投影）；目标优先序=近端结构（主目标/管理位）> MM/远端（runner）；TP1（近端结构，进 RR）+ TP2（MM/远端，必填不进 RR）两级。修的 case：目标跳级（照 scanner entry_ref 跳 H4 大结构当主目标，2026-07-04 Codex 纠）。上游：文件23。复查 2026-09-20。
- **明确不采纳（原版怪癖，与本桌冲突）**：PA_Agent §10「RR>1.5 → 向外扩 stop 拉回 RR≤1.0」（它怀疑高 RR）与本桌「高 RR 靠更好入场、绝不扩损」冲突；live-pa-action-gate Execution Addition #3 已正确拒绝，**保持不抄**。
- **OpenMobius v0.3.0**：ICT/SMC/缠论概念词典（726 概念，ChromaDB 存储、非可执行逻辑）；高价值 OTE/CE/强弱/dealing-range 已进 P5，其余是我们 ICT 层已有词汇或数据证明非 edge 的入场精度（4H-candle 模型/AMD 等），**不再回灌**。

### [Opus 2026-07-20] 数据×上游联合审计 5 提案 — **已裁决 2026-07-20**（P2/P4/P5 收、P1/P3 各收一半，详见 `adjudication-2026-07-20`；退回部分勿直接改正文）

上下文：本轮结合 journal(54笔)+papertrack(4652条)+candidates ledger 真实记录，重挖上游两基座(PA_Agent v1.4 无新分析更新；OpenMobius 升 v0.3.0/726概念)。核心结论：**PA_Agent「效果好」源于 coherence 一致性纪律（非形态覆盖），与本桌数据「13门全废、edge 在裁决+管理+右尾」一致 → 优化方向=收割纪律+读盘一致性，不是加形态/加过滤。** 延伸 `data-2026-07-20` 复盘，不重复。

- **P1 ·【❌本条提案已退回作废（2026-07-20 裁决拆半：仅「+2R 硬地板」被采纳；「+1R 减半降为可选」被否，+1R 必减铁律不变——现行规则以 adjudication-2026-07-20 与 gates「+1R 收割铁律」为准，勿把本段当现行规则引用）】收割硬化：+2R 锁定当唯一铁律，+1R 减半降级为可选。** runner 到过 +2R → 止损必须锁 ≥ 保本+，**禁止再翻红**；+1R 减半从「铁律」降为「可选（按品种/信心，sweep_reclaim 等右尾大单不强制减）」；+1R~+2R 区间保持结构 trail（不碰 BE）。**与 `data-2026-07-20`「+1R/mgmt2r 分池未满30 暂不动」的区分**：那是「选哪条管理轨」的样本问题；本条是「一条硬地板防 ≥2R 回吐」，不依赖分池。修的 case：harvest 漏水——papertrack **75% 亏损单曾 ≥2R**(179/240) + 2026-07-02 24笔止损审计「浮盈>2R 回吐 71%」（跨两源重复）；+1R 就移 BE 已被 mgmt2r 浅窗口证实会洗损，故只在 +2R 硬锁。复查 2026-08-20：journal 补「是否曾≥2R」字段后跑「到过+2R的单最终结果」分桶。
- **P2 · `sweep_reclaim` 抬为头号 A+ 主形态。** SKILL 明确「扫荡→收回→收盘破」为优先主形态；扫描器给该类候选加权/置顶；桌面裁决倾斜；右尾大单不机械 +1R 减（接 P1）。修的 case：journal sweep_reclaim **10 笔 +3.54R**(占净利近半)，扫荡-收回全家桶全大正 + top5赢单=53%总盈利(右尾 edge)。信心：suggestive(n=10 单regime)，先当优先级排序+不砍 runner，不改入场合法门。复查 2026-08-20：≥20 笔后 vs 其它形态期望差。
- **P3 · 同区重试改硬停。** 同结构区第二次止损后**硬停该 setup**（要做须换结构/换品种）；收掉「第三次结构升级放行」口子，或门槛提到「必须更高级别新结构事件+写明非同一想法重试」。修的 case：same_zone_retry **0/3~4笔 −4R 零胜率**(journal + data-2026-07-20 已盖章)。复查 2026-09-20 或再遇同型 +3 笔。
- **P4 · 一致性守门（移植 PA_Agent coherence 精神，机制级非数据门）。** 桌面方向读数与扫描器已算结构字段(d1_state/htf_bias/cycle/传感器)对撞；冲突时**禁止悄悄改读数凑合法**，必须标 `anomaly=cycle_vs_pa|visual_dissent` 并降级。把「已确认事件不可改写」扩为「方向读数一旦与程序结构冲突，只能标注/降级，不能改读数使其合法」（对应 PA_Agent `detect_cheat` immutable-field 防作弊）。修的 case：一致性漏水（无单一 case，是 PA_Agent 机制 + 本桌 edge=裁决一致性的推论）；上游锚=PA_Agent coherence_checks。先作读盘纪律条文，不加代码。复查 2026-09-20：观察 anomaly 标记率与随后偏离率。
- **P5 · OpenMobius v0.3.0 回灌（ICT 层，分档，全部旁证不放行入场）。** ✅**dol_strength**：扫描器给 swing 标 strong(其后 move 破 BOS/CHoCH)/weak(未破)，weak=真诱导目标；**先当 tag 攒数据，验证「weak DOL 更易被打到/runner 更好」后再决定是否重排 DOL 选择**（不一上来改选位）。✅**CE 失效预警**：扩 `limit_zone.refine`(已CE50%)——body 收破 CE=失效预警(喂软离场)，不当入场门。⏸️**OTE(0.62-0.705-0.79)/premium-discount**：只当最低调 context tag 或缓（13门已证位置非 edge，防字段膨胀）。✅**ict-v16-core.md** 更新 OTE/CE/强弱高低定义措辞(v0.3.0 多源版：0.5 非 OTE、CE=respect/invalidation、strong/weak=破没破结构)。修的 case：ICT 定义陈旧 + DOL 无强弱区分；上游=OpenMobius v0.3.0(726概念)。复查 2026-09-20：dol_strength ≥30 DOL 样本后。
- **明确跳过（研究确认无价值/坏）**：机械化楔形/最终旗形/磁力位/MDB-MDT(上游自己留给 LLM 判断)；PA_Agent barbwire 第4分量`<0.3×均棒幅`数学永假=死代码(本桌 `structure.py::barbwire()` 用 `<2.5×` 未抄坏，安全)；leg measured-move(对称误标)、MDB/MDT(邻棒2%ATR 太窄)。

## impl-2026-07-21b — 批C/C'/D/F 全量落地（Opus 实现，用户批准「把这个全做完」）

- **S6**：smc-mechanical-definitions 新增「Sweep 双类判别（IDM vs Turtle Soup）」（内部摆动+BOS前=延续燃料禁fade / 主极值+收回+无位移=弱反转仅LTF兑现；Osler/Mesfin 机制注）+ FVG ≥0.2ATR 最小位移门槛 + OB 两段生命周期（mitigated/broken，CISD=收破序列第一根开盘价）。
- **S7**：cycle-playbook 新增 §9 日型量化判据（趋势日阈值：range>2×ATR20/收盘顶底10%/30min VWAP分离≥0.3%/首回撤<25-50%；IBS 反转仅区间日放行）——「通道日禁逆势 fade」的量化形态，**gate 非 signal**。
- **批D**：CHANGELOG 归档（59KB→16KB 主文件+ARCHIVE）；Load Map 五件套统一（trade-class-contract 升默认必读）；pa-action-gate T0/T1/T2 与中文层名对齐；gates 19%(≥1R,07-10) vs 72%/452(≥2R,07-20) 口径注。
- **证据表新增 5 条**：Mesfin/Osler 外部验证、#101 前视铁证+C8 本桌因果审计通过、死否决器回放（sbq_weak +290R/幸存池转正+0.148R、micro_ct +92R、barbwire 负、climax LTF层）、F5 参数分歧裁决、无严谨验证概念清单。
- **扫描器同步落地**（git 5bfb14f）：C7 asia 软降级（CI95 排除零）/ C9 floor2r 变体轨 / F2 env_sweep_scope / F3 classify_cycle / F1 pool_stats_audit.py（bootstrap CI+漂移守卫）。
- 版本 bump `slim-2026-07-21` → `slim-2026-07-21b`。

## impl-2026-07-21a — 批A 文本修复五项（Opus 实现，用户批准「开火」；源自 2026-07-20 四路审计 + 07-21 基座五路补审，方案见 ~/skill_scanner_optimization_20260720.md）

- **S1**：calibration case 15 撤回数字（76%≥1R/55%≥2R）替换为 strict 口径（72%/452 曾≥2R，指向 evidence §gates）+ RETRACTED 标注——消除 never-cite-retracted 自违。
- **S2**：CHANGELOG P1 提案加显式【已退回作废】戳（防误载入读到与 +1R 铁律相反的规则）。
- **S3**：live-desk-template 三个 Output Shape + 五个校准例首行补【级别】标签 + Output Shapes 头部加成文规则——修复「编译器教漏四级标签」的机制性漏洞。
- **S4**：execution-gates 新增「报价延迟 / 越价作废条款」小节（越价即作废 / 禁改单追价 / 随单挂 watch_level 飞书报警 / 话术模板）——闭合 memory quote-latency-trigger-void 缺口。
- **S5**：trade-class-contract 新增「下单词汇与仓位口径」节（MT5 词汇统一 + 仓位按 R 倒推与杠杆无关 + 净成本 RR 口径指针）——对齐 user-execution-venue-bitget。
- 版本 bump `slim-2026-07-20` → `slim-2026-07-21`。已知未修余项（批C/C'/D 排期）：gates:15「严格口径19%(≥1R)」与 gates:74「72%/452(≥2R)」两个 strict 数字的口径关系待证据表对齐说明；SKILL↔ladder 去重、术语统一、CHANGELOG 归档、session 单源化。

## adjudication-2026-07-20c — G1–G5 主桌裁决落地（用户批准）

- **G1 收半**：✅ 已挂限价失效判定收紧（影线路过≠失效；只认收盘穿越/触损）→ gates 挂单延续守卫。❌ 「计划单被 wick 碰过不失效」退回——与 touch 一次性（16d）+ 深限逆向选择审计（1889信号）冲突，本桌数据优先。复查 2026-09-20（limit≥20笔误杀率）。
- **G2 收**：止损三约束加第4查=上限（>2×ATR / >通道宽40-50% / >区间宽10%→缩仓或不做）→ SKILL。
- **G3 收**：trending_tr 中部禁通道/尖峰式追法点名 → cycle-playbook §2.6。
- **G4 收**：跳数陷阱（非加密止损避开整数关口差1跳）→ gates 场地摩擦。
- **G5 收**：两级目标（TP1近端结构进RR / TP2=MM投影必写不进RR）+ MM四算法 → SKILL Target Method。
- 认可提案自带的「不采纳 RR 扩损」与「B/C 层形态不进扫描器」。
- **收尾修（Opus 2026-07-20）**：G2 由「Stop Triple Constraint 第4约束」改为**三约束锚定后的「过大过滤」**（接受度过滤 ≠ 锚定法，PA_Agent 文件17 同框架）；「三约束」术语保持三条，heading 标注「+G2 过大过滤」。纯呈现/概念摆正，规则效果不变。

## adjudication-2026-07-20 — Opus 五提案主桌裁决落地（用户批准）

- **P1 拆半**：✅ +2R 硬地板进正文（gates +1R铁律节 + Hard Rule 12；曾到+2R→锁保本+禁翻红；papertrack 严格口径 72%/452 亏损单曾≥2R，主桌当场复核非污染行）。❌ 「+1R减降为可选」退回：journal 合法触发池带+1R减 avg+1.76R、07-19 HYPE 实例 −1R→0R，证据错配（机器池 MFE ≠ 实盘管理单）。
- **P2 收**：sweep_reclaim 扫单置顶（SKILL Scanner Map；只改排序不改合法门）。复查 2026-08-20。
- **P3 退核心收措辞**：升级例外保留（JPY 07-07 第4次=当周最大赢单；−4R 样本全是无升级同级重试，归因错误）；升级判据收严进 gates §5（更高级别新结构+显式声明非同想法重试）。
- **P4 收**：一致性守门 = Hard Rule 18（冲突只标 anomaly 降级，禁改读数凑合法）。复查 2026-09-20 看 anomaly 标记率。
- **P5 收（原则批准）**：dol_strength tag / CE 收破软离场预警按提案分寸做，落库后再补 local-stack 字段语义；OTE 缓。扫描器实现归 Opus。

## impl-2026-07-20 — P5 扫描器落地 + 版本 bump（Opus 实现）

- **扫描器**（`~/trading_scanner_service`）：`structure.py::swing_strength()`（ICT 强弱：其后 move 破前结构=strong / 未破=weak / 不可分类=null）；`scanner.py` 候选加 `dol_strength`/`dol_runner_strength`（guarded，按 DOL 价匹配 swing 分类）；`limit_zone.py` 加 `ce_warning` 描述符（入场后 body 收破 CE=软离场预警，因 limit_zone 仅价离区时生成、扫描时永不触发故做描述符非 bool）。全 **evidence-only tag，不改 DOL 选择、不放行入场**。离线单测 4/4 + 真实集成过（ETH 近端 weak/远端 strong 合理），服务重启上线零错误，n=32。OTE/premium-discount 按裁决缓。
- **SKILL 版本** bump `slim-2026-07-16e` → `slim-2026-07-20`（16e base + 07-20 裁决四条）。
- **local-stack.md** 补 dol_strength/ce_warning 字段语义（旁证不放行框架 + 桌面用法：主目标落 weak 位更托底、runner 到 strong 位提防不干净）。
- **grok 内嵌 prompt 查证**：`telegram_proxy/grok_upstream.py` 的 SYSTEM_PROMPT 是纯指针（「读取并遵守 `.grok/skills/.../SKILL.md`」），不嵌规则；sync 后 grok 读新版，**无需手动补**。记忆里「改 skill 要同步内嵌 prompt」的旧警告已过时。
- 复查 2026-09-20：dol_strength ≥30 DOL 样本后验证 weak/strong 命中率与 runner 质量差。

## sensor-2026-07-20 — ETH/BTC regime 旁证层（Opus 实现，主桌验收）

- 扫描器新增 `market_context`（Gate 现货 ETH_BTC，H4/D1 趋势 → risk_on|risk_off）+ alt 候选 `eth_btc_align`；纯旁证与 SMT 同级，不 gate pushable/READY、不进推送。验收：ratio 与永续手算一致、字段只落 9 alt、guarded 不破扫描。
- skill 挂钩：SKILL 旁证节一行 + local-stack 字段语义（alt 多 runner 在 risk_off 默认砍、align=false 提标准）。修的 case：2026-07-19~20 BTC 假突破期间 alt 多头无 breadth 门（HYPE 两笔）。复查 2026-08-20：align 分桶 ≥30 笔看 true/false 期望差。

## data-2026-07-20 — journal 54笔第一轮复盘落地（主桌）

- **SKILL.md 输出要素**：alt 单合同新增 **beta 失效线必填**（BTC 价位+收盘TF+动作，入场时锁定；不算成交后新增软退出）。修的 case：2026-07-19 HYPE 61.05/60.90 两笔 beta 退出均为入场后临场发明。复查 2026-08-20：30 笔 alt 单后看条款触发次数与净省损。
- **local-stack.md**：journal `--signal` 固定词表（10词封闭集，2026-07-20 起强制）；周末单强制 `--flags weekend`（n≥30 后裁决周末提标准与否）。
- **execution-aids-evidence.md**：same_zone_retry 证据盖章（4笔−4R零胜率；clean +3.76R vs flagged +0.36R；top5赢单=53%总盈利；54笔无一损超−1R）。规则零改动。
- 明确不动：CONDITIONAL 门（手筛后 +0.65/笔）、+1R/mgmt2r 双轨（分池未满30）、品种分层。


---

**2026-07-16e 及更早的全部历史条目已移至 `CHANGELOG_ARCHIVE.md`（2026-07-21 批D 归档：主文件只保留活跃提案区+近期裁决，防误载入历史矛盾文本）。**
