from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Callable, List

TRADES = Path("/home/sami/quant-fx/data/combined/multiyear_replay_trades.csv")


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
        rows.append({
            "net": float(r["net_pips"]),
            "year": r["year"],
            "month_num": entry.strftime("%m"),
            "weekday": entry.strftime("%A"),
            "hour": entry.hour,
            "side": r["side"],
        })


tests: dict[str, Callable[[dict], bool]] = {
    "base": lambda r: True,
    "no_december": lambda r: r["month_num"] != "12",
    "hour_8_only": lambda r: r["hour"] == 8,
    "no_december_hour_8_only": lambda r: r["month_num"] != "12" and r["hour"] == 8,
    "no_mon_tue": lambda r: r["weekday"] not in {"Monday", "Tuesday"},
    "wed_thu_only": lambda r: r["weekday"] in {"Wednesday", "Thursday"},
    "thu_only": lambda r: r["weekday"] == "Thursday",
    "no_december_wed_thu": lambda r: r["month_num"] != "12" and r["weekday"] in {"Wednesday", "Thursday"},
    "no_december_no_mon_tue": lambda r: r["month_num"] != "12" and r["weekday"] not in {"Monday", "Tuesday"},
    "no_december_hour8_wedthu": lambda r: r["month_num"] != "12" and r["hour"] == 8 and r["weekday"] in {"Wednesday", "Thursday"},
}


print("=== Isaac Filter Trials V1 ===")

for name, rule in tests.items():
    vals = [r["net"] for r in rows if rule(r)]
    if not vals:
        continue

    wins = [v for v in vals if v > 0]

    print(
        f"{name}: "
        f"trades={len(vals)} "
        f"total={sum(vals):.2f} "
        f"avg={sum(vals) / len(vals):.2f} "
        f"win_rate={len(wins) / len(vals) * 100:.2f}% "
        f"pf={pf(vals):.2f} "
        f"dd={max_dd(vals):.2f}"
    )
