"""答题（并发 + 缓存 + 断点续跑）和逐题打分。run_exam.py 与 optimize.py 共用。"""
import threading
from concurrent.futures import ThreadPoolExecutor

from .common import append_jsonl, build_system, build_user, extract_json, normalize_answer, render_context, sha
from . import llm

_plock = threading.Lock()


def preload(bars, items, spec):
    for sym in {it["sym"] for it in items}:
        for tf in {"M15", "H4", "D1", "W1", *[t for t, _ in spec]}:
            bars.get(sym, tf)


def answer_one(cfg, backend, bars, it, system, spec, rep=0, use_cache=True, indicators=True):
    ctx, _ = render_context(bars, it["sym"], it["ts"], spec, indicators)
    user = build_user(ctx)
    txt = llm.call(cfg, backend, system, user, rep=rep, use_cache=use_cache)
    ans = normalize_answer(extract_json(txt, "decision")) if txt else None
    return {"id": it["id"], "rep": rep, "answer": ans, "raw_tail": None if ans else (txt or "")[-400:]}


def run_items(cfg, backend, bars, items, skill_text, playbook_text, spec, rep=0, workers=4,
              out_path=None, done=None, use_cache=True, indicators=True, verbose=True):
    """返回 {id: row}。out_path 给定时逐题追加写（断点续跑：done 里已有的跳过）。"""
    system = build_system(skill_text, playbook_text)
    preload(bars, items, spec)
    res = dict(done or {})
    todo = [it for it in items if it["id"] not in res]
    n = len(todo)
    k = [0]

    def work(it):
        row = answer_one(cfg, backend, bars, it, system, spec, rep, use_cache, indicators)
        row["system_sha"] = sha(system)
        with _plock:
            res[it["id"]] = row
            if out_path:
                append_jsonl(out_path, row)
            k[0] += 1
            if verbose and (k[0] % 10 == 0 or k[0] == n):
                bad = sum(1 for r in res.values() if r["answer"] is None)
                print(f"  答题 {k[0]}/{n}（解析失败累计 {bad}）", flush=True)
        return row

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        list(ex.map(work, todo))
    return res


# ---------- 打分 ----------

def score_item(it, ans):
    """忠实分 0–1。
    对照题：他没出手 → 你也不做=1，否则 0。
    真题：不做/解析失败=0；方向错=0；方向对=0.4 + 0.3×入场接近 + 0.2×止损接近 + 0.1×单型一致。
          接近 = max(0, 1 − 误差/ATR14(H4))，即误差 1 个 H4 ATR 以上不给分。"""
    out = {"id": it["id"], "kind": it["kind"], "split": it.get("split"), "parsed": ans is not None}
    acted = bool(ans) and ans["decision"] != "不做"
    out["acted"] = acted
    if it["kind"] == "neg":
        out["score"] = 1.0 if (ans is not None and not acted) else 0.0
        return out
    if not acted:
        out["score"] = 0.0
        return out
    atr = it["atr_h4"]
    best = None
    for e in it["expert_orders"]:
        side_ok = e["side"] == ans["side"]
        ee = abs(ans["entry"] - e["entry"]) / atr
        se = abs(ans["stop"] - e["stop"]) / atr
        type_ok = (ans["decision"] == "市价") == (e["type"] == "market")
        s = 0.0 if not side_ok else 0.4 + 0.3 * max(0, 1 - ee) + 0.2 * max(0, 1 - se) + 0.1 * type_ok
        cand = {"score": s, "side_ok": side_ok, "entry_err": ee, "stop_err": se, "type_ok": type_ok}
        if best is None or s > best["score"]:
            best = cand
    out.update(best)
    return out


def score_run(items, answers):
    return {it["id"]: score_item(it, (answers.get(it["id"]) or {}).get("answer")) for it in items}
