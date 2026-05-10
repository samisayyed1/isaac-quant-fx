from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path("/home/sami/quant-fx")
CHUNK_DIR = ROOT / "data" / "dukascopy_chunks"
OUT = ROOT / "data" / "combined" / "eurusd-m15-bid-2021-01-01-2026-01-01.csv"
EXISTING_2025 = Path("/home/sami/download/eurusd-m15-bid-2025-01-01-2026-01-01.csv")

OUT.parent.mkdir(parents=True, exist_ok=True)

files = sorted(CHUNK_DIR.glob("eurusd-m15-bid-*.csv"))

if EXISTING_2025.exists():
    files.append(EXISTING_2025)

seen: set[int] = set()
rows: list[dict[str, str]] = []

for file in files:
    with file.open() as f:
        reader = csv.DictReader(f)
        required = {"timestamp", "open", "high", "low", "close"}

        if not required.issubset(set(reader.fieldnames or [])):
            print(f"SKIP invalid file: {file}")
            continue

        for row in reader:
            ts = int(row["timestamp"])
            if ts in seen:
                continue

            seen.add(ts)
            rows.append({
                "timestamp": str(ts),
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
            })

rows.sort(key=lambda r: int(r["timestamp"]))

with OUT.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["timestamp", "open", "high", "low", "close"])
    writer.writeheader()
    writer.writerows(rows)

print("=== Combined Multi-Year Dataset ===")
print(f"Files used: {len(files)}")
print(f"Rows: {len(rows)}")
print(f"Output: {OUT}")

if rows:
    print(f"First timestamp: {rows[0]['timestamp']}")
    print(f"Last timestamp: {rows[-1]['timestamp']}")
