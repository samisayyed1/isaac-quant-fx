#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="$ROOT/live_data/raw"
CACHE_DIR="$ROOT/.dukascopy-cache"
LIVE_FILE="$ROOT/live_data/eurusd-m15-live.csv"

mkdir -p "$OUT_DIR" "$CACHE_DIR"

START_DATE="$(date -u -d '14 days ago' +%F)"
END_DATE="$(date -u -d 'tomorrow' +%F)"

echo "=== Isaac Live Data Update V1 ==="
echo "Pair: EUR/USD"
echo "Timeframe: M15"
echo "From: $START_DATE"
echo "To: $END_DATE"

npx dukascopy-node@1.46.4 \
  -i eurusd \
  -from "$START_DATE" \
  -to "$END_DATE" \
  -t m15 \
  -f csv \
  -dir "$OUT_DIR" \
  -bs 2 \
  -bp 1500 \
  -ch \
  -chpath "$CACHE_DIR" \
  -r 5 \
  -rp 1000

LATEST_FILE="$(find "$OUT_DIR" -type f -iname "*.csv" -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-)"

if [[ -z "$LATEST_FILE" ]]; then
  echo "FAIL: no CSV downloaded"
  exit 1
fi

cp "$LATEST_FILE" "$LIVE_FILE"

echo "Live file updated: $LIVE_FILE"
wc -l "$LIVE_FILE"
tail -n 3 "$LIVE_FILE"
