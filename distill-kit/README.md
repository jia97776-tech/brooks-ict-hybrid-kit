# distill-kit：把交易员蒸馏成 skill，并量出「有多像」

思路：拿交易员**带时间戳的真实订单**当考卷，让「模型 + 手册」在同一时刻、只看当时的 K 线盲答。
然后逐题对照他本人的答案：做不做、方向、入场线、止损、市价还是挂单。
答错的题交给反思模型，由它改一份**补充条目（playbook）**。改完的版本只有在验证集上配对显著变好才采纳。
最后在从没碰过的**留出集**上考一次，这个分数才算数。

```
他的订单 ──► build_exam ──► 考卷（真题 + 他没出手的对照题；按时间切 train / dev / holdout）
                                   │
edge_check：他本人 vs 随机空模型 ◄──┤   ← 先确认值得蒸
                                   ▼
          run_exam（模型 + 手册 [+ playbook] 盲答） ──► score（忠实分 / 结算 / 配对比较）
                                   ▲                         │
                                   └── optimize：反思 → 改条目 → 小批验 → 验证集验收
```

纯 Python 标准库（3.10+），不依赖 pandas。模型可以用本机的 `claude` / `codex` / `grok` 命令行，也可以走 Anthropic API。

---

## 先看这个：Tom 值不值得蒸

你自己的 `settlement_v0.md` 附录 A 已经做过空模型检验，结论是：Tom 公开 Swing 账本先到 1R 的命中率只比随机时点高 1–3 个百分点；**方向反过来，命中率反而更高**。
他赢面主要来自「止损放在 2 倍 ATR 以外」这一条几何规则，不是看盘判断。

所以对 Tom，这套工具最多能证明「skill 学会了他的选线和挂单习惯」，**不能指望学到赚钱的能力**。
换任何交易员都一样：**先跑 `edge_check.py`**，他本人明显强于空模型，再往下蒸。
可以按单型拆开看，只蒸有 edge 的那一半：Tom 的市价单明显好于挂单。

---

## 0. 拿到本地

```bash
git clone -b claude/hello-w6yz64 https://github.com/jia97776-tech/brooks-ict-hybrid-kit.git ~/distill-kit-src
cd ~/distill-kit-src/distill-kit
cp config.example.json config.json
python3 selftest.py        # 假数据 + 假桌面跑一遍，约 30 秒，不花钱
```

下文用两个变量，按你本机改：

```bash
BK=~/backup                              # claude-desk-backup-20260924 的克隆
SK=~/.claude/skills                      # 现行 skill 目录
```

## 1. 配置桌面（config.json）

| 后端 | 说明 |
|---|---|
| `claude` | 调本机 `claude -p`，提示词走 stdin，在空临时目录里运行 |
| `codex` | 调 `codex exec -m gpt-6-astra ... -`（跟你 `desk_replay.py` 的 Astra 桌同一个模型） |
| `grok` | 调 `grok -p`（提示词作为参数传，手册特别长时可能超过命令行长度上限） |
| `api` | Anthropic 官方 SDK（`pip install anthropic`，读 `ANTHROPIC_API_KEY`）。默认 `claude-opus-5-5`，effort=high；手册放在 system 并开了缓存 |

- `default_backend` 是答题用的桌面，`reflector_backend` 是改条目用的反思模型。两个可以不同，比如 codex 答题、claude 反思。
- `api` 后端默认开了服务端 fallback（`fallbacks: "default"`）：被安全分类器误拒时，自动换模型重跑同一请求。不想要就设 `"fallbacks": false`。

> ⚠️ **防污染**：盲测要求桌面**只**看到考卷给的手册。`claude -p` 默认会加载你 `~/.claude` 里的全局 CLAUDE.md 和 skill，那里面就有 brooks-ict-lean。
> 等于偷偷带了另一份手册进考场，跟你 09-24 查出来的 `SKILL_snapshot.md` 问题是同一类。
> 解决办法三选一：
> - 用 `api` 或 `codex`；
> - 给 claude 模板加上你本机版本支持的「不加载设置 / 技能」参数（用 `claude --help` 核对）；
> - 用一个干净的 `HOME` 跑。
>
> 检查方法：随便抽一道题，看 `runs/<tag>/answers.jsonl` 里的 `reason` 字段，有没有引用考卷里没给的条款。

## 2. 准备 K 线

所有脚本只读 `data/bars/{品种}_M15.jsonl`，用 `prep_bars.py` 转换。M1、M5、M15 都行，按年分成的多个文件会自动合并。

```bash
# Tom 的单在 2020–2025，需要当年结算用过的 FXCM / Dukascopy M1
python3 prep_bars.py --src ~/trading-corpus/<放 M1 的目录> --pattern '*.csv*' --rename GER30=GER40 FTSE=UK100
# 扫描器历史只覆盖 2025-09 以后，适合蒸近期的交易员
python3 prep_bars.py --src /home/box/trading_scanner_service/data/history --pattern '*_M15.jsonl'
```

