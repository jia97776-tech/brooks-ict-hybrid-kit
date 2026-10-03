"""公共件：K 线读取/重采样、盲测上下文、提示词、JSON 抽取、结算、统计。纯标准库。"""
import bisect, hashlib, json, math, os, random, re, time

TF = {"M15": 900, "H1": 3600, "H4": 14400, "D1": 86400, "W1": 604800}
_MONDAY = 4 * 86400  # 1970-01-01 是周四，+4 天对齐到周一 00:00 UTC
WD = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------- 配置 / IO ----------

def load_config(path=None):
    p = path or os.environ.get("DK_CONFIG") or os.path.join(KIT, "config.json")
    if not os.path.exists(p):
        p = os.path.join(KIT, "config.example.json")
    cfg = json.load(open(p, encoding="utf-8"))
    cfg["_path"] = p
    return cfg


def kit_path(p):
    return p if os.path.isabs(p) else os.path.join(KIT, p)


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def append_jsonl(path, row):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def iso(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(ts))


# ---------- K 线 ----------

def bucket(ts, tf):
    s = TF[tf]
    if tf == "W1":
        return (ts - _MONDAY) // s * s + _MONDAY
    return ts // s * s


def resample(m15, tf):
    out, cur = [], None
    for b in m15:
        k = bucket(b["ts"], tf)
        if cur is None or cur["ts"] != k:
            cur = {"ts": k, "open": b["open"], "high": b["high"], "low": b["low"], "close": b["close"]}
            out.append(cur)
        else:
            cur["high"] = max(cur["high"], b["high"]); cur["low"] = min(cur["low"], b["low"]); cur["close"] = b["close"]
    return out


class Bars:
    """bars_dir/{SYM}_M15.jsonl，每行 {"ts":开盘秒,"open","high","low","close"}。其它周期由 M15 重采样。"""

    def __init__(self, bars_dir):
        self.dir = kit_path(bars_dir)
        self._c = {}

    def has(self, sym):
        return os.path.exists(os.path.join(self.dir, f"{sym}_M15.jsonl"))

    def get(self, sym, tf="M15"):
        k = (sym, tf)
        if k not in self._c:
            if tf == "M15":
                d = {}
                for l in open(os.path.join(self.dir, f"{sym}_M15.jsonl")):
                    if l.strip():
                        b = json.loads(l)
                        d[int(b["ts"])] = {"ts": int(b["ts"]), "open": float(b["open"]), "high": float(b["high"]),
                                           "low": float(b["low"]), "close": float(b["close"])}
                rows = [d[t] for t in sorted(d)]
            else:
                rows = resample(self.get(sym, "M15")[0], tf)
            self._c[k] = (rows, [b["ts"] for b in rows])
        return self._c[k]

    def closed(self, sym, tf, ts, n):
        """截至 ts 已收盘的最后 n 根（bar.ts + 周期 <= ts）。"""
        rows, keys = self.get(sym, tf)
        i = bisect.bisect_right(keys, ts - TF[tf])
        return rows[max(0, i - n):i]

    def after(self, sym, ts, n=None):
        """ts 之后开盘的 M15（用于结算）。"""
        rows, keys = self.get(sym, "M15")
        i = bisect.bisect_left(keys, ts)
        return rows[i:] if n is None else rows[i:i + n]

    def span(self, sym):
        rows, _ = self.get(sym, "M15")
        return (rows[0]["ts"], rows[-1]["ts"]) if rows else (0, 0)


def atr(rows, n=14):
    if len(rows) < 2:
        return None
    trs = [max(b["high"] - b["low"], abs(b["high"] - a["close"]), abs(b["low"] - a["close"])) for a, b in zip(rows, rows[1:])]
    trs = trs[-n:]
    return sum(trs) / len(trs)


def sma(rows, n=20):
    if len(rows) < n:
        return None
    return sum(b["close"] for b in rows[-n:]) / n


def decimals(price):
    if not price or price <= 0:
        return 5
    return max(0, min(6, 5 - int(math.floor(math.log10(price)))))


def parse_ctx(spec):
    out = []
    for part in spec.split(","):
        tf, n = part.split(":")
        out.append((tf.strip().upper(), int(n)))
    return out


