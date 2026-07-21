"""A-grade trigger watcher: push M1/M5 three-step entries on READY signals only.

Pipeline (user request 2026-07-10, "只扫每天的A单"):
  parent filter = READY + sweep confirmed + not counter_htf + not news_risk
                  + not target_crowded + fresh (inside fill window)
  -> detect_ltf_trigger (reused from ltf_refine: POI re-entry, then M1/M5
     close-through of the pullback structure; indexes on M1, rest on M5)
  -> trigger must be FRESH (within ~2 LTF bars) — a trigger discovered late
     is a miss, never pushed as an entry
  -> planned RR at trigger >= MIN_RR, weekend = crypto only
  -> Claude second review (never push unreviewed) -> Feishu DM
  -> one attempt per parent signal, hard daily push cap

Run from cron every 2 minutes:
  python3 -m scanner_service.a_watch          # live
  python3 -m scanner_service.a_watch --dry    # print instead of review+push
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from scanner_service.ltf_refine import SL_BUFFER_ATR, detect_ltf_trigger, ltf_tf
from scanner_service.papertrack import FILL_WINDOW_S, _key, _load, session_of
from scanner_service.push_ready import second_review, send_feishu
from scanner_service.structure import average_true_range, find_swings

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STATE_FILE = DATA_DIR / "a_watch.json"

MIN_RR = 2.0                 # planned R at trigger, entry->dol vs entry->ltf sl
TRIGGER_FRESH_BARS = 2       # push only if trigger bar closed within this many LTF bars
MAX_PUSH_PER_DAY = 6         # A单 base quota — quality over quantity
HARD_PUSH_CAP = 9            # absolute daily ceiling incl. the exceptional lane
EXCEPTIONAL_RR = 4.0         # rr >= this may exceed the base quota up to HARD_PUSH_CAP
# Escalating quality bar (2026-07-21 batch B): the cap was blind FIFO — 11d
# audit showed 58 pushed / 214 dropped purely by time of day, so late high-RR
# triggers lost their slot to early rr~2 ones. The nth push of the day must
# clear a rising RR bar so mediocre signals can't consume the whole quota.
PUSH_RR_BARS = (2.0, 2.0, 2.5, 2.5, 3.0, 3.0)


def _rr_bar(pushed: int) -> float:
    return PUSH_RR_BARS[min(pushed, len(PUSH_RR_BARS) - 1)]
TZ_OFFSET_S = 8 * 3600       # user's trading day is UTC+8

CRYPTO = {"BTC", "ETH", "SOL", "DOGE", "XRP", "SUI", "HYPE", "PEPE", "ZEC", "TAO", "WLD"}

# Symbol quality tiers (papertrack 7d snapshot 2026-07-10, single regime —
# re-evaluate monthly, see skill local-stack.md). A-tier watched on any TF;
# everything else only via H4 parents; C-tier never watched.
A_TIER = {"XAUUSD", "XTIUSD", "US500"}
C_TIER = {"ZEC", "EURUSD", "US30", "PEPE"}
# Stock perps pilot: scan for papertrack sample only, never watch/push
# until ~2 weeks of outcomes are reviewed (user decision 2026-07-11).
SCAN_ONLY = {"TSLA", "NVDA", "MSTR", "CRCL", "MU", "SKHYNIX"}


def _fetch_ltf(router, symbol: str, parent_ts: int, now: int):
    """LTF bars with M1→M5 fallback. Gate TradFi M1 died 2026-07-20 01:56–06:14
    (131× HTTP 400) and the A-tier US500 watch was blind for ~4h with no
    fallback; M5 structure is late for indexes but beats total blindness.
    Returns (bars, tf, tf_seconds); raises SourceError only if both TFs fail."""
    from scanner_service.sources import SourceError

    tf, tf_seconds = ltf_tf(symbol)
    need = min(1000, (now - parent_ts) // tf_seconds + 30)
    try:
        return router.bars(symbol, tf, int(need)), tf, tf_seconds
    except SourceError as exc:
        if tf != "M1":
            raise
        print(f"[a_watch] {symbol} M1 failed ({exc}) — falling back to M5", flush=True)
        need = min(1000, (now - parent_ts) // 300 + 30)
        return router.bars(symbol, "M5", int(need)), "M5", 300


def _day(ts: int) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ts + TZ_OFFSET_S))


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def _is_weekend(ts: int) -> bool:
    return time.gmtime(ts + TZ_OFFSET_S).tm_wday >= 5


def a_grade(r: dict, now: int) -> bool:
    sym = r.get("symbol", "").upper()
    tier_ok = sym not in C_TIER and sym not in SCAN_ONLY and (sym in A_TIER or r.get("tf") == "H4")
    return (tier_ok
            and r.get("outcome") == "pending"
            and r.get("model", "poi_retest") == "poi_retest"
            and r.get("state") == "READY"
            and r.get("swept_level") is not None
            and not r.get("counter_htf")
            and not r.get("news_risk")
            and not r.get("target_crowded")
            and now - r["ts"] <= FILL_WINDOW_S
            and (not _is_weekend(now) or r["symbol"].upper() in CRYPTO))


MAX_FADE_PER_DAY = 2         # counter-HTF sweep-reversal scalps, inside the daily 6


def fade_grade(r: dict, now: int) -> bool:
    """Counter-HTF sweep-reversal scalp lane (2026-07-17, XAU 3970 triple-bottom
    miss). The scanner permanently demotes counter_htf rows to CONDITIONAL_READY,
    which excluded the entire range-extreme reversal class from the watch even
    though the LTF three-step is exactly the confirmation it was waiting for.
    A-tier symbols only; the only blockers allowed to remain on the row are
    counter_htf itself and the missing MSS/CISD close-through (the LTF trigger
    supplies that). Fresh D1 leg against still hard-blocks (D1 seniority).
    Pushed as scalp framing — near target only, capped at MAX_FADE_PER_DAY."""
    sym = r.get("symbol", "").upper()
    return (sym in A_TIER
            and r.get("outcome") == "pending"
            and r.get("model", "poi_retest") == "poi_retest"
            and r.get("counter_htf") is True
            and not r.get("counter_d1")
            and r.get("state") in ("READY", "CONDITIONAL_READY")
            and r.get("swept_level") is not None
            and r.get("dol") is not None
            and (r.get("rr") or 0) >= MIN_RR
            and not r.get("late")
            and not r.get("news_risk")
            and not r.get("target_crowded")
            and now - r["ts"] <= FILL_WINDOW_S
            and (not _is_weekend(now) or sym in CRYPTO))


MAX_CONT_PER_PARENT = 2      # continuation pushes per parent signal per day
RECLAIM_BARS = 3             # sweep must reclaim within this many LTF bars
TRIGGER_BARS = 8             # close-break must print within this many bars of reclaim


def detect_continuation_triggers(parent: dict, bars) -> list[dict]:
    """With-trend continuation: local LTF sweep -> reclaim -> close-break,
    in the direction of an active aligned READY parent, without requiring a
    return to the parent POI (which detect_ltf_trigger already covers).
    Returns ALL completed sequences (caller dedupes/filters freshness)."""
    short = parent["direction"] == "SHORT"
    swept_poi = float(parent["swept_level"])
    dol = float(parent["dol"])
    bb = [b for b in bars if b.ts > parent["ts"]]
    if len(bb) < 10:
        return []
    atr = average_true_range(bb)
    swings = find_swings(bb)
    kind = "high" if short else "low"
    out = []
    for s in (s for s in swings if s.kind == kind):
        # price must be on the trade side of the parent POI — inside/through
        # the POI is model B's territory, not continuation
        if (not short and s.price <= swept_poi) or (short and s.price >= swept_poi):
            continue
        seq = None
        for j in range(s.confirmed_at, len(bb)):
            hit = bb[j].high > s.price if short else bb[j].low < s.price
            if not hit:
                continue
            rec = next((k for k in range(j, min(j + RECLAIM_BARS + 1, len(bb)))
                        if (bb[k].close < s.price if short else bb[k].close > s.price)), None)
            if rec is not None:
                for k in range(rec, min(rec + TRIGGER_BARS + 1, len(bb))):
                    lo_i = max(j - 2, 0)
                    if short:
                        minor = min(b.low for b in bb[lo_i:k]) if k > lo_i else bb[j].low
                        trig = bb[k].close < minor and bb[k].close < bb[j].low
                    else:
                        minor = max(b.high for b in bb[lo_i:k]) if k > lo_i else bb[j].high
                        trig = bb[k].close > minor and bb[k].close > bb[j].high
                    if trig:
                        seq = (j, rec, k)
                        break
            break  # first sweep of this swing decides; no seq -> this swing is spent
        if seq is None:
            continue
        j, rec, k = seq
        window = bb[j:k + 1]
        entry = bb[k].close
        if short:
            extreme = max(b.high for b in window)
            sl = extreme + SL_BUFFER_ATR * atr
            risk, reward = sl - entry, entry - dol
        else:
            extreme = min(b.low for b in window)
            sl = extreme - SL_BUFFER_ATR * atr
            risk, reward = entry - sl, dol - entry
        if risk < 0.5 * atr or reward <= 0:
            continue
        out.append({"symbol": parent["symbol"], "tf": parent["tf"],
                    "direction": parent["direction"], "state": parent["state"],
                    "model": "continuation",
                    "price": entry, "entry_ref": entry, "sl": round(sl, 8), "dol": dol,
                    "dol_runner": parent.get("dol_runner"),
                    "rr": round(reward / risk, 2), "rr_now": round(reward / risk, 2),
                    "late": False, "target_crowded": False,
                    "swept_level": s.price, "mss": parent.get("mss"), "cisd": parent.get("cisd"),
                    "reason": f"with-trend local sweep of {s.price} reclaimed, close-break continuation",
                    "_trigger_ts": bb[k].ts})
    return out


MAGNET_MAX_RISK_MULT = 3.0   # only warn about unfilled POIs within this many R of entry


def deep_magnet(parent: dict, cand: dict, records: list[dict], now: int) -> dict | None:
    """Unfilled same-direction POI on the stop side of the trade, close enough
    to act as a magnet (ETH -1R 2026-07-10: SL 1783.53 hung above an unfilled
    M15 POI 1774.6-1780.11; the wick tagged 1780.08 and reversed). The zone is
    reconstructed as [sig.sl, sig.swept_level] (long) since rows carry no poi
    field. Warn-only — desk still adjudicates."""
    long = parent["direction"] == "LONG"
    entry, sl = float(cand["price"]), float(cand["sl"])
    risk = abs(entry - sl)
    best = None
    for r in records:
        if (r.get("symbol") != parent["symbol"]
                or r.get("direction") != parent["direction"]
                or r.get("model", "poi_retest") != "poi_retest"
                or r.get("filled") or r.get("outcome") != "pending"
                or now - r["ts"] > FILL_WINDOW_S):
            continue
        top = float(r["swept_level"])
        if long:
            if top >= sl or entry - top > MAGNET_MAX_RISK_MULT * risk:
                continue
            if best is None or top > float(best["swept_level"]):
                best = r
        else:
            if top <= sl or top - entry > MAGNET_MAX_RISK_MULT * risk:
                continue
            if best is None or top < float(best["swept_level"]):
                best = r
    return best


def format_push(parent: dict, cand: dict, ltf: str, magnet: dict | None = None) -> str:
    entry = cand["price"]
    risk = abs(entry - cand["sl"])
    one_r = entry - risk if parent["direction"] == "SHORT" else entry + risk
    mgmt = parent.get("mgmt")
    mgmt_line = f"管理位 {mgmt}，" if mgmt is not None else ""
    # 2026-07-11: mechanical sequence = legality only, not edge grade.
    # Never brand as「A单/S单」— desk/user still adjudicates.
    if cand.get("model") == "continuation":
        head = (f"🎯 合法触发候选（顺势延续·待裁决）：{parent['symbol']} {parent['direction']}"
                f"（{parent['tf']} READY 方向上，{ltf} 局部扫 {cand['swept_level']} 回收+收盘破）\n")
    else:
        head = (f"🎯 合法触发候选（待裁决）：{parent['symbol']} {parent['direction']}"
                f"（{parent['tf']} READY → {ltf} 三步走齐）\n"
                f"扫 {parent['swept_level']} 后回踩，{ltf} 收盘破回调结构。\n")
    two_r = entry - 2 * risk if parent["direction"] == "SHORT" else entry + 2 * risk
    fade_line = ""
    if parent.get("counter_htf"):
        fade_line = (f"⚠️ 逆HTF（H4 bias {parent.get('htf_bias')}）扫池反转——剥头皮口径：\n"
                     f"只打近池，到管理位/主目标坚决落袋，不拿远DOL，不留runner。\n")
    env_flags = []
    if parent.get("env_sbq") == "weak":
        env_flags.append("信号棒weak")
    if parent.get("env_micro_ct"):
        env_flags.append("逆微通道")
    if parent.get("env_barbwire"):
        env_flags.append("barbwire")
    env_line = ""
    if env_flags:
        env_line = (f"⚠️ 环境标记：{'、'.join(env_flags)}"
                    f"（回放降级因子，RR 门槛已抬高；二审重点核结构质量）\n")
    magnet_line = ""
    if magnet is not None:
        zone = sorted([float(magnet["sl"]), float(magnet["swept_level"])])
        side = "下方" if parent["direction"] == "LONG" else "上方"
        magnet_line = (f"⚠️ 深位磁力警示：SL {side}有未回补 {magnet['tf']} POI "
                       f"{zone[0]}-{zone[1]}，浅损正挂在磁力区外沿——"
                       f"要么损放 {zone[0] if parent['direction'] == 'LONG' else zone[1]} 外侧并减半仓，"
                       f"要么限价 POI 内等深接（可能不成交），别站两层流动性中间。\n")
    return (head
            + fade_line
            + env_line
            + magnet_line
            + f"入场参考 {entry}，SL {cand['sl']}（触发窗极值外），计划 RR {cand['rr']}\n"
            + f"管理二选一（进场前定死，中途不换）：默认 +1R（{round(one_r, 8)}）必减；"
            + f"或 mgmt2r：首减 +2R（{round(two_r, 8)}）/对手 M15 结构位，+1R 起损跟确认结构\n"
            + f"{mgmt_line}主目标 {cand['dol']}\n"
            + f"过两根 {ltf} 没进就别追。序列合法≠自动 edge；桌面/人肉仍要裁决。"
            + f"平仓记账带 --source a_watch。")


def run(now: int | None = None, dry: bool = False) -> dict:
    from scanner_service.sources import MarketDataRouter, SourceError

    router = MarketDataRouter()
    now = now or int(time.time())
    state = _load_state()
    today = _day(now)
    pushed_today = sum(1 for v in state.values()
                       if v.get("status") == "pushed" and v.get("day") == today)

    records = _load()
    parents = [r for r in records if a_grade(r, now)]
    fades = [r for r in records if not a_grade(r, now) and fade_grade(r, now)]
    faded_today = sum(1 for v in state.values()
                      if v.get("fade") and v.get("day") == today
                      and v.get("status") in ("pushed", "dry"))
    checked, triggered, sent, errors = 0, 0, 0, 0
    bar_cache: dict[str, list] = {}
    for parent in parents + fades:
        is_fade = fade_grade(parent, now) and not a_grade(parent, now)
        pkey = json.dumps(_key(parent), ensure_ascii=False)
        try:
            if parent["symbol"] not in bar_cache:
                bar_cache[parent["symbol"]] = _fetch_ltf(router, parent["symbol"], parent["ts"], now)
            bars, tf, tf_seconds = bar_cache[parent["symbol"]]
        except SourceError as exc:
            errors += 1
            print(f"[a_watch] bars failed {parent['symbol']}: {exc}", flush=True)
            continue
        todo: list[tuple[str, dict]] = []
        if pkey not in state:
            checked += 1
            cand = detect_ltf_trigger(parent, bars)
            if cand is not None:
                todo.append((pkey, cand))
        # continuation also runs on fade parents: V-reversals never retest the
        # POI (XAU 2026-07-17 03:00 leg), so the only catchable entries are the
        # local sweep->reclaim->break sequences inside the reversal leg. The
        # fade daily cap + per-parent cont cap + second review still gate it.
        for cand in detect_continuation_triggers(parent, bars):
            ckey = f"{pkey}|cont|{cand['swept_level']}"
            if ckey not in state:
                todo.append((ckey, cand))
        for skey, cand in todo:
            triggered += 1
            label = f"{parent['symbol']} {parent['direction']} [{cand.get('model', 'poi')}]"
            trigger_ts = cand.pop("_trigger_ts")
            # same physical trigger bar can fire under several same-direction
            # parents — push it once
            sig = f"sig|{parent['symbol']}|{parent['direction']}|{trigger_ts}"
            if sig in state:
                state[skey] = {"status": "dup_trigger", "day": today, "ts": trigger_ts}
                continue
            state[sig] = {"status": "seen", "day": today, "ts": trigger_ts}
            age = now - (trigger_ts + tf_seconds)  # bar close time
            if age > TRIGGER_FRESH_BARS * tf_seconds:
                state[skey] = {"status": "late_trigger", "day": today, "ts": trigger_ts}
                print(f"[a_watch] LATE {label} trigger aged {age}s — miss, not pushed", flush=True)
                continue
            rr_bar = max(MIN_RR, _rr_bar(pushed_today))
            # soft env penalty (2026-07-21 C10): replay-validated demotion
            # factors — sbq_weak (+290R net saved, survivor pool +0.148R) and
            # counter-micro-channel (+92R). Never a hard block: the trigger
            # just has to clear a higher bar.
            if parent.get("env_sbq") == "weak" or parent.get("env_micro_ct"):
                rr_bar += 0.5
            # asia-session soft demotion (2026-07-21 C7): paper by-session
            # split asia −0.28R vs london +0.05R (n≈2,957) — penalty, no block
            if session_of(now) == "asia":
                rr_bar += 0.5
            if cand["rr"] < rr_bar:
                state[skey] = {"status": "rr_too_low", "day": today, "ts": trigger_ts}
                print(f"[a_watch] RR {cand['rr']} < bar {rr_bar} (push #{pushed_today + 1}) {label} — skipped", flush=True)
                continue
            if cand.get("model") == "continuation":
                cont_used = sum(1 for k, v in state.items()
                                if k.startswith(pkey + "|cont|") and v.get("day") == today
                                and v.get("status") in ("pushed", "dry"))
                if cont_used >= MAX_CONT_PER_PARENT:
                    state[skey] = {"status": "parent_cont_cap", "day": today, "ts": trigger_ts}
                    print(f"[a_watch] cont cap per parent — {label} dropped", flush=True)
                    continue
            if is_fade and faded_today >= MAX_FADE_PER_DAY:
                state[skey] = {"status": "fade_cap", "day": today, "ts": trigger_ts}
                print(f"[a_watch] fade cap {MAX_FADE_PER_DAY} reached — {label} dropped", flush=True)
                continue
            if pushed_today >= MAX_PUSH_PER_DAY:
                # exceptional lane: an outsized-RR trigger may exceed the base
                # quota, but never the hard ceiling
                if not (cand["rr"] >= EXCEPTIONAL_RR and pushed_today < HARD_PUSH_CAP):
                    state[skey] = {"status": "daily_cap", "day": today, "ts": trigger_ts}
                    print(f"[a_watch] daily cap {MAX_PUSH_PER_DAY} reached — {label} dropped", flush=True)
                    continue
                print(f"[a_watch] cap-exempt exceptional rr={cand['rr']} — {label}", flush=True)
            text = format_push(parent, cand, tf, deep_magnet(parent, cand, records, now))
            if dry:
                print(f"[a_watch] DRY would push:\n{text}", flush=True)
                state[skey] = {"status": "dry", "day": today, "ts": trigger_ts, "fade": is_fade}
                if is_fade:
                    faded_today += 1
                continue
            ok, verdict = second_review(cand)
            if not ok:
                if "unavailable" in verdict.lower() or "not logged in" in verdict.lower():
                    # infra failure, not a veto — leave unconsumed and undo the
                    # dedupe mark so the next cron retries while still fresh
                    state.pop(sig, None)
                    print(f"[a_watch] REVIEW-DOWN {label}: {verdict} — will retry", flush=True)
                    continue
                state[skey] = {"status": "vetoed", "day": today, "ts": trigger_ts}
                print(f"[a_watch] VETO {label}: {verdict}", flush=True)
                continue
            try:
                send_feishu(text)
                sent += 1
                pushed_today += 1
                if is_fade:
                    faded_today += 1
                state[skey] = {"status": "pushed", "day": today, "ts": trigger_ts, "fade": is_fade}
                print(f"[a_watch] SENT {label} rr={cand['rr']}", flush=True)
            except Exception as exc:
                # do not mark consumed — retry next cron while still fresh
                print(f"[a_watch] send failed {label}: {exc}", flush=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return {"parents": len(parents), "fades": len(fades), "checked_new": checked,
            "triggered": triggered, "sent": sent, "pushed_today": pushed_today,
            "errors": errors}


if __name__ == "__main__":
    print(json.dumps(run(dry="--dry" in sys.argv), ensure_ascii=False))
