from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional

DATA_PATH = Path("/home/sami/download/eurusd-m15-bid-2025-01-01-2026-01-01.csv")
TRADES_PATH = Path("/home/sami/quant-fx/trades_asia_breakout.csv")

PIP = 0.0001

ASIA_START_HOUR = 0
ASIA_END_HOUR = 6          # 00:00-05:45 UTC
BREAKOUT_START_HOUR = 7
BREAKOUT_END_HOUR = 16     # forced flat by 16:00 UTC

MIN_ASIA_RANGE_PIPS = 8.0
MAX_ASIA_RANGE_PIPS = 35.0
BREAKOUT_BUFFER_PIPS = 1.0
TAKE_PROFIT_R = 1.5

ROUND_TRIP_COST_PIPS = 1.2  # conservative: spread + slippage


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
    side: str
    entry_time: str
    exit_time: str
    entry: float
    exit: float
    stop: float
    target: float
    gross_pips: float
    net_pips: float
    r_multiple: float
    reason: str


def load_candles(path: Path) -> List[Candle]:
    candles: List[Candle] = []

    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        required = {"timestamp", "open", "high", "low", "close"}
        if not required.issubset(reader.fieldnames or set()):
            raise ValueError(f"CSV missing required columns: {required}")

        for row in reader:
            ts = datetime.fromtimestamp(int(row["timestamp"]) / 1000, tz=timezone.utc)
            candles.append(
                Candle(
                    ts=ts,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                )
            )

    candles.sort(key=lambda c: c.ts)
    return candles


def group_by_day(candles: List[Candle]) -> Dict[str, List[Candle]]:
    grouped: Dict[str, List[Candle]] = {}
    for c in candles:
        grouped.setdefault(c.ts.date().isoformat(), []).append(c)
    return grouped


def pips(value: float) -> float:
    return value / PIP


def backtest(candles: List[Candle]) -> List[Trade]:
    trades: List[Trade] = []
    grouped = group_by_day(candles)

    for day, day_candles in grouped.items():
        asia = [
            c for c in day_candles
            if ASIA_START_HOUR <= c.ts.hour < ASIA_END_HOUR
        ]

        breakout = [
            c for c in day_candles
            if BREAKOUT_START_HOUR <= c.ts.hour < BREAKOUT_END_HOUR
        ]

        if len(asia) < 20 or len(breakout) < 20:
            continue

        asia_high = max(c.high for c in asia)
        asia_low = min(c.low for c in asia)
        asia_range = asia_high - asia_low
        asia_range_pips = pips(asia_range)

        if not (MIN_ASIA_RANGE_PIPS <= asia_range_pips <= MAX_ASIA_RANGE_PIPS):
            continue

        long_entry = asia_high + BREAKOUT_BUFFER_PIPS * PIP
        short_entry = asia_low - BREAKOUT_BUFFER_PIPS * PIP

        traded = False

        for i, c in enumerate(breakout):
            long_break = c.high >= long_entry
            short_break = c.low <= short_entry

            if long_break and short_break:
                # Ambiguous candle. Institutional-grade backtest rejects it.
                continue

            if long_break:
                entry = long_entry
                stop = asia_low - BREAKOUT_BUFFER_PIPS * PIP
                risk = entry - stop
                target = entry + TAKE_PROFIT_R * risk
                side = "LONG"
                traded = True
            elif short_break:
                entry = short_entry
                stop = asia_high + BREAKOUT_BUFFER_PIPS * PIP
                risk = stop - entry
                target = entry - TAKE_PROFIT_R * risk
                side = "SHORT"
                traded = True
            else:
                continue

            exit_price: Optional[float] = None
            exit_time: Optional[datetime] = None
            reason = "TIME_EXIT"

            for future in breakout[i:]:
                if side == "LONG":
                    hit_stop = future.low <= stop
                    hit_target = future.high >= target

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
                    hit_stop = future.high >= stop
                    hit_target = future.low <= target

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
                    exit_time = future.ts
                    break

            if exit_price is None:
                final = breakout[-1]
                exit_price = final.close
                exit_time = final.ts

            gross = pips(exit_price - entry) if side == "LONG" else pips(entry - exit_price)
            net = gross - ROUND_TRIP_COST_PIPS
            r_multiple = net / pips(risk)

            trades.append(
                Trade(
                    day=day,
                    side=side,
                    entry_time=c.ts.isoformat(),
                    exit_time=exit_time.isoformat(),
                    entry=entry,
                    exit=exit_price,
                    stop=stop,
                    target=target,
                    gross_pips=gross,
                    net_pips=net,
                    r_multiple=r_multiple,
                    reason=reason,
                )
            )
            break

        if traded:
            continue

    return trades


def max_drawdown(values: List[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_dd = 0.0

    for v in values:
        equity += v
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)

    return max_dd


def profit_factor(values: List[float]) -> float:
    wins = sum(v for v in values if v > 0)
    losses = abs(sum(v for v in values if v < 0))

    if losses == 0:
        return float("inf") if wins > 0 else 0.0

    return wins / losses


def write_trades(trades: List[Trade], path: Path) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(Trade.__dataclass_fields__.keys()))
        writer.writeheader()
        for t in trades:
            writer.writerow(t.__dict__)


def main() -> None:
    candles = load_candles(DATA_PATH)
    trades = backtest(candles)
    write_trades(trades, TRADES_PATH)

    net = [t.net_pips for t in trades]
    wins = [v for v in net if v > 0]
    losses = [v for v in net if v <= 0]

    print("=== EUR/USD M15 Asia Compression Breakout Backtest v1 ===")
    print(f"Candles: {len(candles)}")
    print(f"Trades: {len(trades)}")
    print(f"Wins: {len(wins)}")
    print(f"Losses: {len(losses)}")
    print(f"Win rate: {(len(wins) / len(trades) * 100) if trades else 0:.2f}%")
    print(f"Total net pips: {sum(net) if net else 0:.2f}")
    print(f"Average net pips/trade: {mean(net) if net else 0:.2f}")
    print(f"Profit factor: {profit_factor(net):.2f}")
    print(f"Max drawdown pips: {max_drawdown(net):.2f}")
    print(f"Best trade pips: {max(net) if net else 0:.2f}")
    print(f"Worst trade pips: {min(net) if net else 0:.2f}")
    print(f"Trades file: {TRADES_PATH}")


if __name__ == "__main__":
    main()
