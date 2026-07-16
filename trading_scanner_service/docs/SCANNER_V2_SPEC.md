# Scanner v2 规格落地状态（draft-2026-07-14b）

**总原则：判断归模型，数字归代码。** 扫描器不算 edge，不直下单。

| 模块 | 状态 | 位置 |
| --- | --- | --- |
| ① confirm_bar | **已上** 2026-07-14a | `structure.build_confirm_bar` |
| pushable / map vs entry TF | **已上** 2026-07-14b | `scanner.scan_symbol` |
| 父单 LTF confirm | **已上** 2026-07-14c | `apply_ltf_confirm_bar` + `server._attach_ltf_confirms` |
| ② 候选全量落库 + 裁决标注 | **已上** 2026-07-14d | `candidates_ledger.py` → `data/candidates.db` |
| ③ confluence_retest | **已上** 2026-07-14e | `confluence.py` + `server._scan_confluence` |
| ④ drilldown_chain + poi_scaled | **已上** 2026-07-14f | `drilldown.py` + `server._scan_drilldown` |
| ⑤ limit_zone | **已上** 2026-07-14g | `limit_zone.py` + `scan_symbol` 字段 |
| ⑥ improve_fill | **已上** 2026-07-14h | `improve_fill.py` → `confirm_bar.improve_fill` |

## 候选表 `candidates`

每轮 `run_scan` 写入全部候选快照（含未完整 setup）。

- `desk_verdict`: trade | conditional-wait | do_not_chase | no_trade | vetoed（机器可预填 veto 类 hint，桌面可覆盖）
- `veto_reason`: cycle_state | position | session | target_crowded | counter_htf | counter_d1 | stale | news | cisd_only | map_tf_not_entry | no_confirm_bar | no_ltf_confirm_bar | c_tier | other
- `outcome_r` / `outcome_note`: 事后机械回算或实盘

查询：`python3 -c "from scanner_service.candidates_ledger import stats_summary; print(stats_summary())"`

## 实施顺序（规格 §十，保持）

1. confirm_bar ✅  
2. 候选落库 ✅（本文件对应）  
3. confluence_retest ✅  
4. drilldown_chain + poi_scaled ✅  
5. limit_zone ✅ / improve_fill ✅  

**v2 六模块核心算术层全部落地**（confirm / ledger / confluence / drilldown / limit_zone / improve_fill）。  

**协议层 2026-07-14i（轻量）：** skill 三层宪法 + anomaly 定长筛单表 + track 双轨纪律；ledger 增 `track` / `model` / `anomaly`。Design-time 强模型岗位 = 流程，不扩扫描器模块。

### ④ 桌面用法（drilldown_chain）

- `setup_type=drilldown_chain`：H4 结构事件 → 同向 M5 确认 → M1 MSS/CISD（链内 CISD 合法）
- `chain.chain_status`：`awaiting_m5` | `awaiting_m1` | `chain_complete` | `m1_confirm_stale`
- 触发价只引用 `confirm_bar`（= M1 live confirm）；`null`/未 complete → 只给事件级 pending
- `poi_scaled`：多 tranche 元数据（总风险 ≤1R，须成交前声明）；**永不自动下单**
- `requires_desk_review=true` 恒真；C 层跳过；H4 确认 age >6 根作废

### ⑤ 桌面用法（limit_zone）

- 候选可选字段 `limit_zone`（非独立 setup_type）：深结构离屏限价算术
- 前置：已完成 sweep + 非 counter_htf + 非 stale/news + **现价已离开区**（深回踩几何）
- 字段：`zone` / `zone_source` / `refine`(CE50%) / `sl_anchor`+bar / `buffer` / `sl` / `mgmt` / `target` / `invalidate` / `valid_until`
- `zone_source` 只认 `sweep_extreme` + 地图层 FVG/OTE；**禁止 M1/M5 微观 array**
- **`requires_desk_review=true` 恒真；`never_auto_hang=true` — 永不直挂**
- 合法链路：扫描器出区 → 桌面 pipeline → 用户确认 → 挂单；持仓冲突时 flat 前不挂

### ⑥ 桌面用法（improve_fill）

- `confirm_bar.improve_fill` 可选子字段（非独立 setup）
- 前置：`confirm_bar` 非 null + `market_ok=true` + 入场 TF（M1/M5）+ 确认 K 内有 FVG
- 字段：`zone_tf` / `zone` / `zone_source` / `limit_price`(区**上沿**非 CE) / `fallback_bars=3` / `fallback=market_if_still_ok`
- **非默认路径**：`default_path=false`，`requires_user_opt_in=true`；仅用户点名浅改善时用
- 越过 `trigger_price` → 作废进 chase；超时未成交且市价仍 ok → 撤限转市价
- journal：`fill = market | improved | improved_timeout_market`

完整字段定义以飞书/对话中的 draft 规格为准；本文件只记落地状态。
