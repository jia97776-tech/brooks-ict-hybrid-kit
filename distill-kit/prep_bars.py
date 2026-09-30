#!/usr/bin/env python3
"""把你手上的 K 线统一成 bars/{SYM}_M15.jsonl（UTC，每行 {"ts","open","high","low","close"}）。
M1/M5/M15 都行，自动重采样到 M15；同一品种多个文件（按年分的）会合并去重。

  # 扫描器历史（已经是 jsonl，直接拷）
  python3 prep_bars.py --src /home/box/trading_scanner_service/data/history --pattern '*_M15.jsonl'
  # FXCM 公开 M1（DateTime,BidOpen,...；可以是 .csv.gz）
  python3 prep_bars.py --src ~/trading-corpus/fxcm_m1 --pattern '*.csv*'
  # 单个文件，文件名里看不出品种时
  python3 prep_bars.py --src ~/Downloads/dax_m1.csv --sym GER40
支持：jsonl（ts 秒/毫秒）；csv/tsv（有表头或无表头）：时间列可以是 epoch、ISO、MM/DD/YYYY、DD.MM.YYYY、YYYY.MM.DD，
可带 'GMT+0200' 后缀；Bid/Ask 两套价时取 Bid。本地时间数据用 --tz-offset-hours 修正（如 +2 表示数据比 UTC 快 2 小时）。
"""
import argparse, csv, fnmatch, glob, gzip, io, json, os, re, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dk.common import kit_path, load_config

FMTS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M",
        "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y%m%d %H%M%S", "%Y%m%d %H:%M:%S",
        "%Y-%m-%d", "%m/%d/%Y", "%d.%m.%Y", "%Y.%m.%d"]
TIME_COLS = ["datetime", "time", "date", "timestamp", "ts", "gmt time", "local time", "open time", "opentime"]
_fmt_cache = {}


def parse_time(s, key):
    s = s.strip()
    if re.fullmatch(r"\d{9,13}(\.\d+)?", s):
        v = float(s)
        return int(v / 1000) if v > 1e11 else int(v)
    off = 0
    m = re.search(r"\s*(?:GMT|UTC)?([+-])(\d{2}):?(\d{2})$", s)
    if m and ("GMT" in s or "UTC" in s or re.search(r"[+-]\d{2}:\d{2}$", s)):
        off = (1 if m.group(1) == "+" else -1) * (int(m.group(2)) * 3600 + int(m.group(3)) * 60)
        s = s[: m.start()]
    s = s.replace("Z", "").strip()
    s = re.sub(r"(\d{2}:\d{2}:\d{2})\.\d+", r"\1", s)
    f = _fmt_cache.get(key)
    if f:
        try:
            return int(datetime.strptime(s, f).replace(tzinfo=timezone.utc).timestamp()) - off
        except ValueError:
            pass
    for f in FMTS:
        try:
            v = int(datetime.strptime(s, f).replace(tzinfo=timezone.utc).timestamp()) - off
            _fmt_cache[key] = f
            return v
        except ValueError:
            continue
    raise ValueError(f"认不出的时间格式：{s!r}")


def opener(p):
    return io.TextIOWrapper(gzip.open(p), encoding="utf-8") if p.endswith(".gz") else open(p, encoding="utf-8", newline="")


def read_jsonl(p):
    for l in opener(p):
        if l.strip():
            b = json.loads(l)
            t = b.get("ts", b.get("t", b.get("time")))
            t = parse_time(str(t), p) if not isinstance(t, (int, float)) else (int(t / 1000) if t > 1e11 else int(t))
            yield t, float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])


