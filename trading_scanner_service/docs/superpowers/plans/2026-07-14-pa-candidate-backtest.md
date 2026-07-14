# PA Candidate Track Backtest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run a preregistered, no-lookahead M15/M5 backtest that compares the current ICT sweep candidate path with three PA Agent-inspired candidate tracks and a deterministic one-ticket merged selector.

**Architecture:** A single importable research module owns immutable experiment configuration, causal history loading/resampling, candidate generation, order settlement, portfolio selection, metrics, and report writing. The production scanner is called only as a read-only ICT decision function on frozen prefixes; PA tracks use existing structure helpers plus focused causal primitives in the backtest module. Unit tests exercise each causal boundary before the full 24-symbol run writes JSONL/JSON/Markdown artifacts under the external history tree.

**Tech Stack:** Python 3.10 standard library, `pytest`, existing `scanner_service.sources.Bar`, existing `scanner_service.scanner.scan_symbol`, existing `scanner_service.structure` helpers.

## Global Constraints

- Production files `scanner_service/scanner.py`, live API behavior, candidate push behavior, skill policy, candidates database, and trade journal must not change.
- History root is `/home/ubuntu/trading_scanner_service/data/history`.
- Universe is exactly AUDUSD, BTC, DOGE, ETH, EURUSD, GBPUSD, HYPE, NAS100, NZDUSD, PEPE, SOL, SUI, TAO, US30, US500, USDCAD, USDCHF, USDJPY, WLD, XAGUSD, XAUUSD, XRP, XTIUSD, and ZEC.
- Evaluation decision timestamps run from `2026-03-12 15:30:00 UTC` through `2026-07-10 15:45:00 UTC`, inclusive.
- Candidate timeframe is M15; execution timeframe is M5.
- An M15 bar timestamp is its open time. It becomes visible only at `ts + 900`; the decision timestamp is that close time, and no order may fill before an M5 bar whose open is at or after the decision timestamp.
- H1 and H4 are resampled from M15 with left-closed UTC buckets and become visible only after every source M15 bar in the bucket has closed.
- A D1 row is visible only at `row.ts + 86400 <= decision_ts`.
- Swing `i` is invisible until `i + SWING_K` has closed; appending future bars must not change candidates with `decision_ts` before the append point.
- Market orders fill at the next eligible M5 open. Stop and limit orders fill only on a later eligible M5 touch. Same-bar stop and target resolves as stop first.
- Stops and targets are frozen when the ticket is emitted; the hard stop is never widened.
- Gross, primary, and stress round-trip costs are exactly `0.00R`, `0.05R`, and `0.10R`; promotion uses `0.05R`.
- The first target must have gross RR at least `1.0`; a runner cannot rescue a failing first target.
- Maximum hold is `48` M5 bars for PA trend/channel and ICT tickets, `72` M5 bars for PA range/retest tickets, and `48` M5 bars for PA second-entry/failed-breakout tickets.
- Pending entry validity is `12` M5 bars for all stop and limit orders.
- Within-symbol campaign deduplication suppresses the same source, direction, structural anchor, and trigger for `12` M15 bars.
- The merged selector permits one new ticket per decision timestamp and one open selected ticket per symbol.
- The first run is evaluation only. Do not alter thresholds and rerun after seeing results.
- Output artifacts are written to `/home/ubuntu/trading_scanner_service/data/backtests/pa_candidate_tracks/`.

---

### Task 1: Causal History And Context Layer

**Files:**
- Create: `trading_scanner_service/scripts/backtest_pa_candidate_tracks_20260714.py`
- Create: `trading_scanner_service/tests/test_pa_candidate_backtest.py`

**Interfaces:**
- Produces: `ExperimentConfig`, `HistoryBundle`, `load_jsonl_bars(path)`, `load_history(root, symbol, config)`, `visible_prefix(bars, decision_ts, seconds)`, `resample_closed(bars, seconds, decision_ts)`, and `iter_decision_points(bundle, config)`.
- `HistoryBundle` fields: `symbol: str`, `m5: tuple[Bar, ...]`, `m15: tuple[Bar, ...]`, `d1: tuple[Bar, ...]`.
- `iter_decision_points` yields immutable `DecisionPoint(symbol, decision_ts, m15_index, m15, m5, h1, h4, d1)`.

