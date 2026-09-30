"""模型调用：命令行后端（claude / codex / grok / 任意命令）+ Anthropic API 后端 + mock（自测用）。
带磁盘缓存：同一后端、同一提示词、同一遍次(rep) 只调一次。"""
import json, os, random, subprocess, tempfile, threading, time

from .common import KIT, sha

_lock = threading.Lock()
_client = None


def _cache_path(name, system, user, rep):
    d = os.path.join(KIT, "cache", name)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, sha(system + "\x00" + user + f"\x00{rep}") + ".txt")


def call(cfg, name, system, user, rep=0, use_cache=True):
    """返回模型的原始文本输出。失败返回 None。"""
    be = cfg["backends"][name]
    cp = _cache_path(name, system, user, rep)
    if use_cache and os.path.exists(cp):
        return open(cp, encoding="utf-8").read()
    txt = None
    for attempt in range(be.get("retries", 2) + 1):
        try:
            if be.get("type") == "mock":
                txt = _mock(system, user, rep)
            elif be.get("type") == "anthropic":
                txt = _anthropic(be, system, user)
            else:
                txt = _cli(be, system, user)
            if txt:
                break
        except Exception as ex:  # 网络/超时/CLI 错误：退避重试
            txt = None
            err = f"{type(ex).__name__}: {ex}"
            with _lock:
                print(f"  [{name}] 第{attempt + 1}次失败 {err[:200]}", flush=True)
            time.sleep(5 * (attempt + 1))
    if txt and use_cache:
        with open(cp, "w", encoding="utf-8") as f:
            f.write(txt)
    return txt


def _cli(be, system, user):
    prompt = system + "\n\n" + user
    with tempfile.TemporaryDirectory(prefix="dk_") as wd:  # 空目录：桌面读不到任何项目文件
        pf = os.path.join(wd, "prompt.txt")
        with open(pf, "w", encoding="utf-8") as f:
            f.write(prompt)
        cmd = [c.replace("{prompt_file}", pf).replace("{prompt}", prompt) for c in be["cmd"]]
        r = subprocess.run(cmd, input=prompt if be.get("stdin") else None, capture_output=True, text=True,
                           timeout=be.get("timeout", 900), cwd=wd, env={**os.environ, **be.get("env", {})})
    if r.returncode != 0 and not r.stdout.strip():
        raise RuntimeError(f"exit {r.returncode}: {r.stderr[-300:]}")
    return r.stdout


def _anthropic(be, system, user):
    """官方 SDK（pip install anthropic）。手册放 system 并开缓存：同一版手册跑几百题只付一次全价。"""
    global _client
    import anthropic
    with _lock:
        if _client is None:
            _client = anthropic.Anthropic()
    kw = dict(model=be.get("model", "claude-opus-5-5"), max_tokens=be.get("max_tokens", 16000),
              system=system, messages=[{"role": "user", "content": user}],
              cache_control={"type": "ephemeral"}, output_config={"effort": be.get("effort", "high")})
    if be.get("fallbacks", True):
        # 被安全分类器误拒时，服务端自动换模型重跑（默认开启；不想要就在 config 里设 "fallbacks": false）
        kw["betas"] = ["server-side-fallback-2026-07-01"]
        kw["extra_body"] = {"fallbacks": "default"}
        resp = _client.beta.messages.create(**kw)
    else:
        resp = _client.messages.create(**kw)
    if resp.stop_reason == "refusal":
        return None
    return "".join(b.text for b in resp.content if b.type == "text")


def _mock(system, user, rep):
    """自测用假桌面：随机但可复现。reflector 请求返回一条假修改。"""
    rnd = random.Random(sha(system + user) + str(rep))
    if '"ops"' in user:
        return json.dumps({"ops": [{"op": "add", "text": f"示例条目 {rnd.randint(1, 999)}：先看 D1 旧水平位，再在 H4 等回测。",
                                    "evidence": ["mock"]}]}, ensure_ascii=False)
    price = None
    for line in user.splitlines():
        if line.startswith("现价"):
            price = float(line.split("=")[-1])
    if price is None or rnd.random() < 0.45:
        return '{"decision":"不做","side":"none","entry":0,"stop":0,"level":"","reason":"mock"}'
    side = rnd.choice(["LONG", "SHORT"])
    d = price * 0.004
    sgn = 1 if side == "LONG" else -1
    dec = rnd.choice(["市价", "挂单"])
    entry = price if dec == "市价" else price - sgn * d * rnd.random()
    return json.dumps({"decision": dec, "side": side, "entry": round(entry, 5), "stop": round(entry - sgn * d, 5),
                       "level": "mock", "reason": "mock"}, ensure_ascii=False)