- 支持 FXCM 格式（`DateTime,BidOpen,...`，可以是 `.csv.gz`）、Dukascopy 格式（`DD.MM.YYYY HH:MM:SS GMT+0200`）、MT 导出格式，以及任何带 open/high/low/close 表头的 csv。
- 本地时区的数据用 `--tz-offset-hours` 修正到 UTC。
- 品种名取文件名开头那一段，对不上就用 `--sym` 或 `--rename` 指定。
- 结算记录里缺 M1 的品种是 XAU、XAG、XTI、GBPAUD、EURCAD、CHFJPY。没有数据的品种，出考卷时会自动跳过并列出来。

## 3. 出考卷

```bash
python3 build_exam.py --format tom-episodes \
  --src $BK/research/work/tom/episodes.jsonl \
  --quotes $BK/claude/skills/brooks-ict-lean/references/validation/distill_audit_20260924/tom_recovered/TOM_READ_INDEX.txt \
  --include-reference --out exams/tom.jsonl
```

**题目怎么来：**
- **真题**：episodes 里带入场和止损的 TRADE / WAIT 单。TRADE 当作市价单（NOW），WAIT 当作挂单。
  - 默认只用 SILVER，164 张。
  - 加 `--include-reference` 再并入几何清楚的 REFERENCE_ONLY，合计 558 张。
- **对照题**：同一品种、真题前后 60 天内、他前后 3 天都没在该品种发过言的时点，默认每道真题配 0.5 道。
  - 没有对照题的话，只要「见到信号就下单」也能拿高分。

**怎么切：** 按时间，最后 25% 做留出集；其余随机抽 20% 做验证集，剩下是训练集。

**原话（`--quotes`）：** 只给反思模型看，桌面看不到。
- READ_INDEX 是索引，只有几十条原话。
- 如果你还有 Tom 频道全量 4256 条（`~/trading-corpus/hougaard_ledger_20260903/`），把它转成一行一条的 `{"msg_id": 3932, "text": "..."}` jsonl 传进来，反思质量会高很多。

**换别的交易员（小新神、Keyshot 等）：** 整理成 canonical 格式，一行一张单：

```json
{"sym":"NAS100","time":"2026-06-17T13:45:00Z","side":"SHORT","type":"market","entry":21950,"stop":22010,"quotes":["这个SMT不重要"]}
```

然后：

```bash
python3 build_exam.py --format canonical --src xinshen.jsonl --out exams/xinshen.jsonl
```

## 4. 先查 edge

```bash
python3 edge_check.py --exam exams/tom.jsonl
```

输出按「全部 / 市价 / 挂单」分三组，每组三行：他本人、随机时点空模型、方向反过来。
本人的命中率和均值要明显高过空模型（CI 不重叠），才值得继续。

## 5. 基线：现在离他有多远

```bash
python3 run_exam.py --exam exams/tom.jsonl --split dev --skill none --tag bare                 # 裸模型
python3 run_exam.py --exam exams/tom.jsonl --split dev --skill $SK/brooks-ict-lean/SKILL.md --tag lean
python3 run_exam.py --exam exams/tom.jsonl --split dev --skill $SK/brooks-ict-lean/SKILL.md --tag lean_r1 --rep 1   # 同一手册第二遍

python3 score.py --exam exams/tom.jsonl --run bare --run lean --settle      # 手册比裸模型多像多少
python3 score.py --exam exams/tom.jsonl --run lean --run lean_r1            # 噪声地板
```

- `--skill` 可以给多个文件，按顺序拼接，比如 lean 的 SKILL.md 加 trials.md。
- 也可以直接给 Tom 的蒸馏材料，比如 `tom_recovered/PATTERN_BOOK.md`。
- 中断了，同一条命令再跑一次就行，只补没做的题。

## 6. 自动迭代补充条目

```bash
python3 optimize.py --exam exams/tom.jsonl --skill $SK/brooks-ict-lean/SKILL.md --tag tom1 --iters 15
# 或者从 Tom 自己的材料起步，不带 lean：
python3 optimize.py --exam exams/tom.jsonl --skill $BK/claude/skills/brooks-ict-lean/references/validation/distill_audit_20260924/tom_recovered/PATTERN_BOOK.md --tag tom_pb --iters 15
```

每轮的过程：
1. 从训练集抽 24 题作答；
2. 挑最多 6 道错题交给反思模型，给它看图的节选、桌面答案、他的实际单和原话；
3. 反思模型提最多 3 处增、删、改；
4. 新版本先在同一小批题上重答，没变好就丢掉；
5. 变好了再上验证集，配对提升 ≥ 0.02 且 P(提升>0) ≥ 0.8 才采纳。

