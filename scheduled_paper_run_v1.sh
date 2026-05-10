#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/sami/quant-fx"
LOG_DIR="$ROOT/runtime_logs"
mkdir -p "$LOG_DIR"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_FILE="$LOG_DIR/paper_run_$STAMP.log"

{
  echo "=== Isaac Scheduled Paper Run V1 ==="
  echo "UTC: $(date -u --iso-8601=seconds)"

  DOW="$(date -u +%u)"
  HOUR="$(date -u +%H)"
  MIN="$(date -u +%M)"

  if [[ "$DOW" -gt 4 ]]; then
    echo "SKIP: not Monday-Thursday UTC."
    exit 0
  fi

  if [[ "$HOUR" != "08" && "$HOUR" != "09" && "$HOUR" != "10" && "$HOUR" != "11" && "$HOUR" != "12" && "$HOUR" != "13" && "$HOUR" != "14" ]]; then
    echo "SKIP: outside operating window."
    exit 0
  fi

  cd "$ROOT"

  python3 paper_live_runner_v1.py --lot 0.01
  python3 daily_report_v1.py

  echo "DONE"
} 2>&1 | tee "$LOG_FILE"
