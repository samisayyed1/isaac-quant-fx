from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Dict, List, Optional

DATA_PATH = Path("/home/sami/download/eurusd-m15-bid-2025-01-01-2026-01-01.csv")
OUT_TRADES = Path("/home/sami/quant-fx/candidate_trades.csv")

PIP = 0.0001
ROUND_TRIP_COST_PIPS = 1.2

ASIA_END = 6
BREAKOUT_START = 8
BREAKOUT_END = 14
MIN_RANGE = 12.0
MAX_RANGE = 30.0
BUFFER = 1.0
TP_R = 2.0


@dataclass(frozen=True)
class Candle:
    ts: datetime
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class Trade:
    day: str
    month: str
    side: str
    entry_time: str
    exit_time: str
    net_pips: float
    reason: str


def load_candles() -> List[Candle]:
    candles: List[Candle] = []
    with DATA_PATH.open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            candles.append(Candle(
                ts=datetime.fromtimestamp(int(r["timestamp"]) / 1000, tz=timezone.utc),
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
            ))
    return sorted(candles, key=lambda c: c.ts)


def pips(x: float) -> float:
    return x / PIP


def max_dd(values: List[float]) -> float:
    eq = 0.0
    peak = 0.0
    worst = 0.0
    for v in values:
        eq += v
        peak = max(peak, eq)
        worst = min(worst, eq - peak)
    return worst


def profit_factor(values: List[float]) -> float:
    wins = sum(v for v in values if v > 0)
    losses = abs(sum(v for v in values if v < 0))
    return wins / losses if losses else 999.0


def backtest(candles: List[Candle]) -> List[Trade]:
    by_day: Dict[str, List[Candle]] = {}
    for c in candles:
        by_day.setdefault(c.ts.date().isoformat(), []).append(c)

    trades: List[Trade] = []

    for day, cs in by_day.items():
        asia = [c for c in cs if 0 <= c.ts.hour < ASIA_END]
        window = [c for c in cs if BREAKOUT_START <= c.ts.hour < BREAKOUT_END]

        if len(asia) < 16 or len(window) < 16:
            continue

        hi = max(c.high for c in asia)
        lo = min(c.low for c in asia)
        rng = pips(hi - lo)

        if not (MIN_RANGE <= rng <= MAX_RANGE):
            continue

        long_entry = hi + BUFFER * PIP
        short_entry = lo - BUFFER * PIP

        for i, c in enumerate(window):
            long_break = c.high >= long_entry
            short_break = c.low <= short_entry

            if long_break and short_break:
                continue

            if long_break:
                side = "LONG"
                entry = long_entry
                stop = lo - BUFFER * PIP
                risk = entry - stop
                target = entry + TP_R * risk
            elif short_break:
                side = "SHORT"
                entry = short_entry
                stop = hi + BUFFER * PIP
                risk = stop - entry
                target = entry - TP_R * risk
            else:
                continue

            exit_price: Optional[float] = None
            exit_time: Optional[datetime] = None
            reason = "TIME_EXIT"

            for f in window[i:]:
                if side == "LONG":
                    hit_stop = f.low <= stop
                    hit_target = f.high >= target
                    if hit_stop:
                        exit_price = stop
                        exit_time = f.ts
                        reason = "STOP"
                    elif hit_target:
                        exit_price = target
                        exit_time = f.ts
                        reason = "TARGET"
                else:
                    hit_stop = f.high >= stop
                    hit_target = f.low <= target
                    if hit_stop:
                        exit_price = stop
                        exit_time = f.ts
                        reason = "STOP"
                    elif hit_target:
                        exit_price = target
                        exit_time = f.ts
                        reason = "TARGET"

                if exit_price is not None:
                    break

            if exit_price is None:
                exit_price = window[-1].close
                exit_time = window[-1].ts

            gross = pips(exit_price - entry) if side == "LONG" else pips(entry - exit_price)
            net = gross - ROUND_TRIP_COST_PIPS

            trades.append(Trade(
                day=day,
                month=day[:7],
                side=side,
                entry_time=c.ts.isoformat(),
                exit_time=exit_time.isoformat(),
                net_pips=net,
                reason=reason,
            ))
            break

    return trades


def monte_carlo(values: List[float], runs: int = 5000) -> Dict[str, float]:
    rng = random.Random(42)
    totals: List[float] = []
    dds: List[float] = []

    for _ in range(runs):
        sample = values[:]
        rng.shuffle(sample)
        totals.append(sum(sample))
        dds.append(max_dd(sample))

    dds_sorted = sorted(dds)

    return {
        "mc_total_median": median(totals),
        "mc_dd_median": median(dds),
        "mc_dd_5pct_worst": dds_sorted[int(len(dds_sorted) * 0.05)],
        "mc_dd_1pct_worst": dds_sorted[int(len(dds_sorted) * 0.01)],
    }


def main() -> None:
    trades = backtest(load_candles())
    values = [t.net_pips for t in trades]
    wins = [v for v in values if v > 0]
    losses = [v for v in values if v <= 0]

    with OUT_TRADES.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(Trade.__dataclass_fields__.keys()))
        writer.writeheader()
        for t in trades:
            writer.writerow(t.__dict__)

    print("=== Candidate Validation ===")
    print(f"Trades: {len(trades)}")
    print(f"Wins: {len(wins)}")
    print(f"Losses: {len(losses)}")
    print(f"Win rate: {len(wins) / len(trades) * 100:.2f}%")
    print(f"Total net pips: {sum(values):.2f}")
    print(f"Average pips/trade: {mean(values):.2f}")
    print(f"Profit factor: {profit_factor(values):.2f}")
    print(f"Max drawdown: {max_dd(values):.2f}")
    print(f"Best trade: {max(values):.2f}")
    print(f"Worst trade: {min(values):.2f}")

    print("\n=== Monthly PnL ===")
    monthly: Dict[str, List[float]] = {}
    for t in trades:
        monthly.setdefault(t.month, []).append(t.net_pips)

    for m in sorted(monthly):
        vals = monthly[m]
        print(f"{m}: trades={len(vals)} net={sum(vals):.2f} avg={mean(vals):.2f}")

    print("\n=== Side PnL ===")
    for side in ["LONG", "SHORT"]:
        vals = [t.net_pips for t in trades if t.side == side]
        print(f"{side}: trades={len(vals)} net={sum(vals):.2f} avg={mean(vals):.2f}")

    print("\n=== Exit Reason ===")
    for reason in ["TARGET", "STOP", "TIME_EXIT"]:
        vals = [t.net_pips for t in trades if t.reason == reason]
        if vals:
            print(f"{reason}: trades={len(vals)} net={sum(vals):.2f} avg={mean(vals):.2f}")

    print("\n=== Monte Carlo Shuffle Stress ===")
    mc = monte_carlo(values)
    for k, v in mc.items():
        print(f"{k}: {v:.2f}")

    print(f"\nTrades saved: {OUT_TRADES}")


if __name__ == "__main__":
    main()
