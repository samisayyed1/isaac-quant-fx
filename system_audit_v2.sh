#!/usr/bin/env bash
set -euo pipefail

echo "=== Isaac Quant-FX System Audit V2 ==="

required_files=(
  "/home/sami/quant-fx/strategy_config_v1.py"
  "/home/sami/quant-fx/strategy_config_audit_v1.py"
  "/home/sami/quant-fx/paper_live_runner_v2.py"
  "/home/sami/quant-fx/daily_report_v1.py"
  "/home/sami/quant-fx/research_memory_v1.py"
  "/home/sami/quant-fx/multiyear_replay_v1.py"
  "/home/sami/quant-fx/v3_no_december_stress.py"
  "/home/sami/quant-fx/data/combined/eurusd-m15-bid-2021-01-01-2026-01-01.csv"
  "/home/sami/quant-fx/data/combined/multiyear_replay_trades.csv"
)

for f in "${required_files[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "FAIL: missing $f"
    exit 1
  fi
done

echo "Files: OK"

python3 /home/sami/quant-fx/strategy_config_audit_v1.py > /tmp/isaac_config_audit.out
cat /tmp/isaac_config_audit.out
grep -q "CONFIG STATUS: GREEN" /tmp/isaac_config_audit.out
grep -q "EURUSD_ASIA_BREAKOUT_V3_NO_DECEMBER" /tmp/isaac_config_audit.out

echo "Config audit: OK"

python3 /home/sami/quant-fx/multiyear_replay_v1.py > /tmp/isaac_multiyear_replay.out
cat /tmp/isaac_multiyear_replay.out

grep -q "Trades: 650" /tmp/isaac_multiyear_replay.out
grep -q "Total net pips: 4022.60" /tmp/isaac_multiyear_replay.out
grep -q "Profit factor: 1.79" /tmp/isaac_multiyear_replay.out
grep -q "Max drawdown: -222.30" /tmp/isaac_multiyear_replay.out

echo "Multi-year replay: OK"

python3 /home/sami/quant-fx/v3_no_december_stress.py > /tmp/isaac_v3_stress.out
cat /tmp/isaac_v3_stress.out

grep -q "Trades: 594" /tmp/isaac_v3_stress.out
grep -q "Total net pips: 4186.50" /tmp/isaac_v3_stress.out
grep -q "Profit factor: 1.94" /tmp/isaac_v3_stress.out
grep -q "Max drawdown: -188.00" /tmp/isaac_v3_stress.out

echo "V3 stress: OK"

python3 /home/sami/quant-fx/paper_live_runner_v2.py --skip-update --lot 0.01 > /tmp/isaac_runner_v2.out
cat /tmp/isaac_runner_v2.out
grep -q "Strategy: EURUSD_ASIA_BREAKOUT_V3_NO_DECEMBER" /tmp/isaac_runner_v2.out

echo "Paper runner: OK"

python3 /home/sami/quant-fx/daily_report_v1.py > /tmp/isaac_daily_report.out
cat /tmp/isaac_daily_report.out
grep -q "Active strategy: EURUSD_ASIA_BREAKOUT_V3_NO_DECEMBER" /tmp/isaac_daily_report.out

echo "Daily report: OK"
echo "SYSTEM STATUS: GREEN"
