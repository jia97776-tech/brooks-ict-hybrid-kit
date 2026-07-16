# Brooks + ICT 中文工作流

> **LEGACY（2026-07-09）— 禁止作为 live 主脑加载。**  
> 权威合同：`SKILL.md` + `references/execution-gates.md` + `references/entry-ladder.md` + `references/live-desk-template.md`。  
> 本文件保留仅供历史对照；若与 SKILL 冲突，以 SKILL 为准。裁决用语请用 `能做/等触发/别追/管仓/没交易/missed alpha`，不要用本文件旧「五选一」覆盖新主干。

这是给 Codex / AI Agent 使用的价格行为分析 skill（旧版融合链说明）。

目标不是把 Al Brooks、ICT、PA_Agent 二元决策树并排摆出来，而是把它们融成一条交易判断链：

`市场状态 -> 流动性目的地 -> 入场位置 -> 触发证据 -> 相似案例经验 -> 失效/目标 -> 交易者方程 -> 结论`

## 核心原则

一句话：PA 决定环境能不能信，ICT 决定价格想去哪和在哪里等，PA 再决定触发是否够格，二元树防止跳步。

不要输出“三套框架各说各话”。最终必须收敛成一个融合判断：

`在当前市场状态下，价格可能被哪个流动性/磁力位吸引；哪个位置才值得等；出现什么 PA 触发才成立；哪里失效。`

## 融合翻译表

| ICT 概念 | 融入 PA 后的含义 | 使用方式 |
| --- | --- | --- |
| DOL / liquidity target | 磁力位、目标、被套盘释放位置 | 用来判断目标空间，不直接当方向 |
| PDA | 候选入场位置 | 只说明“在哪里等”，不说明“现在进” |
| sweep | 对前高/前低/流动性的失败突破 | 必须看到拒绝、回收或反向跟随 |
| displacement | 有跟随的突破 | 没有跟随就只是试探 |
| FVG / IFVG | 回撤缺口/失衡区 | 等信号棒、入场棒或 reclaim |
| OB / breaker / BPR | 结构区 | 必须服从趋势/区间/转换背景 |
| MSS / CISD | 低周期触发候选 | 必须能定义止损和失效 |
| SMT | 强弱分歧背景 | 不能单独当触发 |

## 标准流程

### 1. 市场状态

先用 PA/Brooks 判断环境：

- 趋势、区间、转换，还是不可读？
- K线是强跟随，还是重叠？
- 当前是突破、失败突破、回撤、高潮，还是区间中部噪音？
- Always-In 是否清楚？

如果市场是铁丝网、区间中部、重叠严重，漂亮的 ICT zone 也要降级。

同时标明证据来源：

- 只看截图
- 用户提供 OHLCV
- fresh OHLCV
- SMC 结构字段
- 概念卡 / case memory

如果是当前行情问题，不要凭记忆回答。没有新数据时，必须说明“这是截图/场景分析，不是实时盘口”。

### 2. 流动性目的地

再用 ICT 找目的地，但必须翻译成 PA 语言：

- 价格更可能去扫哪一侧流动性？
- 这个 DOL 是否也是 PA 磁力位、前高/前低、失败信号位、区间边界？
- 如果目标太近，交易者方程可能不通过。

没有清晰 DOL，不要硬写方向。

### 3. 入场位置

PDA 只回答“在哪里等”：

- discount/premium 是否和方向一致？
- FVG、BPR、breaker、OB 是否位于合理回撤或区间边缘？
- 这个位置是否和 PA 的二次入场、失败突破、通道回撤、EMA 测试相吻合？

位置合理但没有触发，结论是「等触发」，并给出具体等什么（扫高失败/回踩守住/反抽压住），不要停在 watch only。

### 4. 触发证据

触发必须由 PA 和 ICT 同时支持：

- ICT: sweep、displacement、MSS/CISD、reclaim。
- PA: 信号棒、入场棒、跟随、H1/H2 或 L1/L2、失败突破、二次入场。

如果只有 sweep/FVG，没有入场棒和跟随，不算完成。

入场时机必须走 SKILL.md 的 Entry Timing Ladder：M15/H4 MSS/CISD 收盘是管理事件不是入场事件；提前入场只有两条合法路径——扫后深位限价（四前提齐）或 M1/M5 完整转向序列。

