from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

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


def print_group(name: str, groups: Dict[str, List[float]]) -> None:
    print(f"\n=== {name} ===")
    rows = []

    for key, vals in groups.items():
        wins = [v for v in vals if v > 0]
        rows.append((
            key,
            len(vals),
            sum(vals),
            sum(vals) / len(vals),
            len(wins) / len(vals) * 100,
            pf(vals),
            max_dd(vals),
        ))

    rows.sort(key=lambda x: x[2])

    for key, trades, net, avg, win_rate, profit_factor, dd in rows:
        print(
            f"{key}: trades={trades} "
            f"net={net:.2f} "
            f"avg={avg:.2f} "
            f"win_rate={win_rate:.2f}% "
            f"pf={profit_factor:.2f} "
            f"dd={dd:.2f}"
        )


def losing_streak(vals: List[float]) -> int:
    worst = 0
    current = 0

    for v in vals:
        if v <= 0:
            current += 1
            worst = max(worst, current)
        else:
            current = 0

    return worst


def rolling_windows(vals: List[float], size: int) -> None:
    if len(vals) < size:
        return

    windows = []
    for i in range(0, len(vals) - size + 1):
        chunk = vals[i:i + size]
        windows.append((i, sum(chunk), max_dd(chunk), pf(chunk)))

    windows.sort(key=lambda x: x[1])

    print(f"\n=== WORST ROLLING {size}-TRADE WINDOWS ===")
    for i, total, dd, profit_factor in windows[:10]:
        print(f"start_trade_index={i} total={total:.2f} dd={dd:.2f} pf={profit_factor:.2f}")


def main() -> None:
    if not TRADES.exists():
        raise SystemExit(f"Missing trades file: {TRADES}")

    rows = []
    with TRADES.open() as f:
        for r in csv.DictReader(f):
            entry = datetime.fromisoformat(r["entry_time"])
            net = float(r["net_pips"])

            rows.append({
                "net": net,
                "year": r["year"],
                "month": r["month"],
                "month_num": entry.strftime("%m"),
                "weekday": entry.strftime("%A"),
                "entry_hour": str(entry.hour),
                "side": r["side"],
                "reason": r["reason"],
                "year_side": f"{r['year']}_{r['side']}",
                "year_weekday": f"{r['year']}_{entry.strftime('%A')}",
                "year_month_num": f"{r['year']}_{entry.strftime('%m')}",
            })

    vals = [r["net"] for r in rows]
    wins = [v for v in vals if v > 0]

    print("=== Isaac Regime Diagnostics V1 ===")
    print(f"Trades: {len(vals)}")
    print(f"Total net pips: {sum(vals):.2f}")
    print(f"Average pips/trade: {sum(vals) / len(vals):.2f}")
    print(f"Win rate: {len(wins) / len(vals) * 100:.2f}%")
    print(f"Profit factor: {pf(vals):.2f}")
    print(f"Max drawdown: {max_dd(vals):.2f}")
    print(f"Worst losing streak: {losing_streak(vals)} trades")

    for key in [
        "year",
        "month_num",
        "weekday",
        "entry_hour",
        "side",
        "reason",
        "year_side",
        "year_weekday",
        "year_month_num",
    ]:
        groups: Dict[str, List[float]] = defaultdict(list)
        for r in rows:
            groups[r[key]].append(r["net"])
        print_group(key.upper(), groups)

    rolling_windows(vals, 25)
    rolling_windows(vals, 50)
    rolling_windows(vals, 100)


if __name__ == "__main__":
    main()
