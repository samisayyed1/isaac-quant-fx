#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "=== Git Status ==="
git status --short

echo ""
echo "=== Crontab ==="
if ! crontab -l; then
  echo "No crontab installed for current user."
fi

echo ""
python3 daily_report_v1.py

echo ""
python3 deployment_gate_checklist_v1.py

echo ""
python3 paper_vs_backtest_comparison_v1.py

echo ""
python3 weekly_paper_evidence_report_v1.py

echo "PAPER OPS CHECK STATUS: GREEN"
