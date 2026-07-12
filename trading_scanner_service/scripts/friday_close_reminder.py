#!/usr/bin/env python3
"""Friday-close flat reminder for non-crypto positions.

Skill rule (2026-07-10 user ruling): non-crypto has no Friday freeze — trade
Friday normally, but ALL non-crypto (CFD) positions must be flat before the
Friday market close (17:00 America/New_York). This pings Feishu with the
actual minutes remaining, DST handled via zoneinfo.

Cron (server tz Asia/Shanghai; NY Fri 17:00 = Sat 05:00 CST summer / 06:00 winter):
  0 4 * * 6   ~1-2h before close
  45 4 * * 6  ~15-75min before close
Runs outside the window (>6h to close, or market already closed) exit silently.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scanner_service.push_ready import send_feishu  # noqa: E402

NY = ZoneInfo("America/New_York")


def minutes_to_friday_close(now: datetime) -> float:
    ny = now.astimezone(NY)
    close = ny.replace(hour=17, minute=0, second=0, microsecond=0)
    close += timedelta(days=(4 - close.weekday()) % 7)  # next Friday (or today)
    if ny.weekday() == 4 and ny >= close:  # Friday after close
        return -1.0
    return (close - ny).total_seconds() / 60.0


def main() -> None:
    mins = minutes_to_friday_close(datetime.now(tz=ZoneInfo("UTC")))
    if mins < 0 or mins > 360:  # closed already, or way too early — stay quiet
        return
    hh, mm = int(mins) // 60, int(mins) % 60
    left = f"{hh} 小时 {mm} 分钟" if hh else f"{mm} 分钟"
    text = (f"⏰ 周五闭盘检查：非加密离闭盘还剩 {left}（纽约 17:00）。\n"
            f"规则：非加密不留仓过周末——FX/金属/指数/油的 CFD 仓位闭盘前必须平掉。\n"
            f"现在有非加密持仓的话，安排离场或回复桌面要个收尾计划。加密不受限。")
    if "--dry" in sys.argv:
        print(text)
        return
    send_feishu(text)


if __name__ == "__main__":
    main()