产出都在 `runs/opt_tom1/`：
- `best.md`：当前最佳补充条目；
- `pb_vN.md`：每个被采纳的版本；
- `log.jsonl`：每轮的诊断、修改、分数，被丢掉的也记着。

中断后，同一条命令会接着上次的最佳版本继续。

## 7. 留出集终考

`optimize.py` 跑完会打印这三条命令：

```bash
python3 run_exam.py --exam exams/tom.jsonl --split holdout --skill <同上> --tag tom1_hold_base
python3 run_exam.py --exam exams/tom.jsonl --split holdout --skill <同上> --playbook runs/opt_tom1/best.md --tag tom1_hold_opt
python3 score.py --exam exams/tom.jsonl --run tom1_hold_base --run tom1_hold_opt --settle
```

**验收标准（事先定好，别看了结果再改）：**
1. 留出集上配对忠实分提升的 95% CI 下沿 > 0；
2. 「做不做 + 方向」一致率接近第 5 步量出的噪声地板。这就是上限，再往上不可能；
3. 结算不差于他本人在同一批题上的结果。像他但亏得更多，不算成功。

通过之后，`best.md` 里的条目由你人工审一遍，按你现有的 trials.md 流程写进 skill，每条带标签和到期处置。**不要让脚本直接改 SKILL.md。**

---

## 分数怎么算

| 题型 | 桌面答 | 得分 |
|---|---|---|
| 对照题（他没出手） | 不做 | 1 |
| 对照题 | 出手 | 0 |
| 真题 | 不做 / 解析失败 | 0 |
| 真题 | 方向错 | 0 |
| 真题 | 方向对 | 0.4 + 0.3×入场接近 + 0.2×止损接近 + 0.1×市价/挂单一致 |

「接近」= max(0, 1 − 误差 ÷ ATR14(H4))，误差超过一个 H4 ATR 就不给分。同一时刻他下了多张单（OCO 或分批），取得分最高的那张。

**结算口径**（`dk/common.py: settle`，桌面和他本人用同一套）：
- 市价单按现价成交；挂单 14 天内触价才算成交；
- 只看初始止损，比先到 +1R / +2R 还是先到止损；同一根 K 线里两者都碰到，按先止损算；
- 30 天还没结果，按最后收盘价计 R。

## 桌面看到什么

| 内容 | 默认 |
|---|---|
| K 线 | W1 26 根、D1 100 根、H4 60 根、H1 48 根，全部是截至决策时刻已收盘的 |
| 辅助算术 | W1 / D1 的 SMA20，H4 / D1 的 ATR14 |
| 输出 | 市价 / 挂单 / 不做 + 方向 + 入场 + 止损 + 依据的线 + 理由 |

- 看到的 K 线在 `config.json` 的 `context` 改。
- 辅助算术那一行用 `--no-indicators` 去掉。
- 要检查桌面实际看到的内容，可以对某一道题调用 `dk/common.py` 里的 `render_context`，把结果打印出来。

## 花费粗估

- 每道题的输入约等于手册加上下文。lean 约 8k token，上下文约 10k token，合计约 2 万 token。
- 每轮迭代约 110 次调用：小批两遍，加一次验证集 60 题。
- 走 API 按 Opus 5.5 每百万输入 token $4 算，每轮约 $5–10，15 轮约 $100 上下。手册开了缓存，实际会低一些。
- 走 claude / codex 命令行消耗的是订阅额度，不单独计费。
- 同一提示词的答案缓存在 `cache/`，不会重复花钱。

## 文件

| 文件 | 作用 |
|---|---|
| `prep_bars.py` | 各种 K 线转成 `data/bars/*_M15.jsonl` |
| `build_exam.py` | 出考卷（tom-episodes / canonical 两种输入） |
| `edge_check.py` | 他本人 vs 空模型 vs 方向反过来 |
| `run_exam.py` | 桌面答题（并发、缓存、断点续跑、`--rep` 量噪声） |
| `score.py` | 忠实分、结算、两份答卷配对比较 |
| `optimize.py` | 反思 → 改条目 → 验收，循环 |
| `selftest.py` | 假数据全流程自测 |
| `dk/` | 公共件：K 线、上下文、提示词、模型调用、打分 |

## 局限，先说在前面

- **样本量**：Tom 能用的真题约 380–550 道，扣掉缺 K 线的品种还会更少，留出集大约 100 道。忠实分的 CI 宽度大约 ±0.05–0.08，小改动分不出好坏。
- **只蒸得到写下来的部分**：只能蒸「看 K 线就能复现」的决策。他看的新闻、盘口、别的市场（比如 DAX 带 FTSE），考卷里都没有。
- **有过拟合风险**：优化器会往验证集上挤分，所以一定以留出集为准；想长期用，就按时间滚动重切一次考卷。
- **像 ≠ 赚钱**：忠实分高只说明像他。能不能赚钱，看结算那一行，也看第 4 步 edge_check 的结果。
