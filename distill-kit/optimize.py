#!/usr/bin/env python3
"""自动迭代「补充条目」（ACE 式逐条增删改 + GEPA 式反思与验收）。手册正文不动，只长出一份 playbook。

每一轮：
  1) 从训练集抽一小批题，让桌面（手册 + 当前 playbook）作答、打分；
  2) 把答错的题（图的节选 + 桌面答案 + 交易员实际单 + 他的原话）交给反思模型，让它提 ≤N 处条目修改；
  3) 新 playbook 先在同一小批上重答：没变好直接丢；
  4) 变好了再上验证集：配对忠实分提升 ≥ --min-gain 且 P(提升>0) ≥ --min-prob 才采纳。
留出集全程不碰；优化结束后用 run_exam.py --split holdout 做最终考试。

  python3 optimize.py --exam exams/tom.jsonl --skill base.md --tag tom1 --iters 15
  中断后同样命令再跑会接着上次的最佳版本继续。
"""
import argparse, json, os, random, re, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dk import llm
from dk.common import (Bars, append_jsonl, extract_json, kit_path, load_config, mean, paired_boot, parse_ctx,
                       read_jsonl, read_skill, render_context)
from dk.desk import run_items, score_run

BULLET = re.compile(r"^- \[(P\d+)\] (.+)$")

REFLECT_SYS = """你是一份交易手册的编辑。目标：让「手册 + 补充条目」驱动的桌面，在盲测里做出和这位交易员本人一样的决定——
做不做、方向、依据哪条线、止损放哪、市价还是挂单。你只能改「补充条目」，不能改手册正文。"""

REFLECT_RULES = """修改规则：
1. 最多 {max_ops} 处修改（add / edit / delete）。补充条目总数不超过 {max_bullets} 条，快满了就合并或删掉没用的。
2. 每条必须是决策时刻看图就能执行的通用规则：写清看哪个周期、什么结构、线怎么取、止损放在哪、什么情况市价/挂单/不做。
   禁止出现具体品种、日期、价格；禁止「更谨慎」「综合判断」这类没法执行的话。
3. 优先修正多个案例共有的偏差；只能解释单个案例的规则不要写。对照题（他没出手）答错说明桌面太爱出手，同样重要。
4. 交易员原话优先于你的推测；原话和手册冲突时，条目里写明「覆盖手册某条」。
5. 下面「最近试过没用」的修改不要换个说法重提。
只输出 JSON：
{{"diagnosis":"一两句话：桌面和他的系统性差别","ops":[{{"op":"add","text":"...","evidence":["案例id"]}},{{"op":"edit","id":"P2","text":"...","evidence":["案例id"]}},{{"op":"delete","id":"P3","why":"..."}}]}}"""


def parse_pb(text):
    out = []
    for l in text.splitlines():
        m = BULLET.match(l.strip())
        if m:
            out.append([m.group(1), m.group(2)])
    return out


def render_pb(bullets):
    return "\n".join(f"- [{i}] {t}" for i, t in bullets)


def apply_ops(bullets, ops, max_bullets):
    b = [list(x) for x in bullets]
    nxt = max([int(i[1:]) for i, _ in b] + [0]) + 1
    applied = []
    for op in ops or []:
        kind = op.get("op")
        text = (op.get("text") or "").strip().replace("\n", " ")
        ev = op.get("evidence") or []
        tail = f" 〔依据: {', '.join(map(str, ev[:4]))}〕" if ev else ""
        if kind == "add" and text and len(b) < max_bullets:
            b.append([f"P{nxt}", text + tail]); applied.append(op); nxt += 1
        elif kind == "edit" and text:
            for x in b:
                if x[0] == op.get("id"):
                    x[1] = text + tail; applied.append(op)
        elif kind == "delete":
            n0 = len(b)
            b = [x for x in b if x[0] != op.get("id")]
            if len(b) < n0:
                applied.append(op)
    return b, applied


