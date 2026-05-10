from __future__ import annotations

import csv
import random
from pathlib import Path
from statistics import median
from typing import List

BASE_COST = 1.2
TRADES_PATH = Path("/home/sami/quant-fx/data/combined/multiyear_replay_trades.csv")


def max_dd(vals: List[float]) -> float:
    eq = 0.0
    peak = 0.0
    worst = 0.0

    for v in vals:
        eq += v
        peak = max(peak, eq)
        worst = min(worst, eq - peak)

    return worst


def profit_factor(vals: List[float]) -> float:
    wins = sum(v for v in vals if v > 0)
    losses = abs(sum(v for v in vals if v < 0))
    return wins / losses if losses else 999.0


def load_values() -> List[float]:
    if not TRADES_PATH.exists():
        raise SystemExit(f"Missing trades file: {TRADES_PATH}")

    vals: List[float] = []

    with TRADES_PATH.open() as f:
        for row in csv.DictReader(f):
            vals.append(float(row["net_pips"]))

    if not vals:
        raise SystemExit("No trade values loaded.")

    return vals


def main() -> None:
    vals = load_values()

    print("=== Multi-Year Cost Stress ===")
    gross = [v + BASE_COST for v in vals]

    for cost in [1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]:
        stressed = [g - cost for g in gross]
        wins = [v for v in stressed if v > 0]

        print(
            f"cost={cost:.1f} | "
            f"total={sum(stressed):.2f} | "
            f"avg={sum(stressed) / len(stressed):.2f} | "
            f"win_rate={len(wins) / len(stressed) * 100:.2f}% | "
            f"pf={profit_factor(stressed):.2f} | "
            f"dd={max_dd(stressed):.2f}"
        )

    print("")
    print("=== Multi-Year Monte Carlo ===")

    rng = random.Random(42)
    dds: List[float] = []
    totals: List[float] = []

    for _ in range(10_000):
        sample = vals[:]
        rng.shuffle(sample)
        totals.append(sum(sample))
        dds.append(max_dd(sample))

    dds = sorted(dds)

    print(f"median_total={median(totals):.2f}")
    print(f"median_dd={median(dds):.2f}")
    print(f"dd_5pct_worst={dds[int(len(dds) * 0.05)]:.2f}")
    print(f"dd_1pct_worst={dds[int(len(dds) * 0.01)]:.2f}")
    print(f"dd_0_1pct_worst={dds[int(len(dds) * 0.001)]:.2f}")


if __name__ == "__main__":
    main()
