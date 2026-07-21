"""Pool-level signal audit (2026-07-21 F1): expectancy tables + honesty guards.

Absorbed from the ict-stradegy audit skeleton + AlphaMaster rubric:
  - per-pool expectancy with bootstrap 95% CI (never a bare mean)
  - IS-only discipline: this script DESCRIBES pools; it never picks rules.
    Rule changes still require >=30/class + desk adjudication (gates policy).
  - drift guards: rolling-50 one-direction share >85% (beta degeneration),
    rolling-50 expectancy decay vs full-history (edge decay alarm)
Pools: model / session / state / env_sbq / env_cycle / env_sweep_scope.
mfe caveat: rows resolved before 2026-07-10 carry inflated mfe_r — this
script uses result_r only, which is unaffected.

Run:  python3 scripts/pool_stats_audit.py
"""

from __future__ import annotations

import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scanner_service.papertrack import _load  # noqa: E402

DECAY_ALARM_R = 0.15
ONE_SIDE_SHARE = 0.85
ROLL = 50


def boot_ci(vals: list[float], n_boot: int = 1000, seed: int = 7) -> tuple[float, float]:
    rng = random.Random(seed)
    means = []
    for _ in range(n_boot):
        s = [rng.choice(vals) for _ in vals]
        means.append(sum(s) / len(s))
    means.sort()
    return means[int(0.025 * n_boot)], means[int(0.975 * n_boot)]


def line(label: str, vals: list[float]) -> str:
    n = len(vals)
    if n == 0:
        return f"  {label:<28} n=0"
    avg = sum(vals) / n
    wr = sum(1 for v in vals if v > 0) / n * 100
    lo, hi = boot_ci(vals) if n >= 5 else (avg, avg)
    sig = " *" if (lo > 0 or hi < 0) and n >= 30 else ""
    return (f"  {label:<28} n={n:<5} wr={wr:5.1f}% avgR={avg:+.3f} "
            f"CI95=[{lo:+.3f},{hi:+.3f}]{sig}")


def main() -> None:
    rows = [r for r in _load()
            if r.get("outcome") in ("win", "loss") and r.get("result_r") is not None]
    rows.sort(key=lambda r: r["ts"])
    print(f"resolved win/loss rows: {len(rows)}  "
          f"(CI marked * only when n>=30 and CI excludes 0)\n")

    for field in ("model", "session", "state", "env_sbq", "env_cycle", "env_sweep_scope"):
        pools = defaultdict(list)
        for r in rows:
            pools[str(r.get(field))].append(float(r["result_r"]))
        print(f"by {field}:")
        for k in sorted(pools, key=lambda k: -len(pools[k])):
            print(line(k, pools[k]))
        print()

    # floor2r variant vs baseline (rows that have the field)
    fl = [(float(r["result_r"]), float(r["floor2r_r"])) for r in rows
          if r.get("floor2r_r") is not None]
    if fl:
        base = [a for a, _ in fl]
        var = [b for _, b in fl]
        print(f"+2R floor variant (n={len(fl)}): baseline avgR={sum(base)/len(base):+.3f} "
              f"vs floor2r avgR={sum(var)/len(var):+.3f}\n")

    # drift guards on the newest ROLL rows
    tail = rows[-ROLL:]
    if len(tail) == ROLL:
        share_long = sum(1 for r in tail if r.get("direction") == "LONG") / ROLL
        full_avg = sum(float(r["result_r"]) for r in rows) / len(rows)
        tail_avg = sum(float(r["result_r"]) for r in tail) / ROLL
        print("drift guards (rolling last %d):" % ROLL)
        if max(share_long, 1 - share_long) > ONE_SIDE_SHARE:
            print(f"  ⚠️ one-direction share {max(share_long, 1 - share_long):.0%} "
                  f"> {ONE_SIDE_SHARE:.0%} — beta-degeneration check (AlphaMaster index lesson)")
        else:
            print(f"  direction balance ok (LONG {share_long:.0%})")
        if tail_avg < full_avg - DECAY_ALARM_R:
            print(f"  ⚠️ expectancy decay: rolling {tail_avg:+.3f} vs full {full_avg:+.3f}")
        else:
            print(f"  expectancy stable: rolling {tail_avg:+.3f} vs full {full_avg:+.3f}")


if __name__ == "__main__":
    main()
