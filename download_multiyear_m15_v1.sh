#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/sami/quant-fx"
OUT_DIR="$ROOT/data/dukascopy_chunks"
CACHE_DIR="$ROOT/.dukascopy-cache"

mkdir -p "$OUT_DIR" "$CACHE_DIR"

chunks=(
  "2021-01-01 2021-04-01"
  "2021-04-01 2021-07-01"
  "2021-07-01 2021-10-01"
  "2021-10-01 2022-01-01"

  "2022-01-01 2022-04-01"
  "2022-04-01 2022-07-01"
  "2022-07-01 2022-10-01"
  "2022-10-01 2023-01-01"

  "2023-01-01 2023-04-01"
  "2023-04-01 2023-07-01"
  "2023-07-01 2023-10-01"
  "2023-10-01 2024-01-01"

  "2024-01-01 2024-04-01"
  "2024-04-01 2024-07-01"
  "2024-07-01 2024-10-01"
  "2024-10-01 2025-01-01"
)

echo "=== Isaac Multi-Year EUR/USD M15 Downloader V1 ==="

for chunk in "${chunks[@]}"; do
  FROM="$(echo "$chunk" | awk '{print $1}')"
  TO="$(echo "$chunk" | awk '{print $2}')"
  EXPECTED="$OUT_DIR/eurusd-m15-bid-$FROM-$TO.csv"

  if [[ -f "$EXPECTED" ]]; then
    LINES="$(wc -l < "$EXPECTED")"
    if [[ "$LINES" -gt 100 ]]; then
      echo "SKIP existing: $EXPECTED ($LINES lines)"
      continue
    fi
  fi

  echo "DOWNLOAD: $FROM to $TO"

  npx dukascopy-node@1.46.4 \
    -i eurusd \
    -from "$FROM" \
    -to "$TO" \
    -t m15 \
    -f csv \
    -dir "$OUT_DIR" \
    -bs 2 \
    -bp 2000 \
    -ch \
    -chpath "$CACHE_DIR" \
    -r 8 \
    -rp 1500
done

echo "DONE downloading chunks."
find "$OUT_DIR" -type f -iname "*.csv" | sort
