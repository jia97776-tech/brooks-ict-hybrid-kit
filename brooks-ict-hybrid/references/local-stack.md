# Local Stack（路径 / API / 宇宙）

Edit this file when the machine stack moves. SKILL.md should not hardcode host paths beyond pointing here.

## API

- Base URL: `http://127.0.0.1:8001`
- Probe: `GET /healthz` or `GET /openapi.json`
- Market data: `GET /price/{SYMBOL}`, `GET /bars?symbol=X&tf=M1|M5|M15|H4|D1|W1`, `GET /multi-bars?symbol=X&tfs=1m,5m,15m,1h,4h,1d,1w`
- Scanner: `POST /scanner/run-once?mode=intraday|swing|both`, `GET /scanner/status`
- Aliases: `POST /scan/run?mode=...`, `GET /scan/status/{job_id}`
- Read-only records: `GET /signals?limit=N`; metadata: `GET /symbols`, `GET /openapi.json`
- On 404: switch generation — never invent data. API down → say so, no levels.

## Scanner field semantics

- `READY` = sweep + MSS/CISD confirmed on a close + clean planned RR
- `CONDITIONAL_READY` = sweep with something missing (`reason`)
- `ARMED` = liquidity map only
- `dol` / `dol_runner` = near / far untaken swing liquidity
- `rr` = planned from POI retest; `rr_now` = degraded chase RR
- `late=true` / `target_crowded=true` → retest plan or do not chase
- `htf_bias` / `counter_htf`: M15 carries H4 bias (sweep-reversal first, EMA20 always-in fallback). `counter_htf=true` → cap CONDITIONAL_READY; scalp to **near** liquidity only; no far DOL runner
- `mgmt` = min(2R from POI, dol): partial/BE when aligned; practical TARGET when counter/NEUTRAL
- `d1_state` / `d1_bias` / `counter_d1`: mechanical D1 seniority (`spike_up/down` ≈ ≥4/5 directional closes + net ≥1.2×ATR + fresh 20-bar extreme close). `counter_d1=true` → with-trend pullback limit per SKILL D1 gate
- `stale_data=true`: last bar older than 2× tf — no live entries
- `contracting`: last 4 swing highs falling AND last 4 lows rising = coil / coin-flip; stops checked vs structure extreme + 0.25×ATR
- `mode=intraday|swing|both` = M15 / H4 / both
- `confirm_bar` (2026-07-14a/b): mechanical trigger contract. `null` = no closed MSS/CISD confirm, TTL≥6, or frozen reclaimed. Fields: `role` (`entry_confirm`|`map_confirm`) / `map_tf` / `entry_tf_hint` / `event` / `frozen_level` / `frozen_source` / `bar_time`+OHLC / `buffer`+`buffer_calc` / `trigger_price` / `trigger_side` / `market_ok`+`market_fail` / `expiry_bars` / `cancel_level`. **SL is NOT in confirm_bar**. `rr_from_trigger` = proxy RR from trigger→DOL (not desk hard SL).
- `pushable` / `not_pushable_reason` (2026-07-14b/c/j; **15e 语义**): **machine hint only** — whether the scanner's **own** entry `trigger_price` may be quoted as path-A hangable entry. `pushable=false` does **not** mean no trade: desk must try **path B** (raw M1/M5) unless reason is `chase` or `stale_data`. Other false reasons (`cisd_only` | `map_tf_not_entry` | `no_confirm_bar` | `no_ltf_confirm_bar` | …) → map retained + desk LTF. `chase` → old machine trigger not hangable (`do_not_chase`).
- `ltf_confirm_bar` / `ltf_tf` / `ltf_status` / `entry_confirm_bar` (2026-07-14c/j): after map scan, eligible parents fetch M5 (indexes M1) and attach LTF `confirm_bar`. Desk quotes **`entry_confirm_bar` or `ltf_confirm_bar`** only when `pushable=true`. Parent `confirm_bar` stays map. `ltf_status`: `entry_ready` | `entry_pending` | `chase` | `awaiting_ltf_confirm` | `direction_mismatch` | `bars_short` | `fetch_failed` | `ltf_cisd_only` | …；`ltf_status=chase` 时旧触发价不可挂。
- **candidates ledger** (2026-07-14d, v2 §8.3): every `run_scan` appends all candidates to SQLite `~/trading_scanner_service/data/candidates.db` (scan_id, snapshot, setup_type, pushable, machine-hint verdict/veto, outcome placeholders). Ops: `from scanner_service.candidates_ledger import stats_summary`. Design status: `trading_scanner_service/docs/SCANNER_V2_SPEC.md`.
- **confluence_retest** (2026-07-14e, v2 §8.1): extra candidates with `setup_type=confluence_retest` and `confluence_zone` (layers≥3, swept_into_zone, optional M5 `signal_bar`). Desk must review; never machine-direct hang. Trigger numbers only from `signal_bar` when present.
- **drilldown_chain + poi_scaled** (2026-07-14f/j, v2 §8.2 / §七): `setup_type=drilldown_chain` — H4 event → M5 same-dir → M1 entry confirm. A candidate exists only when H4 has untaken liquidity **in trade direction**; no forward DOL means no chain candidate. Fields: `chain` (h4/m5/m1 events, `chain_status`, `rr_chain`, risk disclosure), `poi_scaled` (tranche contract meta, total 1R), `confirm_bar` only when M1 live. Desk reviews; never auto-order.
- **limit_zone** (2026-07-14g, v2 §五；**16c**): optional field on map candidates — **deep off-screen / A-leg** arithmetic only (`zone`, `refine`=CE50%, `sl_anchor`+bar, `buffer`, `sl`, `mgmt`, `target`, `invalidate`, `valid_until`). Null if counter-HTF / stale / news / price still in zone. **`requires_desk_review` + `never_auto_hang` always true** — never machine-direct hang；**屏前默认挂单价不在此字段**（默认 M1/M5 FVG·OB·MSS，见 SKILL 16c）。zone_source excludes M1/M5 micro arrays.
- **zone_touch / 干旱（2026-07-15d touch；2026-07-15e/slim；16c LTF）：** 深限与 LTF 数组挂前均须生 bar 判 `zone_touch_state ∈ {untouched, first_touch_done, in_zone_now}`；主挂优先 `untouched`。接单三行：距离、touch 态、`易接|难接|悬空`。**干旱** = 路径 A 无 **且** 路径 B 已拉 M1/M5 仍无合法事件/**LTF 数组挂**/条件单 **且** 无 untouched 合法深限 → `没交易`。**仅 pushable=0 不算干旱**。禁止「先回 H4 POI 才开 LTF」伪门。
- **improve_fill** (2026-07-14h, v2 §六): optional **subfield of** `confirm_bar` when entry TF + `market_ok` + FVG in confirm range. Fields: `zone_tf`, `zone`, `zone_source`, `limit_price` (upper edge), `fallback_bars`, `fallback=market_if_still_ok`. Not default; user opt-in. Void if price past trigger extreme.
- **track / model / anomaly** (2026-07-14i): candidate + ledger fields. `track=cashflow|asymmetric` (machine prefills asymmetric for confluence/drilldown; desk may override). `model` = screening desk name when recorded. `anomaly` short codes; machine may only prefill mechanical `data_inconsistent`; desk fills visual codes. Ledger: `stats_summary()` includes `by_track` / `by_anomaly`.