- [ ] **Step 1: Write failing loader and visibility tests**

```python
def test_visible_prefix_requires_bar_close():
    bars = (bar(0, 10, 11, 9, 10), bar(900, 10, 12, 9, 11))
    assert visible_prefix(bars, 900, 900) == (bars[0],)
    assert visible_prefix(bars, 1799, 900) == (bars[0],)
    assert visible_prefix(bars, 1800, 900) == bars


def test_d1_bar_is_visible_only_after_full_close():
    bars = (bar(0, 10, 11, 9, 10),)
    assert visible_prefix(bars, 86399, 86400) == ()
    assert visible_prefix(bars, 86400, 86400) == bars


def test_iter_decision_points_uses_m15_close_and_next_m5_execution_boundary():
    bundle = bundle_with_regular_bars(
        m15_opens=[0, 900, 1800],
        m5_opens=[0, 300, 600, 900, 1200, 1500, 1800],
    )
    point = list(iter_decision_points(bundle, config(start_ts=900, end_ts=900)))[0]
    assert point.decision_ts == 900
    assert point.m15[-1].ts == 0
    assert point.m5[-1].ts == 600
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest trading_scanner_service/tests/test_pa_candidate_backtest.py -q`

Expected: collection fails because `backtest_pa_candidate_tracks_20260714` does not exist.

- [ ] **Step 3: Implement immutable configuration and JSONL loading**

```python
@dataclass(frozen=True)
class ExperimentConfig:
    symbols: tuple[str, ...] = SYMBOLS
    start_ts: int = 1773329400
    end_ts: int = 1783698300
    m5_seconds: int = 300
    m15_seconds: int = 900
    h1_seconds: int = 3600
    h4_seconds: int = 14400
    d1_seconds: int = 86400
    warmup_m15: int = 120
    min_first_target_rr: float = 1.0
    pending_bars: int = 12
    campaign_bars: int = 12
    costs_r: tuple[float, ...] = (0.0, 0.05, 0.10)


def load_jsonl_bars(path: Path) -> tuple[Bar, ...]:
    rows = []
    with path.open("r", encoding="utf-8-sig") as fh:
        for line in fh:
            raw = json.loads(line)
            rows.append(Bar(
                ts=int(raw["ts"]),
                open=float(raw["open"]),
                high=float(raw["high"]),
                low=float(raw["low"]),
                close=float(raw["close"]),
                volume=float(raw.get("volume", 0.0)),
            ))
    deduped = {row.ts: row for row in rows}
    return tuple(deduped[key] for key in sorted(deduped))
```

- [ ] **Step 4: Implement close-time visibility and causal resampling**

```python
def visible_prefix(bars: Sequence[Bar], decision_ts: int, seconds: int) -> tuple[Bar, ...]:
    return tuple(bar for bar in bars if bar.ts + seconds <= decision_ts)


def resample_closed(bars: Sequence[Bar], seconds: int, decision_ts: int) -> tuple[Bar, ...]:
    buckets: dict[int, list[Bar]] = defaultdict(list)
    for bar in bars:
        if bar.ts + 900 > decision_ts:
            continue
        bucket = bar.ts - (bar.ts % seconds)
        if bucket + seconds <= decision_ts:
            buckets[bucket].append(bar)
    return tuple(
        Bar(
            ts=bucket,
            open=group[0].open,
            high=max(item.high for item in group),
            low=min(item.low for item in group),
            close=group[-1].close,
            volume=sum(item.volume for item in group),
        )
        for bucket, group in sorted(buckets.items())
        if len(group) == seconds // 900
    )
```

- [ ] **Step 5: Run focused tests and commit**

Run: `python -m pytest trading_scanner_service/tests/test_pa_candidate_backtest.py -q`

Expected: loader/visibility/resampling tests pass.

```bash
git add trading_scanner_service/scripts/backtest_pa_candidate_tracks_20260714.py trading_scanner_service/tests/test_pa_candidate_backtest.py
git commit -m "test: add causal PA backtest history layer"
```

