#!/usr/bin/env python3
"""不花钱的整条流程自测：随机游走假 K 线 + 假交易员 + mock 桌面。能跑通就说明环境没问题。
  python3 selftest.py
"""
import gzip, json, math, os, random, shutil, subprocess, sys, time

K = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(K, "selftest_tmp")


def sh(*args):
    env = {**os.environ, "DK_CONFIG": os.path.join(T, "config.json")}
    print("$", " ".join(args), flush=True)
    r = subprocess.run([sys.executable, *args], cwd=K, env=env)
    if r.returncode:
        sys.exit(f"失败：{' '.join(args)}")


def main():
    shutil.rmtree(T, ignore_errors=True)
    os.makedirs(os.path.join(T, "raw"))
    rnd = random.Random(0)
    t0 = int(time.mktime((2021, 1, 4, 0, 0, 0, 0, 0, 0))) - time.timezone
    # 1) 假 M1 CSV（FXCM 格式，gz），两个品种各 ~20 个月
    for sym, p0 in (("EURUSD", 1.20), ("GBPUSD", 1.35)):
        p = p0
        with gzip.open(os.path.join(T, "raw", f"{sym}_M1.csv.gz"), "wt") as f:
            f.write("DateTime,BidOpen,BidHigh,BidLow,BidClose,AskOpen,AskHigh,AskLow,AskClose\n")
            for i in range(0, 600 * 1440, 5):  # 每 5 分钟一行，够测重采样
                ts = t0 + i * 60
                if time.gmtime(ts).tm_wday >= 5:
                    continue
                o = p; p *= math.exp(rnd.gauss(0, 0.0006)); h = max(o, p) * (1 + abs(rnd.gauss(0, 0.0002))); l = min(o, p) * (1 - abs(rnd.gauss(0, 0.0002)))
                f.write(time.strftime("%m/%d/%Y %H:%M:%S.000", time.gmtime(ts)) + f",{o:.5f},{h:.5f},{l:.5f},{p:.5f},{o:.5f},{h:.5f},{l:.5f},{p:.5f}\n")
    cfg = json.load(open(os.path.join(K, "config.example.json")))
    cfg.update(bars_dir=os.path.join(T, "bars"), default_backend="mock", reflector_backend="mock", workers=4)
    json.dump(cfg, open(os.path.join(T, "config.json"), "w"), indent=1)
    sh("prep_bars.py", "--src", os.path.join(T, "raw"), "--pattern", "*.csv.gz")

    # 2) 假交易员：随机时点下单
    with open(os.path.join(T, "trader.jsonl"), "w") as f:
        for n in range(160):
            sym = rnd.choice(["EURUSD", "GBPUSD"])
            ts = t0 + rnd.randint(170, 540) * 86400 + rnd.randint(30, 70) * 900
            if time.gmtime(ts).tm_wday >= 5:
                continue
            side = rnd.choice(["LONG", "SHORT"])
            bars = [json.loads(l) for l in open(os.path.join(T, "bars", f"{sym}_M15.jsonl"))]
            px = [b for b in bars if b["ts"] + 900 <= ts][-1]["close"]
            sgn = 1 if side == "LONG" else -1
            e = px - sgn * px * 0.002 * rnd.random()
            f.write(json.dumps({"sym": sym, "time": ts, "side": side, "type": rnd.choice(["limit", "market"]),
                                "entry": round(e, 5), "stop": round(e - sgn * px * 0.004, 5),
                                "quotes": ["Trend is down, entry retest of daily low"]}) + "\n")
    ex = os.path.join(T, "exam.jsonl")
    sh("build_exam.py", "--format", "canonical", "--src", os.path.join(T, "trader.jsonl"), "--out", ex)
    sh("edge_check.py", "--exam", ex, "--null", "5")
    sh("run_exam.py", "--exam", ex, "--split", "dev", "--skill", "none", "--tag", "st_a")
    sh("run_exam.py", "--exam", ex, "--split", "dev", "--skill", "none", "--tag", "st_b", "--rep", "1")
    sh("score.py", "--exam", ex, "--run", "st_a", "--run", "st_b", "--settle")
    sh("optimize.py", "--exam", ex, "--tag", "st", "--iters", "3", "--minibatch", "12", "--min-gain", "-1", "--min-prob", "0")
    print("\n自测通过。清理：rm -rf selftest_tmp runs/st_* runs/opt_st cache/mock")


if __name__ == "__main__":
    main()