- Flags are evidence, not entries — still pass PA reclassification + pipeline

## Universe (scanned)

29+ symbols:

- Crypto USDT perps: `btc eth sol doge xrp sui hype pepe zec tao wld`
- Metals/energy: `XAUUSD XAGUSD XTIUSD`
- Indexes: `NAS100 US500 US30`
- FX: `EURUSD GBPUSD USDJPY AUDUSD USDCAD USDCHF NZDUSD`
- **DXY**（美元指数，Gate 符号 `USIDX`，内部 `DXY`）：进扫描 + **SMT 确认**（旁证，不单独自动入场）。  
  - **同向金属**：`XAUUSD`↔`XAGUSD`（银的主 SMT 是金，不是 DXY）。  
  - **逆相关 FX**：`EURUSD/GBPUSD/AUDUSD/NZDUSD`↔`DXY`。  
  - **同向 USD 基**：`USDJPY/USDCAD/USDCHF`↔`DXY`。  
  - 候选字段：`smt` / `smt_partner` / `smt_inverse` / `smt_note`。
- **US stocks（2026-07-11 试点，scan-only）**: `TSLA NVDA MSTR CRCL`（Gate TradFi feed）。触发只认美股 RTH（13:30-20:00 UTC）；盘外报价只当地图；财报日按红字新闻；buffer 放大一档；a_watch 永不推送，papertrack 先攒样本。

Watchlist but **not** scanned (say so, do not invent candidates): UK100 / HK50 / USDCNH / XBRUSD.
Avoid non-USD FX crosses and odd thin commodities unless user asks.

**Symbol quality tiers**（papertrack 7d snapshot 2026-07-10，单 regime 样本，月度重评）：

- **A 层**（机器信号相对最好的切片）：`XAUUSD`（胜率 27.5%）、`XTIUSD`、`US500`；周期上 **H4 > M15**（H4 唯一平均为正的周期切片）。
- **C 层**（胜率 ≤4%，接近纯噪音）：`ZEC EURUSD US30 PEPE` — 机器信号**不推送、不主动给单**；扫描继续攒样本。用户点名仍可分析，但要带一句该品种机器信号历史质量差。

