"""Push freshly-scanned READY signals to the user's Feishu DM.

Pipeline per user's standing rules:
  READY + not late + not target_crowded + not news_risk + fresh (last scan)
  -> dedupe/cooldown (one push per signal key per 4h)
  -> Claude second review (Sonnet, low effort) — signals must NEVER be pushed
     unreviewed; a review failure means no push, not a bare push
  -> Feishu DM via the bridge app credentials.

Run from cron a few minutes after each scan:
  python3 -m scanner_service.push_ready
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from pathlib import Path

from scanner_service.papertrack import SIGNALS_FILE, _key, _load

DATA_DIR = SIGNALS_FILE.parent
PUSHED_FILE = DATA_DIR / "pushed.json"
BRIDGE_CONFIG = Path("/home/ubuntu/feishu-claude-bridge/config.json")
CLAUDE_BIN = "/home/ubuntu/.npm-global/bin/claude"

FRESH_WINDOW_S = 40 * 60
COOLDOWN_S = 4 * 3600
MAX_REVIEWS_PER_RUN = 3
REVIEW_TIMEOUT_S = 150

REVIEW_PROMPT = """你是实盘桌面交易员，二审一条机械扫描信号。只判断这条信号作为“候选交易计划”是否值得推送给交易者手机（不是判断行情方向对错）。

否决条件：数字自相矛盾（SL/DOL 与方向不符）、RR 虚高不合理、POI 区间与现价关系荒谬、reason 与字段矛盾。除此之外默认放行。

信号：
{signal}

只回复一行：PASS 或 VETO: <一句理由>"""


def _load_pushed() -> dict:
    if PUSHED_FILE.exists():
        try:
            return json.loads(PUSHED_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _feishu_token(app_id: str, app_secret: str) -> str:
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)["tenant_access_token"]


def send_feishu(text: str) -> None:
    cfg = json.loads(BRIDGE_CONFIG.read_text(encoding="utf-8"))
    # prefer the chat the user actually talks to the bridge in — a bot-initiated
    # open_id DM lands in a conversation the user may have never opened
    receive_id, id_type = None, None
    sessions = BRIDGE_CONFIG.parent / "sessions.json"
    if sessions.exists():
        try:
            chats = list(json.loads(sessions.read_text(encoding="utf-8")))
            if chats:
                receive_id, id_type = chats[0], "chat_id"
        except json.JSONDecodeError:
            pass
    if receive_id is None:
        open_ids = cfg.get("allowed_open_ids") or []
        if not open_ids:
            raise RuntimeError("no chat_id in sessions.json and no allowed_open_ids in bridge config")
        receive_id, id_type = open_ids[0], "open_id"
    token = _feishu_token(cfg["app_id"], cfg["app_secret"])
    req = urllib.request.Request(
        f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={id_type}",
        data=json.dumps({"receive_id": receive_id, "msg_type": "text",
                         "content": json.dumps({"text": text}, ensure_ascii=False)}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        payload = json.load(resp)
    if payload.get("code") != 0:
        raise RuntimeError(f"feishu send failed: code={payload.get('code')} msg={payload.get('msg')}")


def second_review(signal: dict) -> tuple[bool, str]:
    compact = {k: signal.get(k) for k in
               ("symbol", "tf", "direction", "state", "price", "entry_ref", "sl",
                "dol", "rr", "rr_now", "mss", "cisd", "swept_level", "reason")}
    prompt = REVIEW_PROMPT.format(signal=json.dumps(compact, ensure_ascii=False))
    last = ""
    for binary in (CLAUDE_BIN, "/home/ubuntu/.local/bin/reclaude"):
        try:
            result = subprocess.run(
                [binary, "-p", "--model", "claude-sonnet-5", "--effort", "low",
                 "--dangerously-skip-permissions", prompt],
                capture_output=True, text=True, timeout=REVIEW_TIMEOUT_S)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            last = f"review unavailable: {exc}"
            continue
        answer = (result.stdout or "").strip()
        # wrappers may prepend noise lines (e.g. "Syncing config…") — judge by
        # the first line that actually says PASS/VETO, not by a raw prefix
        verdict_lines = [ln.strip() for ln in answer.splitlines()
                         if ln.strip().upper().startswith(("PASS", "VETO"))]
        if result.returncode == 0 and verdict_lines:
            if verdict_lines[0].upper().startswith("PASS"):
                return True, "PASS"
            return False, verdict_lines[0][:200]
        last = (answer[:200] or f"exit={result.returncode} {result.stderr[:120]}")
        if "not logged in" not in last.lower():
            return False, last
    return False, f"review unavailable: {last}"


def format_push(s: dict) -> str:
    poi_lo, poi_hi = sorted([s["swept_level"], 2 * s["entry_ref"] - s["swept_level"]])
    confirms = "+".join(n for n, ok in (("MSS", s.get("mss")), ("CISD", s.get("cisd"))) if ok)
    return (f"⚡ 扫描器 READY：{s['symbol']} {s['direction']} ({s['tf']})\n"
            f"现价 {s['price']}，POI {poi_lo}-{poi_hi}，SL {s['sl']}，目标 {s['dol']}"
            f"（回踩计划 RR {s['rr']}）\n"
            f"{confirms} 收盘确认。已过二审。这是信号不是指令：回踩确认了再动，别市价追。")


def run(now: int | None = None) -> dict:
    now = now or int(time.time())
    rows = _load()
    pushed = _load_pushed()
    fresh = [r for r in rows
             if r.get("outcome") == "pending"
             and r.get("model", "poi_retest") == "poi_retest"
             and r.get("state") == "READY"
             and not r.get("late") and not r.get("target_crowded")
             and not r.get("news_risk")
             and now - r["ts"] <= FRESH_WINDOW_S]
    sent, vetoed, skipped = 0, 0, 0
    for r in fresh[:MAX_REVIEWS_PER_RUN]:
        key = json.dumps(_key(r), ensure_ascii=False)
        if now - pushed.get(key, 0) < COOLDOWN_S:
            skipped += 1
            continue
        ok, verdict = second_review(r)
        pushed[key] = now  # reviewed once per cooldown window either way
        if not ok:
            vetoed += 1
            print(f"[push] VETO {r['symbol']} {r['direction']}: {verdict}", flush=True)
            continue
        try:
            send_feishu(format_push(r))
            sent += 1
            print(f"[push] SENT {r['symbol']} {r['direction']} {r['tf']}", flush=True)
        except Exception as exc:
            print(f"[push] send failed {r['symbol']}: {exc}", flush=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PUSHED_FILE.write_text(json.dumps(pushed, ensure_ascii=False), encoding="utf-8")
    return {"fresh": len(fresh), "sent": sent, "vetoed": vetoed, "cooldown_skipped": skipped}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
