from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional

DATA_PATH = Path("/home/sami/download/eurusd-m15-bid-2025-01-01-2026-01-01.csv")
OUT_PATH = Path("/home/sami/quant-fx/optimization_results.csv")

PIP = 0.0001
ROUND_TRIP_COST_PIPS = 1.2


@dataclass(frozen=True)
class Candle:
    ts: datetime
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class Params:
    asia_end: int
    breakout_start: int
    breakout_end: int
    min_range: float
    max_range: float
    buffer: float
    tp_r: float


def load_candles(path: Path) -> List[Candle]:
    candles: List[Candle] = []
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            candles.append(
                Candle(
                    ts=datetime.fromtimestamp(int(row["timestamp"]) / 1000, tz=timezone.utc),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                )
            )
    candles.sort(key=lambda c: c.ts)
    return candles


def group_by_day(candles: List[Candle]) -> Dict[str, List[Candle]]:
    out: Dict[str, List[Candle]] = {}
    for c in candles:
        out.setdefault(c.ts.date().isoformat(), []).append(c)
    return out


def pips(x: float) -> float:
    return x / PIP


def max_drawdown(values: List[float]) -> float:
    equity = 0.0
    peak = 0.0
    worst = 0.0
    for v in values:
        equity += v
        peak = max(peak, equity)
        worst = min(worst, equity - peak)
    return worst


def profit_factor(values: List[float]) -> float:
    gross_win = sum(v for v in values if v > 0)
    gross_loss = abs(sum(v for v in values if v < 0))
    if gross_loss == 0:
        return 999.0 if gross_win > 0 else 0.0
    return gross_win / gross_loss


def run_backtest(candles: List[Candle], params: Params) -> List[float]:
    results: List[float] = []
    grouped = group_by_day(candles)

    for _, day_candles in grouped.items():
        asia = [c for c in day_candles if 0 <= c.ts.hour < params.asia_end]
        breakout = [c for c in day_candles if params.breakout_start <= c.ts.hour < params.breakout_end]

        if len(asia) < 16 or len(breakout) < 16:
            continue

        asia_high = max(c.high for c in asia)
        asia_low = min(c.low for c in asia)
        asia_range = asia_high - asia_low
        asia_range_pips = pips(asia_range)

        if not (params.min_range <= asia_range_pips <= params.max_range):
            continue

        long_entry = asia_high + params.buffer * PIP
        short_entry = asia_low - params.buffer * PIP

        for i, c in enumerate(breakout):
            long_break = c.high >= long_entry
            short_break = c.low <= short_entry

            if long_break and short_break:
                continue

            if long_break:
                side = "LONG"
                entry = long_entry
                stop = asia_low - params.buffer * PIP
                risk = entry - stop
                target = entry + params.tp_r * risk
            elif short_break:
                side = "SHORT"
                entry = short_entry
                stop = asia_high + params.buffer * PIP
                risk = stop - entry
                target = entry - params.tp_r * risk
            else:
                continue

            exit_price: Optional[float] = None

            for future in breakout[i:]:
                if side == "LONG":
                    hit_stop = future.low <= stop
                    hit_target = future.high >= target
                    if hit_stop and hit_target:
                        exit_price = stop
                    elif hit_stop:
                        exit_price = stop
                    elif hit_target:
                        exit_price = target
                else:
                    hit_stop = future.high >= stop
                    hit_target = future.low <= target
                    if hit_stop and hit_target:
                        exit_price = stop
                    elif hit_stop:
                        exit_price = stop
                    elif hit_target:
                        exit_price = target

                if exit_price is not None:
                    break

            if exit_price is None:
                exit_price = breakout[-1].close

            gross = pips(exit_price - entry) if side == "LONG" else pips(entry - exit_price)
            results.append(gross - ROUND_TRIP_COST_PIPS)
            break

    return results


def main() -> None:
    candles = load_candles(DATA_PATH)

    grid = product(
        [5, 6, 7],
        [6, 7, 8],
        [14, 15, 16, 17],
        [6.0, 8.0, 10.0, 12.0],
        [25.0, 30.0, 35.0, 40.0],
        [0.5, 1.0, 1.5],
        [1.0, 1.25, 1.5, 1.75, 2.0],
    )

    rows = []

    for combo in grid:
        p = Params(*combo)

        if p.breakout_start < p.asia_end:
            continue

        values = run_backtest(candles, p)

        if len(values) < 80:
            continue

        total = sum(values)
        dd = max_drawdown(values)
        pf = profit_factor(values)
        win_rate = len([v for v in values if v > 0]) / len(values) * 100
        avg = mean(values)

        score = (total / abs(dd)) * pf if dd < 0 else 0.0

        rows.append({
            "score": round(score, 4),
            "total_pips": round(total, 2),
            "trades": len(values),
            "win_rate": round(win_rate, 2),
            "profit_factor": round(pf, 2),
            "max_drawdown": round(dd, 2),
            "avg_pips": round(avg, 2),
            "asia_end": p.asia_end,
            "breakout_start": p.breakout_start,
            "breakout_end": p.breakout_end,
            "min_range": p.min_range,
            "max_range": p.max_range,
            "buffer": p.buffer,
            "tp_r": p.tp_r,
        })

    rows.sort(key=lambda r: (r["score"], r["profit_factor"], r["total_pips"]), reverse=True)

    with OUT_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print("=== Top 20 Parameter Sets ===")
    for r in rows[:20]:
        print(r)

    print(f"\nSaved: {OUT_PATH}")
    print(f"Tested valid configs: {len(rows)}")


if __name__ == "__main__":
    main()