def describe_case(bars, it, row, sc):
    ctx, snap = render_context(bars, it["sym"], it["ts"], [("D1", 40), ("H4", 30)], indicators=True)
    atr = it["atr_h4"]
    a = (row or {}).get("answer")
    if a is None:
        mine = "（输出无法解析）"
    elif a["decision"] == "不做":
        mine = "不做"
    else:
        mine = f"{a['decision']} {a['side']} 入场 {a['entry']} 止损 {a['stop']}｜依据：{a['level']}｜理由：{a['reason']}"
    if it["kind"] == "neg":
        his = "他此刻没有出手（前后几天在这个品种上都没发言）。"
    else:
        his = "\n".join(
            f"  - {'市价' if e['type'] == 'market' else '挂单'} {e['side']} 入场 {e['entry']} 止损 {e['stop']}"
            f"（入场距现价 {(e['entry'] - it['price']) / atr:+.2f} ATR(H4)，止损宽 {abs(e['entry'] - e['stop']) / atr:.2f} ATR(H4)）"
            for e in it["expert_orders"])
    q = "\n".join(f"  > {x}" for x in it.get("quotes", [])[:4]) or "  （无原话）"
    return (f"### 案例 {it['id']}（{'真题' if it['kind'] == 'pos' else '对照题'}，本题得分 {sc['score']:.2f}）\n{ctx}\n\n"
            f"桌面答：{mine}\n交易员实际：\n{his}\n他当时的原话：\n{q}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exam", required=True)
    ap.add_argument("--skill", nargs="+", default=["none"], help="手册正文（不改）；none=从零蒸")
    ap.add_argument("--init-playbook", help="起始补充条目（可选）")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--iters", type=int, default=10)
    ap.add_argument("--minibatch", type=int, default=24)
    ap.add_argument("--max-cases", type=int, default=6, help="每轮给反思模型看几个错题")
    ap.add_argument("--max-ops", type=int, default=3)
    ap.add_argument("--max-bullets", type=int, default=25)
    ap.add_argument("--min-gain", type=float, default=0.02, help="验证集忠实分至少提高多少才采纳")
    ap.add_argument("--min-prob", type=float, default=0.8, help="配对自助法 P(提升>0) 至少多少才采纳")
    ap.add_argument("--backend"); ap.add_argument("--reflector")
    ap.add_argument("--workers", type=int)
    ap.add_argument("--hide-skill-from-reflector", action="store_true", help="手册很长时省 token")
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()

    cfg = load_config()
    desk = a.backend or cfg["default_backend"]
    refl = a.reflector or cfg.get("reflector_backend", desk)
    spec = parse_ctx(cfg.get("context", "W1:26,D1:100,H4:60,H1:48"))
    workers = a.workers or cfg.get("workers", 4)
    bars = Bars(cfg["bars_dir"])
    rnd = random.Random(a.seed)
    items = read_jsonl(kit_path(a.exam))
    train = [i for i in items if i["split"] == "train"]
    dev = [i for i in items if i["split"] == "dev"]
    if not train or not dev:
        sys.exit("考卷里没有 train/dev 题。")
    skill = read_skill(a.skill)

    d = kit_path(os.path.join("runs", f"opt_{a.tag}"))
    os.makedirs(d, exist_ok=True)
    st_p = os.path.join(d, "state.json")
    if os.path.exists(st_p):
        st = json.load(open(st_p))
        pb = parse_pb(open(os.path.join(d, "best.md"), encoding="utf-8").read())
        print(f"接着上次：已跑 {st['iter']} 轮，当前最佳 v{st['best_v']} 验证集 {st['best_dev']:.3f}")
    else:
        pb = parse_pb(open(a.init_playbook, encoding="utf-8").read()) if a.init_playbook else []
        st = {"iter": 0, "best_v": 0, "best_dev": None, "tried_rejected": [], "skill": a.skill, "exam": a.exam}
        open(os.path.join(d, "pb_v0.md"), "w", encoding="utf-8").write(render_pb(pb))
        shutil.copy(os.path.join(d, "pb_v0.md"), os.path.join(d, "best.md"))

    def evaluate(bullets, its):
        ans = run_items(cfg, desk, bars, its, skill, render_pb(bullets), spec, workers=workers, verbose=False)
        return ans, score_run(its, ans)

    print(f"验证集 {len(dev)} 题评估当前版本…", flush=True)
    _, dev_sc = evaluate(pb, dev)
    st["best_dev"] = mean([s["score"] for s in dev_sc.values()])
    print(f"当前版本验证集忠实分 {st['best_dev']:.3f}")

    pos_t = [i for i in train if i["kind"] == "pos"]; neg_t = [i for i in train if i["kind"] == "neg"]
    for _ in range(a.iters):
        st["iter"] += 1
        k = st["iter"]
        n_neg = round(a.minibatch * len(neg_t) / len(train))
        mb = rnd.sample(pos_t, min(len(pos_t), a.minibatch - n_neg)) + rnd.sample(neg_t, min(len(neg_t), n_neg))
        ans_old, sc_old = evaluate(pb, mb)
        m_old = mean([s["score"] for s in sc_old.values()])
        fails = sorted((i for i in mb if sc_old[i["id"]]["score"] < 0.7),
                       key=lambda i: (sc_old[i["id"]]["score"], not i.get("quotes")))[: a.max_cases]
        log = {"iter": k, "minibatch_old": round(m_old, 4), "n_fail": len(fails)}
        if not fails:
            print(f"[{k}] 小批 {m_old:.3f}，没有错题，跳过"); append_jsonl(os.path.join(d, "log.jsonl"), log); continue

        cases = "\n".join(describe_case(bars, i, ans_old.get(i["id"]), sc_old[i["id"]]) for i in fails)
        tried = "\n".join(f"- {t}" for t in st["tried_rejected"][-8:]) or "（无）"
        user = ((("=== 手册正文（只读）===\n" + skill + "\n=== 正文结束 ===\n\n") if skill and not a.hide_skill_from_reflector else "")
                + "=== 当前补充条目 ===\n" + (render_pb(pb) or "（空）") + "\n=== 结束 ===\n\n"
                + f"=== 桌面答错的案例（共 {len(fails)} 个）===\n{cases}\n"
                + f"=== 最近试过没用的修改 ===\n{tried}\n\n"
                + REFLECT_RULES.format(max_ops=a.max_ops, max_bullets=a.max_bullets)
                + '\n（输出字段名固定为 "ops"。）')
        txt = llm.call(cfg, refl, REFLECT_SYS, user, rep=k)
        prop = extract_json(txt, "ops") if txt else None
        new_pb, applied = apply_ops(pb, (prop or {}).get("ops"), a.max_bullets)
        log["diagnosis"] = (prop or {}).get("diagnosis")
        log["ops"] = applied
        if not applied:
            print(f"[{k}] 反思没给出可用修改"); append_jsonl(os.path.join(d, "log.jsonl"), log); continue

        _, sc_new = evaluate(new_pb, mb)
        m_new = mean([s["score"] for s in sc_new.values()])
        log["minibatch_new"] = round(m_new, 4)
        summary = "; ".join(f"{o['op']} {o.get('id', '')} {(o.get('text') or o.get('why') or '')[:60]}" for o in applied)
        if m_new <= m_old:
            print(f"[{k}] 小批 {m_old:.3f}→{m_new:.3f} 没变好，丢弃：{summary}")
            st["tried_rejected"].append(summary); log["result"] = "reject_minibatch"
        else:
            _, dev_new = evaluate(new_pb, dev)
            diff, ci, p = paired_boot([dev_new[i["id"]]["score"] - dev_sc[i["id"]]["score"] for i in dev])
            dm = mean([s["score"] for s in dev_new.values()])
            log.update(dev_new=round(dm, 4), dev_diff=round(diff, 4), dev_ci=[round(x, 4) for x in ci], p=round(p, 3))
            if diff >= a.min_gain and p >= a.min_prob:
                v = st["best_v"] + 1
                pb, dev_sc, st["best_v"], st["best_dev"] = new_pb, dev_new, v, dm
                open(os.path.join(d, f"pb_v{v}.md"), "w", encoding="utf-8").write(render_pb(pb))
                shutil.copy(os.path.join(d, f"pb_v{v}.md"), os.path.join(d, "best.md"))
                print(f"[{k}] ✅ 采纳 v{v}：验证集 {dm:.3f}（{diff:+.3f}，CI [{ci[0]:+.3f},{ci[1]:+.3f}]，P={p:.2f}）｜{summary}")
                log["result"] = f"accept_v{v}"
            else:
                print(f"[{k}] 验证集 {diff:+.3f}（P={p:.2f}）不够，丢弃：{summary}")
                st["tried_rejected"].append(summary); log["result"] = "reject_dev"
        append_jsonl(os.path.join(d, "log.jsonl"), log)
        json.dump(st, open(st_p, "w"), ensure_ascii=False, indent=1)

    json.dump(st, open(st_p, "w"), ensure_ascii=False, indent=1)
    print(f"\n结束。最佳 v{st['best_v']} 验证集 {st['best_dev']:.3f} → {os.path.join(d, 'best.md')}")
    print("最终考试（留出集，基线 vs 优化后）：")
    sk = " ".join(a.skill)
    print(f"  python3 run_exam.py --exam {a.exam} --split holdout --skill {sk} --tag {a.tag}_hold_base")
    print(f"  python3 run_exam.py --exam {a.exam} --split holdout --skill {sk} --playbook {os.path.join(d, 'best.md')} --tag {a.tag}_hold_opt")
    print(f"  python3 score.py --exam {a.exam} --run {a.tag}_hold_base --run {a.tag}_hold_opt --settle")


if __name__ == "__main__":
    main()