## Data source notes

- **Gate-only（2026-07-14）**：单一数据源，不做跨场报价 fallback。Gate 不可用就报 `SourceError`，禁止静默混入其它场。
- Crypto: **Gate USDT-M futures**。
- FX / metals / indexes / oil / US stocks: **Gate TradFi**。
- 油符号：对外统一 `XTIUSD`。
- Weekend: only crypto live; FX/metals/index scanner rows = Friday freeze（仅数据事实——周五交易本身**不冻结**，非加密只要求闭盘前平仓，见 SKILL 规则 10）

## Commands

```bash
# Level watch (alert ≠ fill); 8h hard stop
python3 ~/trading_scanner_service/scripts/watch_level.py SYMBOL --above X --below Y --note "计划" [--webhook <feishu bot url>]

# Journal on close — R from ACTUAL fills only
python3 /home/ubuntu/trade_journal/journal.py add \
  --symbol X --side long|short --result-r N \
  --cycle <8-state> --signal <trigger> --tier ready|conditional \
  --class scalp|intraday|trend|weekly --flags <violations> \
  --source desk|user|a_watch|mixed   # 触发是谁读的（2026-07-10 起必填，测桌面 vs 人肉）
# aliases accepted by journal: swing→trend, position→weekly

python3 /home/ubuntu/trade_journal/journal.py stats

# Papertrack (sample-size caveat; not proof of edge)
cd ~/trading_scanner_service && python3 -m scanner_service.papertrack stats
```

**`mfe_r` 口径警告**：2026-07-10 起为严格口径（成交 bar 与止损 bar 的极值剔除）；**此前所有行的 `mfe_r` 系统性虚高**（限价单成交 bar 的有利极值发生在成交之前也被记入）。禁止引用旧行 mfe_r 说「到过 +1R」——严格重放下 M15 亏单只有 19% 到过 +1R。

Papertrack cron: scans ~30m; outcomes hourly → `~/trading_scanner_service/data/signals.jsonl`.
Correlated-sample rule: 11 crypto are BTC-beta — cluster same-day same-direction alts as ~one sample before significance talk.

## Claude Code 主桌模型分流（16e，已于 2026-07-16 撤销，改用「本地过滤」省 token）

- **撤销：不再默认派 `desk-data` 子 agent。** 该分流为 2026-07-16 凌晨新加，实测导致 Feishu 实盘问答单轮延迟到 3-6 分钟（Agent 起子进程 + Monitor 等待），用户反馈"之前没这么慢"，判定为速度换 token 不划算，撤销。
- 主桌（Fable/Opus）看盘时**直接自己跑** curl/run_scan/拉 M1/M5/M15/H4/ATR/位移腿/FVG·OB 数组/zone_touch，不再中转到子agent等回信。
- **省 token 的关键不是"换便宜模型读"，而是"别把全量 JSON 倒进主脑 context"。** 所以 curl 之后必须本地过滤再进 context，禁止直接把 `/scanner/run-once`、`/multi-bars` 的原始大 JSON 整段贴出来：
  - 用 `curl ... | python3 -c '...'`（或 `jq`）在同一条 Bash 命令里就地过滤，只留 `symbol/tf/direction/state/price/reason/pushable/rr/rr_now/sl/dol/confirm_bar` 这类判断要用的字段，丢弃 `limit_zone`/`chain`/`poi_scaled` 等大字段，除非当前任务真的要用到。
  - 全场扫描（44+候选）：先按 `state=READY` 或 `pushable=true` 过滤出个位数候选，再展开细节，不要把 45 个候选的全字段一次性摊开。
  - 只有当过滤后仍然是超大批量（例如一次性要几十个品种的多周期 K 线原始 OHLC）时，才考虑临时派 `desk-data` 子agent，且优先放后台异步跑、不阻塞当次回复。
- 这样"省 token"和"不慢"是同一件事的两面：过滤这一步反正都要做（子agent时代也是数据员在做这个过滤），区别只是"自己顺手过滤"（快)还是"另起一个进程过滤再传回来"（慢)。

## Handoff verification

Never accept Codex/external relayed read into the live plan. Refetch price + M1/M5; state gap already made; rebuild entry/stop/management; re-anchor stop beyond structure extreme + ATR buffer (scanner uses 0.25×ATR).

## Dashboard vocab aliases

`POI` ≈ `fvg_entry_zone`; `DOL` ≈ `dol_target`/`tp`; trigger ≈ `ltf_mss`; plus `daily_bias_aligned`. Derive missing RR from sourced numbers only.
