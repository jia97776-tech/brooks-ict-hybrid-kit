#!/usr/bin/env python3
"""让桌面（模型 + 手册）做考卷。断点续跑：中断后同样命令再跑一次，只补没做的题。

  python3 run_exam.py --exam exams/tom.jsonl --split dev --skill none --tag bare           # 裸模型基线
  python3 run_exam.py --exam exams/tom.jsonl --split dev --skill ~/.claude/skills/brooks-ict-lean/SKILL.md --tag lean
  python3 run_exam.py --exam exams/tom.jsonl --split dev --skill base.md --playbook runs/opt_x/best.md --tag opt
  python3 run_exam.py ... --rep 1 --tag lean_rep1     # 同一份手册第二遍，量噪声
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dk.common import Bars, kit_path, load_config, parse_ctx, read_jsonl, read_skill, sha
from dk.desk import run_items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exam", required=True)
    ap.add_argument("--split", default="dev", help="train|dev|holdout|all，可逗号分隔")
    ap.add_argument("--skill", nargs="+", default=["none"], help="手册文件，可多个（按顺序拼接）；none=不给手册")
    ap.add_argument("--playbook", help="优化器产出的补充条目")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--backend")
    ap.add_argument("--workers", type=int)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--rep", type=int, default=0, help="第几遍；不同 rep 不共用缓存，用来量自身一致率")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--no-indicators", action="store_true", help="不给 SMA20/ATR 这行辅助算术")
    a = ap.parse_args()
    cfg = load_config()
    backend = a.backend or cfg["default_backend"]
    spec = parse_ctx(cfg.get("context", "W1:26,D1:100,H4:60,H1:48"))

    items = read_jsonl(kit_path(a.exam))
    if a.split != "all":
        sp = set(a.split.split(","))
        items = [it for it in items if it["split"] in sp]
    if a.limit:
        items = items[: a.limit]
    skill = read_skill(a.skill)
    pb = open(a.playbook, encoding="utf-8").read() if a.playbook else ""

    out_dir = kit_path(os.path.join("runs", a.tag))
    os.makedirs(out_dir, exist_ok=True)
    meta_p = os.path.join(out_dir, "meta.json")
    meta = {"exam": a.exam, "split": a.split, "skill": a.skill, "playbook": a.playbook, "backend": backend,
            "rep": a.rep, "context": cfg.get("context"), "skill_sha": sha(skill + "\x00" + pb)}
    if os.path.exists(meta_p):
        old = json.load(open(meta_p))
        if old.get("skill_sha") != meta["skill_sha"] or old.get("backend") != backend:
            sys.exit(f"runs/{a.tag} 已存在但手册/后端不同。换个 --tag，或删掉该目录重跑。")
    json.dump(meta, open(meta_p, "w"), ensure_ascii=False, indent=1)

    ans_p = os.path.join(out_dir, "answers.jsonl")
    done = {r["id"]: r for r in read_jsonl(ans_p) if r.get("rep", 0) == a.rep}
    print(f"[{a.tag}] 后端 {backend}，{len(items)} 题，已完成 {sum(1 for i in items if i['id'] in done)}")
    res = run_items(cfg, backend, Bars(cfg["bars_dir"]), items, skill, pb, spec, rep=a.rep,
                    workers=a.workers or cfg.get("workers", 4), out_path=ans_p, done=done,
                    use_cache=not a.no_cache, indicators=not a.no_indicators)
    bad = sum(1 for i in items if res.get(i["id"], {}).get("answer") is None)
    print(f"[{a.tag}] 完成。解析失败 {bad} 题（raw_tail 字段里有模型原文末尾）。下一步：python3 score.py --exam {a.exam} --run {a.tag}")


if __name__ == "__main__":
    main()