### 5. 二元决策树

每一步只问一个问题：

| 节点 | 问题 | 不通过时 |
| --- | --- | --- |
| 0.1 | 输入是否足够？ | unknown / wait |
| 1.1 | 市场状态是否可识别？ | wait |
| 2.1 | 方向偏好是否清楚？ | neutral / wait |
| ICT.1 | 是否有明确 DOL/磁力位？ | wait |
| ICT.2 | 是否在合理 PDA/边界/回撤位？ | wait |
| PA.1 | PA 环境是否允许这个 ICT idea？ | 降级或 wait |
| 9.0 | 是否有实际触发或入场计划？ | wait |
| 10.1 | 失效/止损是否清楚？ | wait |
| 10.2 | 目标空间是否足够？ | reject 或 wait |
| 10.3 | 交易者方程是否通过？ | reject |

结论规则：

- 没有入场计划，写 `wait`，不是 `reject`。
- 有 entry/stop/target，但质量或交易者方程不通过，才写 `reject`。
- entry/stop/target 齐全，且环境、位置、触发都通过，才写 `trade`。

### 6. OpenMobius case memory

case 只能作为经验层，不能当规则。

可用方式：

- 当前结构像 `MSS -> FVG/OB -> inducement sweep -> expansion` 时，提醒等待诱导扫点和 PA 确认。
- FVG 内有旧低点/旧高点时，提醒观察是否扫后收回，而不是直接入场。
- 强趋势中出现多次内部 sweep 时，提醒它可能是 continuation entry，不一定是反转。
- HTF swing 需要 LTF CISD/MSS 保护后，才更适合执行。
- session AMD 需要 sweep + reclaim/displacement，不要硬套叙事。

禁忌：

- 不要说 case 证明这笔会成功。
- 不要从 case 推胜率。
- 不要用相似案例跳过二元树。

### 7. OpenMobius evidence contract

保留这几条作为证据合同：

- fresh data 优先于记忆。
- SMC 字段只做证据输入，不自动下结论。
- `equal highs/lows` 是 DOL 候选。
- `active OB/FVG` 是候选位置，不是触发。
- `BOS` 偏延续，`CHoCH` 偏转换，但都要 PA 确认。
- `Strong High/Low` 更适合做失效或反转确认参考。
- `Weak High/Low` 更适合作为目标/磁力位。
- `premium/discount/EQ` 用来判断方向位置是否合理。

术语归一：

- sweep / stop run / liquidity grab / raid = liquidity sweep / failed breakout test
- FVG / imbalance / BISI / SIBI = Fair Value Gap
- CISD / CSD / closure through opposing candles = Change In State Of Delivery
- OB = Order Block
- BPR = Balanced Price Range
- OTE = Optimal Trade Entry
- AMD / Power of Three = session delivery narrative

## 输出格式

以上整条链（市场状态 → 目的地 → 位置 → 触发 → 二元树 → case memory → 证据合同）只在内部运行，**不要把它作为回复结构摆出来**。最终输出必须服从 SKILL.md 的 Trader Identity Contract：

1. 第一行：直接裁决，五选一——`能做 / 等触发 / 别追 / 管仓 / 没交易`。
2. 第二行：现价和位置，说清这笔为什么舒服或不舒服。
3. 中间几行：入场/等待区、止损、管理位、主目标（runner 只在跟随还活着时提）。
4. 最后一行：取消条件（什么情况这个想法作废）。

禁止输出：市场状态小节、二元决策表、case memory 提醒段、证据来源段、「多空成立条件」并列段、最终评级标签。这些是内部推理，不是给用户看的。

内部评级到桌面裁决的翻译：

- A setup → 直接给可执行计划（`能做`）。
- B setup → `可以小仓 conditional`，并说清缺哪个确认。
- 位置对但触发没完成 → `等触发`，给出具体触发事件，不说 watch only。
- 状态/方向/目标不清楚 → `没交易`，点名下一个值得等的事件。
- 已到近端目标 → `别追` 或 `missed alpha`，给下一个再入场条件。

## 禁忌

- 不要把 ICT zone 当成自动入场。
- 不要把 Brooks 形态和 ICT 名词分栏堆砌。
- 不要瞎编价格位。
- 不要在 PA 环境不支持时硬解释 ICT。
- 不要把“看起来像”写成“一定会”。
