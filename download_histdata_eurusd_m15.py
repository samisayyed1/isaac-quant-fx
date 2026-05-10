from __future__ import annotations

import csv
import os
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List

from histdata import download_hist_data as dl
from histdata.api import Platform as P, TimeFrame as TF

BASE = Path("/home/sami/quant-fx/histdata_files")
RAW = BASE / "raw"
EXTRACTED = BASE / "extracted"
OUT = Path("/home/sami/download/eurusd-m15-histdata-2021-01-01-2026-01-01.csv")

RAW.mkdir(parents=True, exist_ok=True)
EXTRACTED.mkdir(parents=True, exist_ok=True)

for year in range(2021, 2026):
    print(f"Downloading EURUSD M1 {year}")
    try:
        dl(
            year=str(year),
            month=None,
            pair="eurusd",
            platform=P.META_TRADER,
            time_frame=TF.ONE_MINUTE,
            output_directory=str(RAW),
        )
    except Exception as e:
        print(f"Skipped {year}: {e}")

for z in RAW.rglob("*.zip"):
    target = EXTRACTED / z.stem
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(z) as archive:
        archive.extractall(target)

rows: List[tuple[datetime, float, float, float, float]] = []

for file in EXTRACTED.rglob("*"):
    if not file.is_file():
        continue
    if file.suffix.lower() not in {".csv", ".txt"}:
        continue

    with file.open("r", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = line.split(";")
            if len(parts) < 6:
                parts = line.split(",")

            try:
                if "." in parts[0] and len(parts) >= 6:
                    dt = datetime.strptime(parts[0] + " " + parts[1], "%Y.%m.%d %H:%M")
                    o, h, l, c = map(float, parts[2:6])
                else:
                    dt = datetime.strptime(parts[0], "%Y%m%d %H%M%S")
                    o, h, l, c = map(float, parts[1:5])

                dt_utc = dt.replace(tzinfo=timezone(timedelta(hours=-5))).astimezone(timezone.utc)
                rows.append((dt_utc, o, h, l, c))
            except Exception:
                continue

rows.sort(key=lambda x: x[0])

buckets: Dict[datetime, List[tuple[datetime, float, float, float, float]]] = {}

for r in rows:
    ts = r[0]
    bucket_minute = (ts.minute // 15) * 15
    bucket = ts.replace(minute=bucket_minute, second=0, microsecond=0)
    buckets.setdefault(bucket, []).append(r)

with OUT.open("w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "open", "high", "low", "close"])

    for ts in sorted(buckets):
        candles = buckets[ts]
        writer.writerow([
            int(ts.timestamp() * 1000),
            candles[0][1],
            max(x[2] for x in candles),
            min(x[3] for x in candles),
            candles[-1][4],
        ])

print(f"Done: {OUT}")
print(f"Raw M1 rows: {len(rows)}")
print(f"M15 candles: {len(buckets)}")
