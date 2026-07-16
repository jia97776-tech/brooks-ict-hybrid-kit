#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="/home/ubuntu/trading_scanner_service"
LOG_FILE="/tmp/trading_scanner_service.log"
HEALTH_URL="http://127.0.0.1:8001/healthz"

# Give the systemd service the first chance to bind 8001 after boot.
sleep "${SCANNER_BOOT_DELAY:-15}"

if curl -fsS -m 2 "$HEALTH_URL" >/dev/null 2>&1; then
  exit 0
fi

if pgrep -f "$BASE_DIR/run_server.py" >/dev/null 2>&1; then
  exit 0
fi

cd "$BASE_DIR"
exec setsid python3 run_server.py >>"$LOG_FILE" 2>&1 < /dev/null