### Task 2: Candidate And Ticket Primitives

**Files:**
- Modify: `trading_scanner_service/scripts/backtest_pa_candidate_tracks_20260714.py`
- Modify: `trading_scanner_service/tests/test_pa_candidate_backtest.py`

**Interfaces:**
- Produces: `Candidate`, `Ticket`, `Settlement`, `confirmed_swings(bars)`, `ema_series(bars, period)`, `always_in_direction(bars)`, `classify_environment(bars, direction)`, `stable_range(bars)`, `candidate_to_ticket(candidate, config)`, and `dedupe_candidates(candidates, config)`.
- `Candidate` includes `candidate_id`, `symbol`, `track`, `setup`, `direction`, `decision_ts`, `order_type`, `entry`, `stop`, `target`, `runner`, `anchor`, `trigger_ts`, `trigger_freshness`, `target_room_atr`, `stop_clarity`, `hard_vetoes`, and `evidence`.

- [ ] **Step 1: Write failing swing, Always-In, range, RR, and dedupe tests**

```python
def test_confirmed_swings_hide_unconfirmed_right_edge():
    bars = swing_fixture()
    assert [s.index for s in confirmed_swings(bars[:5])] == []
    assert [s.index for s in confirmed_swings(bars[:6])] == [3]


def test_always_in_direction_requires_near_side_ratio_and_ema_slope():
    assert always_in_direction(clean_bull_bars(30)) == "LONG"
    assert always_in_direction(clean_bear_bars(30)) == "SHORT"
    assert always_in_direction(overlapping_range_bars(30)) == "NEUTRAL"


def test_stable_range_uses_confirmed_boundaries_and_rejects_midrange():
    bounds = stable_range(range_fixture())
    assert bounds is not None
    assert bounds.low < bounds.mid < bounds.high
    assert not near_range_edge(bounds.mid, bounds, atr=1.0)


def test_ticket_rejects_first_target_below_one_r():
    weak = candidate(entry=100, stop=102, target=99)
    assert candidate_to_ticket(weak, config()) is None


def test_campaign_dedupe_keeps_first_identical_event():
    one = candidate(candidate_id="a", decision_ts=900, anchor=100)
    two = replace(one, candidate_id="b", decision_ts=1800)
    assert dedupe_candidates([one, two], config(campaign_bars=12)) == [one]
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest trading_scanner_service/tests/test_pa_candidate_backtest.py -q`

Expected: new tests fail because primitives are missing.

- [ ] **Step 3: Implement locked PA facts**

Implement these exact rules:

- `always_in_direction`: use the PA Agent near window of `8` bars, require at
  least `65%` of closes on one EMA20 side, require the EMA20 slope over `10`
  bars in the same direction, require the final close on that side, and return
  `NEUTRAL` when `barbwire` is true.
- `classify_environment`: label `spike` for at least two final strong
  directional bars with at most `30%` overlap; otherwise prefer the existing
  `micro_channel` result; label `tight_channel` for at least six of eight
  directional closes with pullbacks no longer than two bars and mean overlap
  below `0.45`; label `normal_channel` for Always-In with ordered confirmed
  swings; label `broad_channel` when that structure has pullbacks longer than
  two bars or EMA crossings; label `range` when `stable_range` exists; label
  `chaos` when `barbwire` is true; otherwise return `unknown`.
- `stable_range`: inspect the last `48` closed M15 bars, require at least two
  confirmed swing highs and two confirmed swing lows, require each edge's
  swings to cluster within `0.50 ATR`, require width of at least `2 ATR`,
  require at least two touches per edge, and reject any boundary with a close
  accepted more than `0.25 ATR` outside it.

- [ ] **Step 4: Implement ticket legality and campaign deduplication**

`candidate_to_ticket` must reject non-finite values, wrong-sided stops/targets, risk `<= 0`, first-target RR `< 1.0`, any hard veto, and stop distance `< 0.20 ATR`. It assigns `hold_bars` from the source track and records gross/primary/stress planned RR.

