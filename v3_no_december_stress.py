from __future__ import annotations

import csv
import random
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import List

TRADES = Path("/home/sami/quant-fx/data/combined/multiyear_replay_trades.csv")
BASE_COST = 1.2


def max_dd(vals: List[float]) -> float:
    eq = peak = worst = 0.0
    for v in vals:
        eq += v
        peak = max(peak, eq)
        worst = min(worst, eq - peak)
    return worst


def pf(vals: List[float]) -> float:
    wins = sum(v for v in vals if v > 0)
    losses = abs(sum(v for v in vals if v < 0))
    return wins / losses if losses else 999.0


rows = []

with TRADES.open() as f:
    for r in csv.DictReader(f):
        entry = datetime.fromisoformat(r["entry_time"])
        if entry.strftime("%m") == "12":
            continue

        rows.append({
            "net": float(r["net_pips"]),
            "year": r["year"],
            "month": r["month"],
            "side": r["side"],
        })

vals = [r["net"] for r in rows]
wins = [v for v in vals if v > 0]

print("=== V3 No-December Stress ===")
print(f"Trades: {len(vals)}")
print(f"Total net pips: {sum(vals):.2f}")
print(f"Average pips/trade: {sum(vals) / len(vals):.2f}")
print(f"Win rate: {len(wins) / len(vals) * 100:.2f}%")
print(f"Profit factor: {pf(vals):.2f}")
print(f"Max drawdown: {max_dd(vals):.2f}")

print("\n=== Yearly ===")
yearly = defaultdict(list)
for r in rows:
    yearly[r["year"]].append(r["net"])

for y in sorted(yearly):
    yv = yearly[y]
    yw = [v for v in yv if v > 0]
    print(
        f"{y}: trades={len(yv)} "
        f"net={sum(yv):.2f} "
        f"avg={sum(yv)/len(yv):.2f} "
        f"win_rate={len(yw)/len(yv)*100:.2f}% "
        f"pf={pf(yv):.2f} "
        f"dd={max_dd(yv):.2f}"
    )

print("\n=== Cost Stress ===")
gross = [v + BASE_COST for v in vals]

for cost in [1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]:
    stressed = [g - cost for g in gross]
    sw = [v for v in stressed if v > 0]
    print(
        f"cost={cost:.1f} | "
        f"total={sum(stressed):.2f} | "
        f"avg={sum(stressed)/len(stressed):.2f} | "
        f"win_rate={len(sw)/len(stressed)*100:.2f}% | "
        f"pf={pf(stressed):.2f} | "
        f"dd={max_dd(stressed):.2f}"
    )

print("\n=== Monte Carlo ===")
rng = random.Random(42)
dds = []
totals = []

for _ in range(10000):
    sample = vals[:]
    rng.shuffle(sample)
    totals.append(sum(sample))
    dds.append(max_dd(sample))

dds.sort()

print(f"median_total={median(totals):.2f}")
print(f"median_dd={median(dds):.2f}")
print(f"dd_5pct_worst={dds[int(len(dds)*0.05)]:.2f}")
print(f"dd_1pct_worst={dds[int(len(dds)*0.01)]:.2f}")
print(f"dd_0_1pct_worst={dds[int(len(dds)*0.001)]:.2f}")