def market_snapshot(bars, sym, ts):
    m = bars.closed(sym, "M15", ts, 1)
    if not m:
        return None
    h4 = bars.closed(sym, "H4", ts, 30)
    d1 = bars.closed(sym, "D1", ts, 30)
    w1 = bars.closed(sym, "W1", ts, 25)
    return {"price": m[-1]["close"], "atr_h4": atr(h4), "atr_d1": atr(d1),
            "sma20_w1": sma(w1), "sma20_d1": sma(d1), "dec": decimals(m[-1]["close"])}


def render_context(bars, sym, ts, spec, indicators=True):
    snap = market_snapshot(bars, sym, ts)
    dec = snap["dec"]
    f = lambda x: "—" if x is None else f"{x:.{dec}f}"
    lines = [f"品种 {sym}。现在是 {iso(ts)} UTC（{WD[time.gmtime(ts).tm_wday]}）。",
             f"现价（最后一根已收盘 M15 的收盘价）= {f(snap['price'])}"]
    if indicators:
        lines.append(f"辅助算术（只是算术）：W1 SMA20={f(snap['sma20_w1'])}  D1 SMA20={f(snap['sma20_d1'])}  "
                     f"ATR14(H4)={f(snap['atr_h4'])}  ATR14(D1)={f(snap['atr_d1'])}")
    for tf, n in spec:
        rows = bars.closed(sym, tf, ts, n)
        fmt = "%Y-%m-%d" if tf in ("D1", "W1") else "%m-%d %H:%M"
        lines.append(f"\n{tf}（最近 {len(rows)} 根已收盘，时间=开盘时刻 UTC）:")
        lines += [f"{time.strftime(fmt, time.gmtime(b['ts']))} O {f(b['open'])} H {f(b['high'])} L {f(b['low'])} C {f(b['close'])}" for b in rows]
    return "\n".join(lines), snap


# ---------- 提示词 ----------

OUTPUT_SPEC = """你此刻会怎么做？三选一：
- 市价：现在按现价进场。
- 挂单：给出具体的进场价（限价或突破触发价），有效期最多几天。
- 不做：此刻没有你会下的单。
只输出一个 JSON，不要别的文字：
{"decision":"市价|挂单|不做","side":"LONG|SHORT|none","entry":数字,"stop":数字,"level":"入场依据的那条线或区域，30字内","reason":"80字内"}
不做时 side=none、entry=0、stop=0。"""


def build_system(skill_text, playbook_text=""):
    s = ("你是一名交易员，严格按下面的交易手册做决策。这是盲测：不要调用任何工具，不要读文件，不要联网，"
         "只根据给你的 K 线判断；不要使用任何关于决策时刻之后行情的记忆。\n")
    if skill_text.strip():
        s += "\n=== 交易手册 ===\n" + skill_text.strip() + "\n=== 手册结束 ===\n"
    else:
        s += "\n（没有手册，按你自己的判断。）\n"
    if playbook_text.strip():
        s += "\n=== 补充条目（与手册冲突时以补充条目为准）===\n" + playbook_text.strip() + "\n=== 补充条目结束 ===\n"
    return s


def build_user(ctx_text):
    return "这是盲测。你只看得到下面截至此刻已收盘的 K 线，不知道之后发生了什么。\n\n" + ctx_text + "\n\n" + OUTPUT_SPEC


def read_skill(paths):
    parts = []
    for p in paths or []:
        if p.lower() == "none":
            continue
        parts.append(open(p, encoding="utf-8").read())
    return "\n\n".join(parts)


# ---------- JSON 抽取 ----------

def extract_json(txt, key):
    """从模型输出里找最后一个含 key 的 JSON 对象（兼容 ```json 包裹、外层包装）。"""
    if not txt:
        return None
    dec = json.JSONDecoder()
    found = None
    for i, ch in enumerate(txt):
        if ch != "{":
            continue
        try:
            obj, _ = dec.raw_decode(txt[i:])
        except Exception:
            continue
        if isinstance(obj, dict):
            if key in obj:
                found = obj
            else:
                for v in obj.values():
                    if isinstance(v, dict) and key in v:
                        found = v
                    elif isinstance(v, str) and key in v:
                        inner = extract_json(v, key)
                        if inner:
                            found = inner
    return found