`dedupe_candidates` uses `(symbol, track, direction, round(anchor / max(atr, 1e-12), 2), trigger_ts)` as the event key and suppresses later same-campaign candidates inside `12` M15 bars.

- [ ] **Step 5: Run tests and commit**

Run: `python -m pytest trading_scanner_service/tests/test_pa_candidate_backtest.py -q`

Expected: all primitive tests pass.

```bash
git add trading_scanner_service/scripts/backtest_pa_candidate_tracks_20260714.py trading_scanner_service/tests/test_pa_candidate_backtest.py
git commit -m "feat: add PA candidate ticket primitives"
```

### Task 3: ICT Baseline Replay

**Files:**
- Modify: `trading_scanner_service/scripts/backtest_pa_candidate_tracks_20260714.py`
- Modify: `trading_scanner_service/tests/test_pa_candidate_backtest.py`

**Interfaces:**
- Consumes: `DecisionPoint`, `Candidate`, `candidate_to_ticket`.
- Produces: `generate_ict_candidate(point, config) -> Candidate | None`.

- [ ] **Step 1: Write failing ICT replay tests**

```python
def test_ict_candidate_calls_production_scanner_on_frozen_prefix(monkeypatch):
    seen = {}
    def fake_scan(symbol, bars, tf, htf, d1, now):
        seen["last_ts"] = bars[-1].ts
        return ready_ict_payload()
    monkeypatch.setattr(module, "production_scan_symbol", fake_scan)
    result = generate_ict_candidate(decision_point(), config())
    assert seen["last_ts"] + 900 == result.decision_ts


def test_ict_candidate_requires_m5_entry_confirm_and_uses_its_frozen_numbers():
    payload = ready_ict_payload(
        entry_confirm_bar={"trigger_price": 99, "frozen_level": 100, "confirm_bar_ts": 600},
        sl=102,
        dol=96,
    )
    result = generate_ict_candidate(decision_point(ict_payload=payload), config())
    assert result.order_type == "stop"
    assert result.entry == 99
    assert result.stop == 102
    assert result.target == 96
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest trading_scanner_service/tests/test_pa_candidate_backtest.py -q`

Expected: ICT generator tests fail.

- [ ] **Step 3: Implement production-compatible frozen replay**

For each decision point:

1. Calculate H4 `htf_bias(point.h4)`.
2. Calculate D1 `(d1_spike, htf_bias)` from `point.d1`.
3. Call production `scan_symbol(symbol, point.m15[-120:], tf="M15", htf=h4_context, d1=d1_context, now=point.decision_ts)`.
4. If the parent qualifies for LTF confirmation, call production `apply_ltf_confirm_bar` with `point.m5[-120:]`.
5. Emit only when direction is LONG/SHORT, sweep is true, `entry_confirm_bar` exists, it is M5 `entry_confirm`, no chase/stale/crowded hard veto exists, and the first-target ticket passes RR.
6. Use `entry_confirm_bar.trigger_price`, production `sl`, production `dol`, and `dol_runner`; do not reconstruct those values.

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest trading_scanner_service/tests/test_pa_candidate_backtest.py -q`

Expected: ICT tests pass.

```bash
git add trading_scanner_service/scripts/backtest_pa_candidate_tracks_20260714.py trading_scanner_service/tests/test_pa_candidate_backtest.py
git commit -m "feat: replay ICT baseline on frozen prefixes"
```

### Task 4: PA Trend And Channel Pullback Track

**Files:**
- Modify: `trading_scanner_service/scripts/backtest_pa_candidate_tracks_20260714.py`
- Modify: `trading_scanner_service/tests/test_pa_candidate_backtest.py`

**Interfaces:**
- Produces: `generate_pa_trend_candidate(point, config) -> Candidate | None`.

- [ ] **Step 1: Write failing trend candidate tests**

```python
def test_trend_track_emits_h2_pullback_without_ict_sweep():
    result = generate_pa_trend_candidate(point_with_h2_bull_pullback(), config())
    assert result.track == "pa_trend"
    assert result.direction == "LONG"
    assert result.setup == "h2_pullback"
    assert result.order_type in {"stop", "limit"}


