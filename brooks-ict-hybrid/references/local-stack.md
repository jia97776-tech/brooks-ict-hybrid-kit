# Local Stack（路径 / API / 宇宙）

Edit this file when the machine stack moves. SKILL.md should not hardcode host paths beyond pointing here.

## API

- Base URL: `http://127.0.0.1:8001`
- Probe: `GET /healthz` or `GET /openapi.json`
- Compat: `GET /price/{SYMBOL}`, `GET /bars?symbol=X&tf=M1|M5|M15|H4|D1|W1`, `GET /scanner/status`, `POST /scanner/run-once`
- Dashboard: `POST /scan/run`, `GET /scan/status/{job_id}`, `/signals`, `/signal/{id}/bars|review|deep_pa`, `/review/live`
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
- Flags are evidence, not entries — still pass PA reclassification + pipeline

## Universe (scanned)

28 symbols:

- Crypto USDT perps: `btc eth sol doge xrp sui hype pepe zec tao wld`
- Metals/energy: `XAUUSD XAGUSD XTIUSD`
- Indexes: `NAS100 US500 US30`
- FX: `EURUSD GBPUSD USDJPY AUDUSD USDCAD USDCHF NZDUSD`
- **US stock perps（2026-07-11 试点，scan-only）**: `TSLA NVDA MSTR CRCL`（Bitget usdt-futures，24/7 有价）。专用规矩：①触发只认美股 RTH（13:30-20:00 UTC），盘外合成价只当地图；②财报日=红字新闻；③点差按山寨最差档、buffer 放大一档；④MSTR/CRCL/COIN 类=BTC-beta 池计样本；⑤a_watch 永不推送（`SCAN_ONLY` set），papertrack 攒 ~2 周后评级。流动性参考（周六快照）：最好的 CRCL ~$660万/24h ≈ HYPE 的 1/6，仓位对应缩。TradFi CFD 端股票仅现货、无公开 kline，不接。

Watchlist but **not** scanned (say so, do not invent candidates): UK100 / HK50 / USDCNH / XBRUSD.
Avoid non-USD FX crosses and odd thin commodities unless user asks.
Periodic volume check: `contract.mexc.com/api/v1/contract/ticker` sort `amount24`.

**Symbol quality tiers**（papertrack 7d snapshot 2026-07-10，单 regime 样本，月度重评）：

- **A 层**（机器信号相对最好的切片）：`XAUUSD`（胜率 27.5%）、`XTIUSD`、`US500`；周期上 **H4 > M15**（H4 唯一平均为正的周期切片）。
- **C 层**（胜率 ≤4%，接近纯噪音）：`ZEC EURUSD US30 PEPE` — 机器信号**不推送、不主动给单**；扫描继续攒样本。用户点名仍可分析，但要带一句该品种机器信号历史质量差。

## Data source notes

- Crypto: **Bitget USDT-M futures**（故障回落 MEXC）
- 全部非加密（XAU/XAG + NAS100/US500/US30 + XTIUSD→USOUSD + 7 FX）: **Bitget TradFi**（MT5 CFD 同源行情；公开 web 接口 `bitgettradfi.com/v1/kline/getMoreKlineDataV2`，1m..1w 各 1000 根，~45s 新鲜；无鉴权但未文档化——故障自动回落 Gate/MEXC 旧路由）
- 油符号：WTI=`USOUSD`，布伦特=`UKOUSD`
- 陷阱备忘：Bitget 合约的 SPXUSDT 是 SPX6900 meme 币；NDX100USDT 流动性太薄不可用
- Weekend: only crypto live; FX/metals/index scanner rows = Friday freeze（仅数据事实——周五交易本身**不冻结**，非加密只要求闭盘前平仓，见 SKILL 规则 10）

## Commands

```bash
# Level watch (alert ≠ fill); 8h hard stop
python3 ~/trading_scanner_service/scripts/watch_level.py SYMBOL --above X --below Y --note "计划" [--webhook <feishu bot url>]

# Journal on close — R from ACTUAL fills only
python3 ~/trade_journal/journal.py add \
  --symbol X --side long|short --result-r N \
  --cycle <8-state> --signal <trigger> --tier ready|conditional \
  --class scalp|intraday|trend|weekly --flags <violations> \
  --source desk|user|a_watch|mixed   # 触发是谁读的（2026-07-10 起必填，测桌面 vs 人肉）
# aliases accepted by journal: swing→trend, position→weekly

python3 ~/trade_journal/journal.py stats

# Papertrack (sample-size caveat; not proof of edge)
cd ~/trading_scanner_service && python3 -m scanner_service.papertrack stats
```

**`mfe_r` 口径警告**：2026-07-10 起为严格口径（成交 bar 与止损 bar 的极值剔除）；**此前所有行的 `mfe_r` 系统性虚高**（限价单成交 bar 的有利极值发生在成交之前也被记入）。禁止引用旧行 mfe_r 说「到过 +1R」——严格重放下 M15 亏单只有 19% 到过 +1R。

Papertrack cron: scans ~30m; outcomes hourly → `~/trading_scanner_service/data/signals.jsonl`.
Correlated-sample rule: 11 crypto are BTC-beta — cluster same-day same-direction alts as ~one sample before significance talk.

## Handoff verification

Never accept Codex/external relayed read into the live plan. Refetch price + M1/M5; state gap already made; rebuild entry/stop/management; re-anchor stop beyond structure extreme + ATR buffer (scanner uses 0.25×ATR).

## Dashboard vocab aliases

`POI` ≈ `fvg_entry_zone`; `DOL` ≈ `dol_target`/`tp`; trigger ≈ `ltf_mss`; plus `daily_bias_aligned`. Derive missing RR from sourced numbers only.