def normalize_answer(a):
    if not a:
        return None
    d = str(a.get("decision", "")).strip()
    d = {"market": "市价", "limit": "挂单", "none": "不做", "pass": "不做"}.get(d.lower(), d)
    if d not in ("市价", "挂单", "不做"):
        return None
    side = str(a.get("side", "none")).upper()
    try:
        entry, stop = float(a.get("entry") or 0), float(a.get("stop") or 0)
    except Exception:
        return None
    if d != "不做":
        if side not in ("LONG", "SHORT") or not entry or not stop:
            return None
        if (side == "LONG" and stop >= entry) or (side == "SHORT" and stop <= entry):
            return None
    else:
        side, entry, stop = "none", 0.0, 0.0
    return {"decision": d, "side": side, "entry": entry, "stop": stop,
            "level": str(a.get("level", ""))[:80], "reason": str(a.get("reason", ""))[:200]}


# ---------- 结算 ----------

def settle(bars, sym, ts, side, otype, entry, stop, price, ttl_days=14, cap_days=30):
    """固定口径：市价=现价成交；挂单=14 天内触价成交（入场价在现价哪侧决定是回踩还是突破）。
    成交后只看初始止损：先到 +1R/+2R 还是先到 SL；同一根同时碰 = 先算止损。30 天未决按最后收盘计 R。"""
    L = side == "LONG"
    rows = bars.after(sym, ts, int((cap_days + ttl_days) * 96))
    if not rows:
        return {"filled": False, "why": "no_bars"}
    fi, e = None, entry
    if otype == "market":
        fi, e = 0, price
    else:
        below = entry <= price
        for j, b in enumerate(rows[: ttl_days * 96]):
            if (below and b["low"] <= entry) or (not below and b["high"] >= entry):
                fi = j
                if (below and b["open"] < entry) or (not below and b["open"] > entry):
                    e = b["open"]  # 跳空穿过：按开盘价成交
                break
    if fi is None:
        return {"filled": False, "why": "no_fill"}
    R = abs(e - stop)
    if R <= 0 or (L and stop >= e) or (not L and stop <= e):
        return {"filled": False, "why": "bad_geometry"}
    best, hit1, hit2, res = 0.0, False, False, None
    end = min(len(rows), fi + cap_days * 96)
    for j in range(fi, end):
        b = rows[j]
        adverse = b["low"] <= stop if L else b["high"] >= stop
        fav = ((b["high"] - e) if L else (e - b["low"])) / R
        if adverse:
            res = -1.0
            break
        best = max(best, fav)
        hit1 = hit1 or best >= 1
        if best >= 2:
            hit2, res = True, 2.0
            break
    if res is None:
        last = rows[end - 1]["close"]
        res = ((last - e) if L else (e - last)) / R
    return {"filled": True, "fill_ts": rows[fi]["ts"], "entry": e, "hit1R": hit1 or res >= 2, "hit2R": hit2, "r2": round(res, 3)}


# ---------- 统计 ----------

def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float("nan")


def boot_ci(xs, n=2000, seed=1):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return (float("nan"), float("nan"))
    rnd = random.Random(seed)
    ms = sorted(sum(rnd.choice(xs) for _ in xs) / len(xs) for _ in range(n))
    return (ms[int(0.025 * n)], ms[int(0.975 * n) - 1])


def paired_boot(diffs, n=2000, seed=1):
    """配对差的均值、95% CI、P(差>0)。"""
    diffs = [d for d in diffs if d is not None]
    if not diffs:
        return float("nan"), (float("nan"), float("nan")), float("nan")
    rnd = random.Random(seed)
    ms = sorted(sum(rnd.choice(diffs) for _ in diffs) / len(diffs) for _ in range(n))
    return sum(diffs) / len(diffs), (ms[int(0.025 * n)], ms[int(0.975 * n) - 1]), sum(m > 0 for m in ms) / n


def pct(x):
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.1f}%"