def test_trend_track_rejects_counter_always_in_and_climax_chase():
    assert generate_pa_trend_candidate(point_with_countertrend_signal(), config()) is None
    assert generate_pa_trend_candidate(point_with_bull_climax_at_high(), config()) is None
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest trading_scanner_service/tests/test_pa_candidate_backtest.py -q`

Expected: trend-track tests fail.

- [ ] **Step 3: Implement locked trend/channel entry definition**

Emit only when:

- M15 `always_in_direction` is LONG or SHORT;
- H1/H4 bias is not the opposite direction;
- environment is spike, micro_channel, tight_channel, normal_channel, or broad_channel;
- `barbwire` is false and `climax_risk` in the candidate direction is false;
- price pulled back to EMA20 within `0.35 ATR`, the prior bar extreme within `0.20 ATR`, or the latest confirmed channel swing within `0.35 ATR`;
- `hl_count` is at least `1`; label count `>=2` as H2/L2 and count `1` as H1/L1;
- the final M15 signal bar quality is `strong` or `ok`.

Use a next-bar M5 market entry for a strong signal bar. Use a limit at the nearest real pullback anchor for an `ok` signal bar. Stop goes `0.25 ATR` beyond the pullback swing or signal extreme. First target is the nearest confirmed with-trend swing beyond entry; if unavailable, use the prior channel extreme, never an arithmetic projection. Runner is the next confirmed swing.

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest trading_scanner_service/tests/test_pa_candidate_backtest.py -q`

Expected: trend-track tests pass.

```bash
git add trading_scanner_service/scripts/backtest_pa_candidate_tracks_20260714.py trading_scanner_service/tests/test_pa_candidate_backtest.py
git commit -m "feat: add PA trend pullback candidate track"
```

### Task 5: PA Range Edge And Breakout Retest Track

**Files:**
- Modify: `trading_scanner_service/scripts/backtest_pa_candidate_tracks_20260714.py`
- Modify: `trading_scanner_service/tests/test_pa_candidate_backtest.py`

**Interfaces:**
- Produces: `generate_pa_range_candidate(point, config) -> Candidate | None`.

- [ ] **Step 1: Write failing edge and retest tests**

```python
def test_range_track_emits_edge_reversal_but_not_midrange():
    edge = generate_pa_range_candidate(point_at_range_low_with_bull_signal(), config())
    assert edge.setup == "range_edge"
    assert edge.direction == "LONG"
    assert generate_pa_range_candidate(point_at_range_mid(), config()) is None


def test_range_track_emits_confirmed_breakout_retest_only_after_retest_close():
    assert generate_pa_range_candidate(point_on_breakout_bar(), config()) is None
    retest = generate_pa_range_candidate(point_after_breakout_retest(), config())
    assert retest.setup == "breakout_retest"
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest trading_scanner_service/tests/test_pa_candidate_backtest.py -q`

Expected: range-track tests fail.

- [ ] **Step 3: Implement locked range-edge and breakout-retest definitions**

For an edge reversal, require `stable_range`, final price in the outer `20%` of range width or within `0.35 ATR` of an edge, directional `strong` or `ok` signal bar away from the edge, and no close accepted `0.25 ATR` beyond the stop side. Entry is next M5 open for a strong signal or edge limit for an `ok` signal. Stop is `0.25 ATR` outside the edge/signal extreme. First target is range midpoint; runner is opposite edge.

