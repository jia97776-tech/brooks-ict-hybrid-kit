"""Anti-lookahead historical signal backtest for trading_scanner_service.

Reuses the PRODUCTION functions verbatim:
  - scanner_service.scanner.scan_symbol   (pure signal function)
  - scanner_service.structure.htf_bias    (H4 bias)
  - scanner_service.papertrack._resolve_one, _key, session_of  (settlement)

Replays decision points on the M15/H4 close-time axis, feeding scan_symbol
ONLY bars whose timestamp <= decision time t (never later), using the same
window sizes production uses:
  - M15 candidates: scan_symbol(..., tf="M15", htf=htf_bias(<=60 H4 bars<=t))
    window = last 240 M15 bars with ts<=t   (SCAN_MODES["both"]: ("M15",240))
  - H4 candidates:  scan_symbol(..., tf="H4", htf=None)
    window = last 180 H4 bars with ts<=t    (SCAN_MODES["both"]: ("H4",180))
  step: M15 advances 2 bars (~30min, matches cron */30 mode=both);
        H4 advances 1 bar.

Settlement uses only bars with ts > row["ts"], via the real _resolve_one,
exactly replicating fill/no_fill/expired/win/loss + scalp + mfe semantics.

Output is written ONLY under scratchpad/backtest_1m/ -- never touches the
production data/signals.jsonl.
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, "/home/ubuntu/trading_scanner_service")
from scanner_service.sources import Bar  # noqa: E402
from scanner_service.scanner import scan_symbol  # noqa: E402
from scanner_service.structure import htf_bias  # noqa: E402
from scanner_service import papertrack as pt  # noqa: E402

HERE = Path(__file__).resolve().parent
BARS_DIR = HERE / "bars"
OUT_JSONL = HERE / "signals_backtest.jsonl"
REPORT_MD = HERE / "report.md"
SELFCHECK_JSON = HERE / "selfcheck.json"

SYMBOLS = [
    "BTC", "ETH", "SOL", "DOGE",
    "XAUUSD", "XAGUSD", "XTIUSD",
    "NAS100", "US500", "US30",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
]

# production window sizes, from scanner_service/server.py SCAN_MODES["both"]
M15_WINDOW = 240
H4_WINDOW = 180
HTF_BIAS_WINDOW = 60          # server.py bias_of(): router.bars(symbol, "H4", 60)
M15_STEP = 2                  # 2 bars * 15min = 30min, matches cron */30
H4_STEP = 1

TARGET_DECISION_DAYS = 33     # within the requested 30-35 day window
TF_SECONDS = {"M15": 900, "H4": 14400}


def load_cached_bars(symbol: str, tf: str) -> list[Bar]:
    path = BARS_DIR / f"{symbol}_{tf}.jsonl"
    bars = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            bars.append(Bar(ts=d["ts"], open=d["open"], high=d["high"], low=d["low"],
                             close=d["close"], volume=d.get("volume", 0.0)))
    bars.sort(key=lambda b: b.ts)
    return bars


def trackable(cand: dict) -> bool:
    return (cand.get("state") in ("READY", "CONDITIONAL_READY")
            and cand.get("sl") is not None
            and cand.get("dol") is not None
            and cand.get("entry_ref") is not None)


def window_upto(bars: list[Bar], t: int, n: int) -> list[Bar]:
    """Last n bars with ts<=t. bars must be sorted ascending."""
    # bisect for the rightmost index with ts<=t
    lo, hi = 0, len(bars)
    while lo < hi:
        mid = (lo + hi) // 2
        if bars[mid].ts <= t:
            lo = mid + 1
        else:
            hi = mid
    end = lo  # exclusive; bars[:end] all have ts<=t
    start = max(0, end - n)
    return bars[start:end]


def h4_input_at(h4_bars: list[Bar], m15_bars: list[Bar], t: int, n: int) -> list[Bar]:
    """H4 bars as production would see them at wall time T = t+900 (the close of
    the decision M15 bar): fully closed H4 bars only, plus the in-progress H4
    bar SYNTHESIZED from M15 bars up to T — never its final (future) OHLC.

    Fix for lookahead found 2026-07-02: bar ts is OPEN time, so `ts <= t`
    included the still-forming H4 bar with its completed future OHLC (up to
    ~3h45m of leak) — directly contaminating htf_bias/counter_htf."""
    T = t + TF_SECONDS["M15"]
    win = window_upto(h4_bars, t, n + 1)
    closed = [b for b in win if b.ts + TF_SECONDS["H4"] <= T]
    forming = [b for b in win if b.ts + TF_SECONDS["H4"] > T]
    if forming:
        p = forming[-1]
        seg = [b for b in m15_bars if p.ts <= b.ts <= t]
        if seg:
            closed = closed + [Bar(ts=p.ts, open=seg[0].open,
                                   high=max(b.high for b in seg),
                                   low=min(b.low for b in seg),
                                   close=seg[-1].close,
                                   volume=sum(b.volume for b in seg))]
    return closed[-n:]


def build_row(cand: dict, t: int, model: str = "poi_retest") -> dict:
    return {
        "symbol": cand["symbol"], "tf": cand["tf"], "direction": cand["direction"],
        "side": cand["direction"], "state": cand["state"], "price": cand["price"],
        "entry_ref": cand["entry_ref"], "sl": cand["sl"], "dol": cand["dol"],
        "dol_runner": cand.get("dol_runner"), "rr": cand["rr"], "rr_now": cand.get("rr_now"),
        "late": cand.get("late", False), "target_crowded": cand.get("target_crowded", False),
        "swept_level": cand.get("swept_level"), "mss": cand.get("mss"), "cisd": cand.get("cisd"),
        "reason": cand.get("reason"), "htf_bias": cand.get("htf_bias"),
        "counter_htf": cand.get("counter_htf", False), "mgmt": cand.get("mgmt"),
        "poi": cand.get("poi"), "atr": cand.get("atr"), "equal_liquidity": cand.get("equal_liquidity"),
        "ts": t, "session": pt.session_of(t), "model": model,
        "outcome": "pending", "filled": False, "fill_ts": None, "resolve_ts": None,
        "result_r": None, "mfe_r": None, "scalp_r": None,
    }


def resolve_row(row: dict, bars_for_tf: list[Bar], now: int) -> None:
    pt._resolve_one(row, bars_for_tf, now)


def run_symbol_tf(symbol: str, tf: str, m15_bars: list[Bar], h4_bars: list[Bar],
                   decision_start: int, decision_end: int, now: int) -> tuple[list[dict], dict]:
    """Walk the decision timeline for one (symbol, tf), applying pending-dedup
    and full settlement. Returns (recorded_rows, coverage_meta)."""
    if tf == "M15":
        bars, window_n, step = m15_bars, M15_WINDOW, M15_STEP
    else:
        bars, window_n, step = h4_bars, H4_WINDOW, H4_STEP

    # first index with ts >= decision_start
    idxs = [i for i, b in enumerate(bars) if decision_start <= b.ts <= decision_end]
    key_state: dict[tuple, int | None] = {}
    recorded: list[dict] = []
    n_decisions = 0
    for pos in range(0, len(idxs), step):
        i = idxs[pos]
        t = bars[i].ts
        n_decisions += 1
        window = window_upto(bars, t, window_n)
        htf_arg = None
        if tf == "M15":
            h4_win = h4_input_at(h4_bars, m15_bars, t, HTF_BIAS_WINDOW)
            htf_arg = htf_bias(h4_win) if h4_win else ("NEUTRAL", "no H4 bars yet")
        cand = scan_symbol(symbol, window, tf=tf, htf=htf_arg)
        if not trackable(cand):
            continue
        key = pt._key(cand)
        state = key_state.get(key, "never")
        if state == "never" or (state is not None and state < t):
            row = build_row(cand, t)
            resolve_row(row, bars, now)
            recorded.append(row)
            key_state[key] = row["resolve_ts"] if row["outcome"] != "pending" else None

    meta = {
        "symbol": symbol, "tf": tf,
        "n_decision_points": n_decisions,
        "decision_start": decision_start, "decision_end": decision_end,
        "decision_days": round((decision_end - decision_start) / 86400, 2) if n_decisions else 0.0,
        "n_recorded": len(recorded),
    }
    return recorded, meta


def compute_decision_bounds(symbol: str, tf: str, m15_bars: list[Bar], h4_bars: list[Bar],
                             now: int) -> tuple[int, int]:
    target_start = now - TARGET_DECISION_DAYS * 86400
    if tf == "M15":
        m15_floor = m15_bars[0].ts + M15_WINDOW * TF_SECONDS["M15"] if m15_bars else now
        h4_floor = h4_bars[0].ts + HTF_BIAS_WINDOW * TF_SECONDS["H4"] if h4_bars else now
        start = max(target_start, m15_floor, h4_floor)
        end = m15_bars[-1].ts if m15_bars else now
    else:
        h4_floor = h4_bars[0].ts + H4_WINDOW * TF_SECONDS["H4"] if h4_bars else now
        start = max(target_start, h4_floor)
        end = h4_bars[-1].ts if h4_bars else now
    return start, end


# ---------------------------------------------------------------------------
# self-checks
# ---------------------------------------------------------------------------

def selfcheck_truncation_invariance(all_bars_cache: dict, samples: int = 10, seed: int = 7) -> dict:
    """For random (symbol, t), compare scan_symbol output built from:
      A) window truncated directly to t (last N bars with ts<=t)
      B) a wider slice that includes up to 8 bars AFTER t, then filtered back
         down to ts<=t and re-sliced to the last N -- must reduce to the same
         window/output. A mismatch = lookahead/off-by-one bug.
    """
    rng = random.Random(seed)
    candidates_pool = []
    for symbol in SYMBOLS:
        for tf in ("M15", "H4"):
            bars = all_bars_cache[(symbol, tf)]
            n = M15_WINDOW if tf == "M15" else H4_WINDOW
            if len(bars) < n + 20:
                continue
            for _ in range(3):
                i = rng.randint(n + 10, len(bars) - 9)
                candidates_pool.append((symbol, tf, i))
    picks = rng.sample(candidates_pool, min(samples, len(candidates_pool)))
    results = []
    all_ok = True
    for symbol, tf, i in picks:
        bars = all_bars_cache[(symbol, tf)]
        h4_bars = all_bars_cache[(symbol, "H4")]
        t = bars[i].ts
        n = M15_WINDOW if tf == "M15" else H4_WINDOW

        window_a = window_upto(bars, t, n)
        # method B: slice generously beyond t (+8 bars), then filter to ts<=t, then take last n
        wide_end = min(len(bars), i + 1 + 8)
        wide_start = max(0, i - n - 8)
        wide_slice = bars[wide_start:wide_end]
        filtered = [b for b in wide_slice if b.ts <= t]
        window_b = filtered[-n:]

        htf_a = htf_b = None
        if tf == "M15":
            m15_all = all_bars_cache[(symbol, "M15")]
            h4_a = h4_input_at(h4_bars, m15_all, t, HTF_BIAS_WINDOW)
            htf_a = htf_bias(h4_a) if h4_a else ("NEUTRAL", "no H4 bars yet")
            # method B: same closed+synthesized-partial semantics via a different code path
            T = t + TF_SECONDS["M15"]
            h4_closed = [b for b in h4_bars if b.ts + TF_SECONDS["H4"] <= T]
            forming = [b for b in h4_bars if b.ts <= t and b.ts + TF_SECONDS["H4"] > T]
            h4_b = list(h4_closed)
            if forming:
                p = forming[-1]
                seg = [b for b in m15_all if p.ts <= b.ts <= t]
                if seg:
                    h4_b.append(Bar(ts=p.ts, open=seg[0].open,
                                    high=max(b.high for b in seg),
                                    low=min(b.low for b in seg),
                                    close=seg[-1].close,
                                    volume=sum(b.volume for b in seg)))
            h4_b = h4_b[-HTF_BIAS_WINDOW:]
            htf_b = htf_bias(h4_b) if h4_b else ("NEUTRAL", "no H4 bars yet")
        cand_a = scan_symbol(symbol, window_a, tf=tf, htf=htf_a)
        cand_b = scan_symbol(symbol, window_b, tf=tf, htf=htf_b)
        same = cand_a == cand_b
        all_ok = all_ok and same
        results.append({
            "symbol": symbol, "tf": tf, "t": t,
            "len_a": len(window_a), "len_b": len(window_b),
            "match": same,
            "state_a": cand_a["state"], "state_b": cand_b["state"],
        })
    return {"all_ok": all_ok, "n": len(results), "results": results}


def selfcheck_settlement_prints(recorded_all: list[dict], all_bars_cache: dict, k: int = 5, seed: int = 11) -> list[dict]:
    rng = random.Random(seed)
    resolved = [r for r in recorded_all if r["outcome"] not in ("pending",)]
    picks = rng.sample(resolved, min(k, len(resolved)))
    out = []
    for row in picks:
        bars = all_bars_cache[(row["symbol"], row["tf"])]
        after = [b for b in bars if row["ts"] < b.ts <= (row["resolve_ts"] or bars[-1].ts) + TF_SECONDS[row["tf"]]]
        seq = [{"ts": b.ts, "iso": time.strftime("%Y-%m-%d %H:%M", time.gmtime(b.ts)),
                "o": b.open, "h": b.high, "l": b.low, "c": b.close} for b in after[:40]]
        out.append({
            "symbol": row["symbol"], "tf": row["tf"], "direction": row["direction"],
            "ts": row["ts"], "entry_ref": row["entry_ref"], "sl": row["sl"], "dol": row["dol"],
            "outcome": row["outcome"], "result_r": row["result_r"], "scalp_r": row["scalp_r"],
            "mfe_r": row["mfe_r"], "fill_ts": row["fill_ts"], "resolve_ts": row["resolve_ts"],
            "bar_sequence": seq,
        })
    return out


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def bucket_stats(rows: list[dict]) -> dict:
    settled = [r for r in rows if r["outcome"] in ("win", "loss", "expired")]
    n = len(rows)
    wins = sum(1 for r in settled if r["outcome"] == "win")
    losses = sum(1 for r in settled if r["outcome"] == "loss")
    expired = sum(1 for r in settled if r["outcome"] == "expired")
    no_fill = sum(1 for r in rows if r["outcome"] == "no_fill")
    pending = sum(1 for r in rows if r["outcome"] == "pending")
    fills = wins + losses + expired
    winrate = wins / (wins + losses) if (wins + losses) else None
    sum_r_a = sum((r["result_r"] or 0) for r in settled)
    avg_r_a = sum_r_a / fills if fills else None
    sum_r_scalp = sum((r["scalp_r"] if r["scalp_r"] is not None else 0) for r in settled)
    avg_r_scalp = sum_r_scalp / fills if fills else None
    return {
        "n": n, "filled": fills, "wins": wins, "losses": losses, "expired": expired,
        "no_fill": no_fill, "pending": pending, "winrate": winrate,
        "sumR_a": round(sum_r_a, 2), "avgR_a": round(avg_r_a, 3) if avg_r_a is not None else None,
        "sumR_scalp": round(sum_r_scalp, 2), "avgR_scalp": round(avg_r_scalp, 3) if avg_r_scalp is not None else None,
    }


def htf_align_bucket(row: dict) -> str:
    bias = row.get("htf_bias")
    if bias not in ("LONG", "SHORT"):
        return "neutral"
    return "counter" if row.get("counter_htf") else "aligned"


def main():
    fetch_report = json.loads((HERE / "fetch_report.json").read_text())
    GLOBAL_NOW = fetch_report["now"]
    print(f"GLOBAL_NOW = {GLOBAL_NOW} ({time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(GLOBAL_NOW))})")

    all_bars_cache: dict[tuple, list[Bar]] = {}
    coverage_rows = []
    for symbol in SYMBOLS:
        m15 = load_cached_bars(symbol, "M15")
        h4 = load_cached_bars(symbol, "H4")
        all_bars_cache[(symbol, "M15")] = m15
        all_bars_cache[(symbol, "H4")] = h4

    recorded_all: list[dict] = []
    t0 = time.time()
    for symbol in SYMBOLS:
        m15 = all_bars_cache[(symbol, "M15")]
        h4 = all_bars_cache[(symbol, "H4")]
        for tf in ("M15", "H4"):
            start, end = compute_decision_bounds(symbol, tf, m15, h4, GLOBAL_NOW)
            recorded, meta = run_symbol_tf(symbol, tf, m15, h4, start, end, GLOBAL_NOW)
            meta["raw_bar_count"] = len(m15 if tf == "M15" else h4)
            meta["raw_span_days"] = round(((m15 if tf == "M15" else h4)[-1].ts - (m15 if tf == "M15" else h4)[0].ts) / 86400, 2) if (m15 if tf == "M15" else h4) else 0
            coverage_rows.append(meta)
            recorded_all.extend(recorded)
            print(f"{symbol:8} {tf:4} decisions={meta['n_decision_points']:5} "
                  f"decision_days={meta['decision_days']:6} recorded={meta['n_recorded']:4}")
    print(f"scan wall time: {time.time()-t0:.1f}s, total recorded candidates: {len(recorded_all)}")

    # ---- write signals_backtest.jsonl ----
    with OUT_JSONL.open("w", encoding="utf-8") as fh:
        for row in recorded_all:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {OUT_JSONL}")

    # ---- self-checks ----
    print("running self-check: truncation invariance ...")
    trunc_check = selfcheck_truncation_invariance(all_bars_cache)
    print(f"  truncation invariance all_ok={trunc_check['all_ok']} (n={trunc_check['n']})")

    print("running self-check: settlement spot prints ...")
    settle_check = selfcheck_settlement_prints(recorded_all, all_bars_cache)

    with SELFCHECK_JSON.open("w", encoding="utf-8") as fh:
        json.dump({"truncation_invariance": trunc_check, "settlement_prints": settle_check}, fh,
                   ensure_ascii=False, indent=2)
    print(f"wrote {SELFCHECK_JSON}")

    # ---- report ----
    write_report(recorded_all, coverage_rows, trunc_check, settle_check, GLOBAL_NOW)
    print(f"wrote {REPORT_MD}")


def write_report(rows, coverage_rows, trunc_check, settle_check, global_now):
    lines = []
    lines.append("# 扫描器历史信号回测报告\n")
    lines.append(f"生成时间(UTC): {time.strftime('%Y-%m-%d %H:%M', time.gmtime(global_now))}\n")
    lines.append("口径: 生产 mode=both，每30分钟一次(cron */30)。M15候选窗口=240根、H4候选窗口=180根、"
                  "HTF bias 用60根H4(≤决策时刻)。M15决策步长=2根(30分钟)，H4决策步长=1根(4小时)。"
                  "结算逐条复刻 papertrack._resolve_one（同棒双触记亏、24h未回踩=no_fill、72h未决=expired、"
                  "平行scalp模型 min(2R,DOL)、MFE记录）。\n")

    lines.append("\n## 数据覆盖\n")
    lines.append("| symbol | tf | 原始根数 | 原始跨度(天) | 决策点数 | 决策窗口(天) | 记录候选数 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for m in sorted(coverage_rows, key=lambda x: (x["symbol"], x["tf"])):
        lines.append(f"| {m['symbol']} | {m['tf']} | {m['raw_bar_count']} | {m['raw_span_days']} | "
                      f"{m['n_decision_points']} | {m['decision_days']} | {m['n_recorded']} |")
    short = [m for m in coverage_rows if m["decision_days"] < 30]
    if short:
        lines.append("\n**决策窗口不足30天的品种/周期(如实标注，未做虚假补全):**\n")
        for m in short:
            lines.append(f"- {m['symbol']} {m['tf']}: 决策窗口仅 {m['decision_days']} 天"
                          f"（原始数据跨度 {m['raw_span_days']} 天，受合约上线时间/API历史深度限制或H4预热窗口约束）")
    else:
        lines.append("\n所有品种×周期决策窗口均 >= 30 天。")

    lines.append("\n## 总量\n")
    overall = bucket_stats(rows)
    lines.append(f"- 候选总数: {overall['n']}")
    lines.append(f"- 成交(filled, win+loss+expired): {overall['filled']}  "
                  f"(fill率 = {overall['filled']/overall['n']*100:.1f}% of all candidates)" if overall['n'] else "")
    lines.append(f"- no_fill: {overall['no_fill']} ({overall['no_fill']/overall['n']*100:.1f}%)" if overall['n'] else "")
    lines.append(f"- pending(数据尾部未决): {overall['pending']} ({overall['pending']/overall['n']*100:.1f}%)" if overall['n'] else "")
    lines.append(f"- win/loss/expired: {overall['wins']}/{overall['losses']}/{overall['expired']}")
    if overall['winrate'] is not None:
        lines.append(f"- win率(win/(win+loss)): {overall['winrate']*100:.1f}%")
    lines.append(f"- A模型(hold-to-DOL) sumR={overall['sumR_a']} avgR={overall['avgR_a']}")
    lines.append(f"- scalp模型(min 2R/DOL) sumR={overall['sumR_scalp']} avgR={overall['avgR_scalp']}")

    def bucket_table(title, groups):
        lines.append(f"\n## {title}\n")
        lines.append("| 分桶 | n | filled | win | loss | expired | no_fill | win率 | A模型avgR | scalp模型avgR |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for label, rs in groups:
            if not rs:
                continue
            s = bucket_stats(rs)
            wr = f"{s['winrate']*100:.1f}%" if s['winrate'] is not None else "n/a"
            note = " ⚠️n<30" if s['filled'] < 30 else ""
            lines.append(f"| {label}{note} | {s['n']} | {s['filled']} | {s['wins']} | {s['losses']} | "
                          f"{s['expired']} | {s['no_fill']} | {wr} | {s['avgR_a']} | {s['avgR_scalp']} |")

    bucket_table("按 state 分桶", [(st, [r for r in rows if r["state"] == st]) for st in ("READY", "CONDITIONAL_READY")])
    bucket_table("按 HTF 对齐分桶", [(lb, [r for r in rows if r["tf"] == "M15" and htf_align_bucket(r) == lb])
                                 for lb in ("aligned", "neutral", "counter")])
    bucket_table("按 tf 分桶", [(tf, [r for r in rows if r["tf"] == tf]) for tf in ("M15", "H4")])
    bucket_table("按品种分桶", [(sym, [r for r in rows if r["symbol"] == sym]) for sym in SYMBOLS])
    bucket_table("按 session 分桶", [(s, [r for r in rows if r["session"] == s]) for s in ("asia", "london", "ny", "late")])
    bucket_table("按标记分桶", [
        ("late=True", [r for r in rows if r.get("late")]),
        ("late=False", [r for r in rows if not r.get("late")]),
        ("target_crowded=True", [r for r in rows if r.get("target_crowded")]),
        ("target_crowded=False", [r for r in rows if not r.get("target_crowded")]),
    ])

    lines.append("\n## 自检结果\n")
    lines.append(f"- 截断不变性抽查: n={trunc_check['n']}, 全部一致={trunc_check['all_ok']}")
    if not trunc_check["all_ok"]:
        lines.append("  **存在不一致样本，详见 selfcheck.json，需先修复再采信结果**")
        for r in trunc_check["results"]:
            if not r["match"]:
                lines.append(f"  - MISMATCH {r['symbol']} {r['tf']} t={r['iso'] if 'iso' in r else r['t']}: "
                              f"state_a={r['state_a']} state_b={r['state_b']}")
    lines.append(f"- 结算抽查样本数: {len(settle_check)}（人工核对见 selfcheck.json 的 settlement_prints 字段，"
                  "每条含信号后续bar序列，可核对先触DOL还是先触SL）")

    lines.append("\n## 口径与样本量警告\n")
    lines.append("- 本回测为**信号层paper口径**：限价理想成交、无滑点、无点差、无手续费、无实际下单延迟，"
                  "不代表实盘可实现收益。")
    lines.append("- 结算完全复刻生产 `papertrack._resolve_one`：先成交(24h内回踩POI)判定 -> 先触DOL/先触SL "
                  "-> 同棒双触按亏损记(保守) -> 72h未决记expired。")
    lines.append("- 任何 n<30 的分桶，胜率/avgR 只是噪音，不构成有效统计结论(仿照 papertrack.stats() 的既有警示口径)。")
    lines.append("- pending 候选是数据尾部尚未走完 24h 成交窗口或 72h 结算窗口的候选，不计入 win/loss/expired 统计。")
    lines.append("- news_risk（经济日历）过滤未在回测中复刻（生产版本仅用于推送前提示，不影响 record_candidates 记录与结算，"
                  "且日历API只提供当周数据，无历史回溯），因此本回测候选未按新闻窗口过滤。")
    lines.append("- ltf_refine（Model B）与 push_ready 在生产 crontab 中当前处于 disabled 状态，回测未包含。")

    REPORT_MD.write_text("\n".join(str(l) for l in lines if l != ""), encoding="utf-8")


if __name__ == "__main__":
    main()
