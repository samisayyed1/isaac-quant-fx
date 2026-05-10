#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/sami/quant-fx"
LOG_DIR="$ROOT/runtime_logs"
mkdir -p "$LOG_DIR"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_FILE="$LOG_DIR/operating_review_$STAMP.log"

{
  echo "=== Isaac Operating Review V1 ==="
  echo "UTC: $(date -u --iso-8601=seconds)"

  cd "$ROOT"

  ./system_audit_v2.sh
  python3 daily_report_v1.py
  ./ai_research_loop_v1.sh
  python3 weekly_paper_evidence_report_v1.py
  python3 deployment_gate_checklist_v1.py

  echo "OPERATING REVIEW STATUS: GREEN"
} 2>&1 | tee "$LOG_FILE"