For a breakout retest, require a close at least `0.25 ATR` outside a previously stable boundary, then within the next `8` M15 bars a touch within `0.35 ATR` of that frozen boundary and a close back in breakout direction. Entry is a stop beyond the retest signal bar. Stop is `0.25 ATR` through the retest extreme. First target is the nearest confirmed structure beyond the breakout; do not use measured moves. `barbwire` is negative evidence and blocks breakout-retest candidates, but never creates a trade.

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest trading_scanner_service/tests/test_pa_candidate_backtest.py -q`

Expected: range-track tests pass.

```bash
git add trading_scanner_service/scripts/backtest_pa_candidate_tracks_20260714.py trading_scanner_service/tests/test_pa_candidate_backtest.py
git commit -m "feat: add PA range and retest candidate track"
```

### Task 6: PA Second Entry And Failed Breakout Track

**Files:**
- Modify: `trading_scanner_service/scripts/backtest_pa_candidate_tracks_20260714.py`
- Modify: `trading_scanner_service/tests/test_pa_candidate_backtest.py`

**Interfaces:**
- Produces: `generate_pa_boundary_candidate(point, config) -> Candidate | None`, `detect_wedge_three_push(bars, direction)`, and `detect_failed_breakout(bars, bounds)`.

- [ ] **Step 1: Write failing H2/L2, failed-breakout, and wedge tests**

```python
def test_boundary_track_requires_second_entry_or_failed_breakout_trigger():
    assert generate_pa_boundary_candidate(point_with_wedge_label_only(), config()) is None
    h2 = generate_pa_boundary_candidate(point_with_range_edge_h2(), config())
    assert h2.setup == "h2_boundary"


def test_failure_of_failed_breakout_emits_with_final_failure_direction():
    result = generate_pa_boundary_candidate(point_with_failure_of_failure(), config())
    assert result.setup == "failure_of_failure"
    assert result.direction == "LONG"
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest trading_scanner_service/tests/test_pa_candidate_backtest.py -q`

Expected: boundary-track tests fail.

- [ ] **Step 3: Implement locked boundary trigger definitions**

Candidates are valid only near a stable range edge, a frozen breakout boundary, EMA20 in a broad channel, or a confirmed channel swing.

- H2/L2: use `hl_count >= 2` in the Always-In direction after a pullback; trigger bar must be `strong` or `ok`.
- Failed breakout: a wick or close exceeds a frozen boundary, then closes back inside within `3` M15 bars with a directional signal bar.
- Failure of failure: after the failed-breakout signal, price closes beyond that signal bar extreme in the original breakout direction within `3` M15 bars.
- Wedge: three confirmed pushes with the third extension smaller than the second; it is evidence only and must accompany H2/L2, failed breakout, or failure-of-failure.

Use stop entries beyond signal-bar extremes. Stop is `0.25 ATR` beyond the structure extreme. First target is midpoint/nearest confirmed structure for edge reversals and nearest confirmed structure beyond the boundary for failure-of-failure. Runner is optional and never affects legality.

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest trading_scanner_service/tests/test_pa_candidate_backtest.py -q`

Expected: boundary-track tests pass.

```bash
git add trading_scanner_service/scripts/backtest_pa_candidate_tracks_20260714.py trading_scanner_service/tests/test_pa_candidate_backtest.py
git commit -m "feat: add PA second-entry boundary track"
```

### Task 7: M5 Settlement, Costs, And Prefix Invariance

**Files:**
- Modify: `trading_scanner_service/scripts/backtest_pa_candidate_tracks_20260714.py`
- Modify: `trading_scanner_service/tests/test_pa_candidate_backtest.py`

**Interfaces:**
- Produces: `settle_ticket(ticket, future_m5, costs_r) -> Settlement`, `run_symbol_candidates(bundle, config)`, and `assert_prefix_invariance(bundle, config, cut_ts)`.

- [ ] **Step 1: Write failing execution tests**

```python
def test_market_entry_fills_at_next_eligible_m5_open():
    ticket = ticket(order_type="market", decision_ts=900)
    result = settle_ticket(ticket, [bar(900, 101, 102, 99, 100)], COSTS)
    assert result.entry_ts == 900
    assert result.entry == 101


def test_same_bar_stop_and_target_resolves_stop_first():
    result = settle_ticket(
        ticket(direction="LONG", order_type="limit", entry=100, stop=98, target=104),
        [bar(900, 100, 105, 97, 103)],
        COSTS,
    )
    assert result.outcome == "sl"
    assert result.gross_r == -1.0


def test_target_before_unfilled_limit_is_missed_alpha():
    result = settle_ticket(
        ticket(direction="SHORT", order_type="limit", entry=105, stop=107, target=100),
        [bar(900, 103, 104, 99, 100)],
        COSTS,
    )
    assert not result.filled
    assert result.outcome == "missed_alpha"


def test_prefix_invariance_keeps_all_pre_cut_candidates_identical():
    full = run_symbol_candidates(prefix_fixture(full=True), config())
    prefix = run_symbol_candidates(prefix_fixture(full=False), config())
    cut = prefix_fixture(full=False).m15[-1].ts + 900
    assert [c for c in full if c.decision_ts <= cut] == prefix
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest trading_scanner_service/tests/test_pa_candidate_backtest.py -q`

