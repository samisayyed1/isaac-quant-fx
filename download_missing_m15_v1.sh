#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="$ROOT/data/dukascopy_chunks"
CACHE_DIR="$ROOT/.dukascopy-cache"

mkdir -p "$OUT_DIR" "$CACHE_DIR"

chunks=(
  "2022-10-01 2022-11-01"
  "2022-11-01 2022-12-01"
  "2022-12-01 2023-01-01"

  "2023-01-01 2023-02-01"
  "2023-02-01 2023-03-01"
  "2023-03-01 2023-04-01"
  "2023-04-01 2023-05-01"
  "2023-05-01 2023-06-01"
  "2023-06-01 2023-07-01"
  "2023-07-01 2023-08-01"
  "2023-08-01 2023-09-01"
  "2023-09-01 2023-10-01"
  "2023-10-01 2023-11-01"
  "2023-11-01 2023-12-01"
  "2023-12-01 2024-01-01"

  "2024-01-01 2024-02-01"
  "2024-02-01 2024-03-01"
  "2024-03-01 2024-04-01"
  "2024-04-01 2024-05-01"
  "2024-05-01 2024-06-01"
  "2024-06-01 2024-07-01"
  "2024-07-01 2024-08-01"
  "2024-08-01 2024-09-01"
  "2024-09-01 2024-10-01"
  "2024-10-01 2024-11-01"
  "2024-11-01 2024-12-01"
  "2024-12-01 2025-01-01"
)

echo "=== Isaac Missing Multi-Year Downloader V1 ==="

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
    -bs 1 \
    -bp 2500 \
    -ch \
    -chpath "$CACHE_DIR" \
    -r 10 \
    -rp 2000

  sleep 2
done

echo "DONE missing chunks."
