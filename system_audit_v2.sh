#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP_DIR="${TMPDIR:-/tmp}"
CONFIG_OUT="$(mktemp "$TMP_DIR/isaac_config_audit.XXXXXX")"
REPLAY_OUT="$(mktemp "$TMP_DIR/isaac_multiyear_replay.XXXXXX")"
STRESS_OUT="$(mktemp "$TMP_DIR/isaac_v3_stress.XXXXXX")"
RUNNER_OUT="$(mktemp "$TMP_DIR/isaac_runner_v2.XXXXXX")"
DAILY_OUT="$(mktemp "$TMP_DIR/isaac_daily_report.XXXXXX")"

cleanup() {
  rm -f "$CONFIG_OUT" "$REPLAY_OUT" "$STRESS_OUT" "$RUNNER_OUT" "$DAILY_OUT"
}
trap cleanup EXIT

CFG_NAME="$(
  cd "$ROOT"
  python3 - <<'PY'
from strategy_config_v1 import OPERATIONAL_STRATEGY
print(OPERATIONAL_STRATEGY.name)
PY
)"

echo "=== Isaac Quant-FX System Audit V2 ==="

required_files=(
  "$ROOT/strategy_config_v1.py"
  "$ROOT/strategy_config_audit_v1.py"
  "$ROOT/paper_live_runner_v2.py"
  "$ROOT/daily_report_v1.py"
  "$ROOT/research_memory_v1.py"
  "$ROOT/multiyear_replay_v1.py"
  "$ROOT/v3_no_december_stress.py"
  "$ROOT/data/combined/eurusd-m15-bid-2021-01-01-2026-01-01.csv"
  "$ROOT/data/combined/multiyear_replay_trades.csv"
)

for f in "${required_files[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "FAIL: missing $f"
    exit 1
  fi
done

echo "Files: OK"

python3 "$ROOT/strategy_config_audit_v1.py" > "$CONFIG_OUT"
cat "$CONFIG_OUT"
grep -q "CONFIG STATUS: GREEN" "$CONFIG_OUT"
grep -q "$CFG_NAME" "$CONFIG_OUT"

echo "Config audit: OK"

python3 "$ROOT/multiyear_replay_v1.py" > "$REPLAY_OUT"
cat "$REPLAY_OUT"

grep -q "Trades: 650" "$REPLAY_OUT"
grep -q "Total net pips: 4022.60" "$REPLAY_OUT"
grep -q "Profit factor: 1.79" "$REPLAY_OUT"
grep -q "Max drawdown: -222.30" "$REPLAY_OUT"

echo "Multi-year replay: OK"

python3 "$ROOT/v3_no_december_stress.py" > "$STRESS_OUT"
cat "$STRESS_OUT"

grep -q "Trades: 594" "$STRESS_OUT"
grep -q "Total net pips: 4186.50" "$STRESS_OUT"
grep -q "Profit factor: 1.94" "$STRESS_OUT"
grep -q "Max drawdown: -188.00" "$STRESS_OUT"

echo "V3 stress: OK"

python3 "$ROOT/paper_live_runner_v2.py" --skip-update --lot 0.01 > "$RUNNER_OUT"
cat "$RUNNER_OUT"
grep -q "Strategy: $CFG_NAME" "$RUNNER_OUT"

echo "Paper runner: OK"

ISAAC_PARENT_AUDIT_V2=1 python3 "$ROOT/daily_report_v1.py" > "$DAILY_OUT"
cat "$DAILY_OUT"
grep -q "Active strategy: $CFG_NAME" "$DAILY_OUT"

echo "Daily report: OK"
echo "SYSTEM STATUS: GREEN"