Expected: settlement and invariance tests fail.

- [ ] **Step 3: Implement conservative order settlement**

Process only M5 bars with `bar.ts >= ticket.decision_ts`. Pending stop/limit orders expire after `12` bars. Market entry fills at the first eligible open. On a fill bar, test stop before target. Before a pending fill, if target trades without touching entry, record `missed_alpha`. Filled unresolved trades close at the final hold-window close. Record fill latency, exit timestamp, gross R, net R at each cost, MFE R, MAE R, and bars held.

- [ ] **Step 4: Implement actual prefix-invariance audit**

For every symbol, rerun candidate generation on prefixes ending at 25%, 50%, and 75% of the evaluation interval. Compare serialized candidates whose decision timestamps are not later than each cut against the full run. Any mismatch raises and prevents report promotion.

- [ ] **Step 5: Run tests and commit**

Run: `python -m pytest trading_scanner_service/tests/test_pa_candidate_backtest.py -q`

Expected: settlement and invariance tests pass.

```bash
git add trading_scanner_service/scripts/backtest_pa_candidate_tracks_20260714.py trading_scanner_service/tests/test_pa_candidate_backtest.py
git commit -m "feat: add conservative M5 ticket settlement"
```

### Task 8: Selector, Metrics, Reports, And Promotion Verdict

**Files:**
- Modify: `trading_scanner_service/scripts/backtest_pa_candidate_tracks_20260714.py`
- Modify: `trading_scanner_service/tests/test_pa_candidate_backtest.py`

**Interfaces:**
- Produces: `select_one_ticket(candidates, open_until)`, `summarize_trades(trades, cost_r)`, `build_comparisons(candidates, settlements, selected)`, `promotion_verdict(track_report)`, `write_artifacts(result, output_dir)`, and `main(argv=None)`.

- [ ] **Step 1: Write failing selector and metric tests**

```python
def test_selector_is_deterministic_and_uses_only_predeclared_fields():
    chosen = select_one_ticket([lower_quality_pa(), higher_quality_ict()], {})
    assert chosen.track == "ict"
    assert select_one_ticket(list(reversed([lower_quality_pa(), higher_quality_ict()])), {}).candidate_id == chosen.candidate_id


def test_selector_blocks_second_open_ticket_for_same_symbol():
    assert select_one_ticket([candidate(symbol="BTC")], {"BTC": 9999}) is None


def test_promotion_requires_all_locked_gates():
    report = qualifying_track_report(unique_fills=99)
    assert promotion_verdict(report) == "insufficient_evidence"
    report = qualifying_track_report(unique_fills=100, displacement_cost=-0.01)
    assert promotion_verdict(report) == "reject"
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest trading_scanner_service/tests/test_pa_candidate_backtest.py -q`

Expected: selector/report tests fail.

- [ ] **Step 3: Implement deterministic one-ticket selector**

Sort candidates at one decision timestamp by:

1. no hard veto;
2. primary first-target net RR descending;
3. target room in ATR descending;
4. trigger freshness descending;
5. stop clarity descending;
6. source priority `ict`, `pa_trend`, `pa_range`, `pa_boundary`;
7. symbol and candidate ID ascending as stable tie-breakers.

Exclude any candidate whose symbol already has an open selected ticket. Record every ICT candidate displaced by PA and every PA candidate with no ICT candidate on the same symbol within `4` M15 bars.

- [ ] **Step 4: Implement required metrics and promotion gates**

Calculate candidate count, fill/no-fill/missed-alpha rates, win rate, average/total gross and net R, profit factor, median R, MFE/MAE, maximum drawdown, monthly and per-symbol tables, ICT overlap, unique PA net R, and displacement cost.

