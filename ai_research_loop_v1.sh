#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/sami/quant-fx"
LOG_DIR="$ROOT/runtime_logs"
mkdir -p "$LOG_DIR"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_FILE="$LOG_DIR/ai_research_loop_$STAMP.log"

{
  echo "=== Isaac AI Research Loop V1 ==="
  echo "UTC: $(date -u --iso-8601=seconds)"

  cd "$ROOT"

  ./system_audit_v2.sh
  python3 research_memory_v1.py snapshot
  python3 local_research_agent_v1.py
  python3 cloud_research_connector_v1.py
  python3 ingest_cloud_research_note_v1.py
  python3 daily_report_v1.py

  echo "AI RESEARCH LOOP STATUS: GREEN"
} 2>&1 | tee "$LOG_FILE"
