from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional

DATA_PATH = Path("/home/sami/quant-fx/data/combined/eurusd-m15-bid-2021-01-01-2026-01-01.csv")
OUT_PATH = Path("/home/sami/quant-fx/data/combined/multiyear_replay_trades.csv")

PIP = 0.0001
ROUND_TRIP_COST_PIPS = 1.2

ASIA_END = 6
ENTRY_HOURS = {8, 9}
EXIT_HOUR = 14
MIN_RANGE_PIPS = 12.0
MAX_RANGE_PIPS = 30.0
BUFFER_PIPS = 1.0
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
    year: str
    month: str
    side: str
    entry_time: str
    exit_time: str
    entry: float
    stop: float
    target: float
    exit: float
    net_pips: float
    reason: str


def load_candles() -> List[Candle]:
    candles: List[Candle] = []

    with DATA_PATH.open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            candles.append(
                Candle(
                    ts=datetime.fromtimestamp(int(r["timestamp"]) / 1000, tz=timezone.utc),
                    open=float(r["open"]),
                    high=float(r["high"]),
                    low=float(r["low"]),
                    close=float(r["close"]),
                )
            )

    return sorted(candles, key=lambda c: c.ts)


def pips(x: float) -> float:
    return x / PIP


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


def replay(candles: List[Candle]) -> List[Trade]:
    by_day: Dict[str, List[Candle]] = defaultdict(list)
    for c in candles:
        by_day[c.ts.date().isoformat()].append(c)

    trades: List[Trade] = []

    for day, cs in sorted(by_day.items()):
        weekday = cs[0].ts.strftime("%A")
        if weekday == "Friday":
            continue

        asia = [c for c in cs if 0 <= c.ts.hour < ASIA_END]
        entry_window = [c for c in cs if c.ts.hour in ENTRY_HOURS]

        if len(asia) < 16 or not entry_window:
            continue

        asia_high = max(c.high for c in asia)
        asia_low = min(c.low for c in asia)
        asia_range = pips(asia_high - asia_low)

        if not (MIN_RANGE_PIPS <= asia_range <= MAX_RANGE_PIPS):
            continue

        long_entry = asia_high + BUFFER_PIPS * PIP
        short_entry = asia_low - BUFFER_PIPS * PIP
        long_stop = asia_low - BUFFER_PIPS * PIP
        short_stop = asia_high + BUFFER_PIPS * PIP
        long_target = long_entry + TP_R * (long_entry - long_stop)
        short_target = short_entry - TP_R * (short_stop - short_entry)

        for c in entry_window:
            long_trigger = c.high >= long_entry
            short_trigger = c.low <= short_entry

            if long_trigger and short_trigger:
                continue

            if long_trigger:
                side = "LONG"
                entry = long_entry
                stop = long_stop
                target = long_target
            elif short_trigger:
                side = "SHORT"
                entry = short_entry
                stop = short_stop
                target = short_target
            else:
                continue

            future = [x for x in cs if c.ts <= x.ts and x.ts.hour < EXIT_HOUR]

            exit_price: Optional[float] = None
            exit_time: Optional[datetime] = None
            reason = "TIME_EXIT"

            for f in future:
                if side == "LONG":
                    hit_stop = f.low <= stop
                    hit_target = f.high >= target

                    if hit_stop and hit_target:
                        exit_price = stop
                        reason = "STOP_AMBIGUOUS"
                    elif hit_stop:
                        exit_price = stop
                        reason = "STOP"
                    elif hit_target:
                        exit_price = target
                        reason = "TARGET"
                else:
                    hit_stop = f.high >= stop
                    hit_target = f.low <= target

                    if hit_stop and hit_target:
                        exit_price = stop
                        reason = "STOP_AMBIGUOUS"
                    elif hit_stop:
                        exit_price = stop
                        reason = "STOP"
                    elif hit_target:
                        exit_price = target
                        reason = "TARGET"

                if exit_price is not None:
                    exit_time = f.ts
                    break

            if exit_price is None:
                final = future[-1]
                exit_price = final.close
                exit_time = final.ts
                reason = "TIME_EXIT"

            gross = pips(exit_price - entry) if side == "LONG" else pips(entry - exit_price)
            net = gross - ROUND_TRIP_COST_PIPS

            trades.append(
                Trade(
                    day=day,
                    year=day[:4],
                    month=day[:7],
                    side=side,
                    entry_time=c.ts.isoformat(),
                    exit_time=exit_time.isoformat(),
                    entry=entry,
                    stop=stop,
                    target=target,
                    exit=exit_price,
                    net_pips=net,
                    reason=reason,
                )
            )
            break

    return trades


def print_group(name: str, groups: Dict[str, List[float]]) -> None:
    print(f"\n=== {name} ===")
    for key in sorted(groups):
        vals = groups[key]
        wins = [v for v in vals if v > 0]
        print(
            f"{key}: trades={len(vals)} "
            f"net={sum(vals):.2f} "
            f"avg={sum(vals) / len(vals):.2f} "
            f"win_rate={len(wins) / len(vals) * 100:.2f}% "
            f"pf={pf(vals):.2f} "
            f"dd={max_dd(vals):.2f}"
        )


def main() -> None:
    candles = load_candles()
    trades = replay(candles)
    vals = [t.net_pips for t in trades]
    wins = [v for v in vals if v > 0]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(Trade.__dataclass_fields__.keys()))
        writer.writeheader()
        for t in trades:
            writer.writerow(t.__dict__)

    print("=== Isaac Multi-Year Replay V1 ===")
    print(f"Candles: {len(candles)}")
    print(f"Trades: {len(trades)}")
    print(f"Total net pips: {sum(vals):.2f}")
    print(f"Average pips/trade: {mean(vals):.2f}")
    print(f"Win rate: {len(wins) / len(vals) * 100:.2f}%")
    print(f"Profit factor: {pf(vals):.2f}")
    print(f"Max drawdown: {max_dd(vals):.2f}")
    print(f"Best trade: {max(vals):.2f}")
    print(f"Worst trade: {min(vals):.2f}")
    print(f"Saved: {OUT_PATH}")

    yearly: Dict[str, List[float]] = defaultdict(list)
    monthly: Dict[str, List[float]] = defaultdict(list)
    side: Dict[str, List[float]] = defaultdict(list)
    reason: Dict[str, List[float]] = defaultdict(list)

    for t in trades:
        yearly[t.year].append(t.net_pips)
        monthly[t.month].append(t.net_pips)
        side[t.side].append(t.net_pips)
        reason[t.reason].append(t.net_pips)

    print_group("YEARLY", yearly)
    print_group("SIDE", side)
    print_group("EXIT_REASON", reason)


if __name__ == "__main__":
    main()