Promotion requires all of:

```python
eligible = (
    unique_fills >= 100
    and primary_net_avg_r > 0
    and primary_profit_factor > 1.05
    and positive_months >= max(2, math.ceil(month_count / 2))
    and top_symbol_abs_net_share <= 0.50
    and merged_net_avg_r >= ict_net_avg_r - 0.05
    and displacement_cost_r >= 0
    and causality_passed
    and prefix_invariance_passed
)
```

If sample is below 100, verdict is `insufficient_evidence`. Otherwise any failed gate is `reject`; all gates pass is `promote_to_shadow`. A positive primary result that becomes negative at `0.10R` is labeled `cost_sensitive`.

- [ ] **Step 5: Write machine-readable and Markdown artifacts**

Write:

- `config.json`;
- `candidates.jsonl`;
- `trades.jsonl`;
- `selected_trades.jsonl`;
- `summary.json`;
- `report.md`.

Use atomic temporary-file replacement. Include the Git commit, exact interval, data counts, all locked thresholds, skip counts, causality results, aggregate/track/month/symbol tables, displacement ledger, and one verdict per PA track.

- [ ] **Step 6: Run tests and commit**

Run: `python -m pytest trading_scanner_service/tests/test_pa_candidate_backtest.py -q`

Expected: all backtest-specific tests pass.

```bash
git add trading_scanner_service/scripts/backtest_pa_candidate_tracks_20260714.py trading_scanner_service/tests/test_pa_candidate_backtest.py
git commit -m "feat: add PA backtest selection and reporting"
```

### Task 9: Full Verification And Actual 24-Symbol Run

**Files:**
- Generated only: `/home/ubuntu/trading_scanner_service/data/backtests/pa_candidate_tracks/*`

**Interfaces:**
- Consumes the completed backtest module and external history.
- Produces the final preregistered result artifacts; no source file changes are allowed after seeing these results.

- [ ] **Step 1: Run focused and full test suites**

Run:

```bash
python -m pytest trading_scanner_service/tests/test_pa_candidate_backtest.py -q
python -m pytest trading_scanner_service/tests -q
python -m pytest contract_tests -q
```

Expected: all tests pass with no collection errors.

- [ ] **Step 2: Run the locked backtest once**

Run:

```bash
python trading_scanner_service/scripts/backtest_pa_candidate_tracks_20260714.py \
  --history-root /home/ubuntu/trading_scanner_service/data/history \
  --output-dir /home/ubuntu/trading_scanner_service/data/backtests/pa_candidate_tracks
```

Expected: 24 symbols load, all causality/prefix checks pass, and six artifacts are written.

- [ ] **Step 3: Audit output integrity**

Run:

```bash
python -m json.tool /home/ubuntu/trading_scanner_service/data/backtests/pa_candidate_tracks/config.json
python -m json.tool /home/ubuntu/trading_scanner_service/data/backtests/pa_candidate_tracks/summary.json
wc -l /home/ubuntu/trading_scanner_service/data/backtests/pa_candidate_tracks/candidates.jsonl
wc -l /home/ubuntu/trading_scanner_service/data/backtests/pa_candidate_tracks/trades.jsonl
wc -l /home/ubuntu/trading_scanner_service/data/backtests/pa_candidate_tracks/selected_trades.jsonl
git status --short
```

Expected: JSON parses, row counts match `summary.json`, and production scanner/skill/API files are unchanged on the backtest branch.

- [ ] **Step 4: Perform adversarial review**

Inspect:

- candidate timestamps versus M15 close timestamps;
- entry timestamps versus next eligible M5 bars;
- swing confirmation visibility;
- same-bar stop priority;
- duplicate event/campaign counts;
- PA-versus-ICT displacement examples;
- symbol/month concentration;
- result changes from `0.00R` to `0.05R` to `0.10R`;
- absence of production file changes.

- [ ] **Step 5: Commit only source and test changes**

Do not commit external generated artifacts.

```bash
git status --short
git log --oneline --decorate -10
```

Expected: implementation commits are present; external reports remain outside the repository.