def read_csv(p):
    with opener(p) as f0:
        head = f0.read(4096)
    if not head.strip():
        return
    try:
        dialect = csv.Sniffer().sniff(head, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rd = csv.reader(opener(p), dialect)
    first = next(rd)
    low = [c.strip().lower() for c in first]
    has_header = any(x in low for x in TIME_COLS) or any("open" in x for x in low)
    if has_header:
        def col(*names):
            for n in names:
                for i, c in enumerate(low):
                    if c == n:
                        return i
            return None
        o = col("bidopen", "open", "o"); h = col("bidhigh", "high", "h"); l_ = col("bidlow", "low", "l"); c = col("bidclose", "close", "c")
        tcol = next((low.index(x) for x in TIME_COLS if x in low), 0)
        dcol = low.index("date") if "date" in low and "time" in low else None
        tcol = low.index("time") if dcol is not None else tcol
        rows = rd
    else:  # 无表头：时间在前（可能拆成 日期、时间 两列），后面依次 O H L C
        def gen():
            yield first
            yield from rd
        rows = gen()
        two = len(first) > 1 and re.fullmatch(r"\d{4}[.\-/]\d{2}[.\-/]\d{2}|\d{2}[./]\d{2}[./]\d{4}", first[0].strip()) and re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", first[1].strip())
        dcol, tcol = (0, 1) if two else (None, 0)
        base = 2 if two else 1
        o, h, l_, c = base, base + 1, base + 2, base + 3
    if None in (o, h, l_, c):
        raise ValueError(f"{p}: 找不到 open/high/low/close 列：{first}")
    for r in rows:
        if not r or not r[0].strip():
            continue
        try:
            ts_s = (r[dcol].strip() + " " + r[tcol].strip()) if dcol is not None else r[tcol]
            yield parse_time(ts_s, p), float(r[o]), float(r[h]), float(r[l_]), float(r[c])
        except (ValueError, IndexError):
            continue


def sym_from_name(p):
    n = os.path.basename(p)
    n = re.sub(r"\.(csv|tsv|txt|jsonl)(\.gz)?$", "", n, flags=re.I)
    n = re.split(r"[_\-\s.]", n)[0]
    return re.sub(r"[^A-Z0-9]", "", n.upper())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", nargs="+", required=True, help="文件或目录")
    ap.add_argument("--pattern", default="*", help="目录内文件名通配，如 '*_M15.jsonl' 或 '*.csv*'")
    ap.add_argument("--sym", help="强制品种名（单文件时用）")
    ap.add_argument("--rename", nargs="*", default=[], help="改名，如 GER30=GER40 FTSE=UK100")
    ap.add_argument("--tz-offset-hours", type=float, default=0.0)
    ap.add_argument("--out-dir")
    a = ap.parse_args()
    out_dir = kit_path(a.out_dir or load_config()["bars_dir"])
    os.makedirs(out_dir, exist_ok=True)
    ren = dict(x.split("=") for x in a.rename)
    files = []
    for s in a.src:
        s = os.path.expanduser(s)
        if os.path.isdir(s):
            files += [p for p in sorted(glob.glob(os.path.join(s, "**", "*"), recursive=True))
                      if os.path.isfile(p) and fnmatch.fnmatch(os.path.basename(p), a.pattern)]
        else:
            files.append(s)
    by_sym = {}
    for p in files:
        sym = a.sym or sym_from_name(p)
        sym = ren.get(sym, sym)
        by_sym.setdefault(sym, []).append(p)
    shift = int(a.tz_offset_hours * 3600)
    for sym, ps in sorted(by_sym.items()):
        bars = {}
        n_in = 0
        for p in ps:
            rd = read_jsonl(p) if re.search(r"\.jsonl(\.gz)?$", p) else read_csv(p)
            try:
                for t, o, h, l, c in rd:
                    n_in += 1
                    t -= shift
                    k = t // 900 * 900
                    b = bars.get(k)
                    if b is None:
                        bars[k] = [t, o, h, l, c, t]
                    else:  # 同一根 M15 里：开盘取最早、收盘取最晚
                        if t < b[0]: b[0], b[1] = t, o
                        b[2] = max(b[2], h); b[3] = min(b[3], l)
                        if t >= b[5]: b[5], b[4] = t, c
            except ValueError as ex:
                print(f"  跳过 {p}：{ex}")
        if not bars:
            print(f"{sym}: 没读到数据"); continue
        out = os.path.join(out_dir, f"{sym}_M15.jsonl")
        with open(out, "w", encoding="utf-8") as f:
            for k in sorted(bars):
                _, o, h, l, c, _ = bars[k]
                f.write(json.dumps({"ts": k, "open": o, "high": h, "low": l, "close": c}) + "\n")
        ks = sorted(bars)
        print(f"{sym}: {len(ps)} 个文件，{n_in} 行 → {len(bars)} 根 M15，"
              f"{datetime.fromtimestamp(ks[0], timezone.utc):%Y-%m-%d} ~ {datetime.fromtimestamp(ks[-1], timezone.utc):%Y-%m-%d}")


if __name__ == "__main__":
    main()
