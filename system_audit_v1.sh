#!/usr/bin/env bash
set -euo pipefail

echo "=== Isaac Quant-FX System Audit V1 ==="

required_files=(
  "/home/sami/download/eurusd-m15-bid-2025-01-01-2026-01-01.csv"
  "/home/sami/quant-fx/backtest_asia_breakout.py"
  "/home/sami/quant-fx/optimize_asia_breakout.py"
  "/home/sami/quant-fx/validate_candidate.py"
  "/home/sami/quant-fx/signal_scanner_v2.py"
  "/home/sami/quant-fx/paper_ledger_v1.py"
  "/home/sami/quant-fx/paper_signal_bridge_v1.py"
  "/home/sami/quant-fx/paper_exit_resolver_v1.py"
  "/home/sami/quant-fx/full_replay_v1.py"
)

for f in "${required_files[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "FAIL: missing $f"
    exit 1
  fi
done

echo "Files: OK"

python3 /home/sami/quant-fx/full_replay_v1.py > /tmp/isaac_full_replay.out

cat /tmp/isaac_full_replay.out

grep -q "Trades: 115" /tmp/isaac_full_replay.out
grep -q "Total net pips: 1094.30" /tmp/isaac_full_replay.out
grep -q "Profit factor: 2.36" /tmp/isaac_full_replay.out
grep -q "Max drawdown: -67.90" /tmp/isaac_full_replay.out

echo "Replay metrics: OK"
echo "SYSTEM STATUS: GREEN"
