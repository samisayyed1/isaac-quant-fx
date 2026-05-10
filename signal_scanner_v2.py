from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from strategy_config_v1 import OPERATIONAL_STRATEGY as CFG

DATA_PATH = Path("/home/sami/download/eurusd-m15-bid-2025-01-01-2026-01-01.csv")


@dataclass(frozen=True)
class Candle:
    ts: datetime
    open: float
    high: float
    low: float
    close: float


def load_candles(path: Path) -> List[Candle]:
    out: List[Candle] = []
    with path.open() as f:
        for r in csv.DictReader(f):
            out.append(Candle(
                ts=datetime.fromtimestamp(int(r["timestamp"]) / 1000, tz=timezone.utc),
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
            ))
    return sorted(out, key=lambda c: c.ts)


def parse_at(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def pips(x: float) -> float:
    return x / CFG.pip_size


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--at", help="Replay timestamp, e.g. 2025-09-03T08:15:00Z")
    args = parser.parse_args()

    all_candles = load_candles(DATA_PATH)
    at = parse_at(args.at)

    candles = [c for c in all_candles if at is None or c.ts <= at]
    if not candles:
        raise SystemExit("No candles available before --at timestamp")

    latest = candles[-1]
    day = latest.ts.date()

    today = [c for c in candles if c.ts.date() == day]
    asia = [c for c in today if CFG.asia_start_hour <= c.ts.hour < CFG.asia_end_hour]
    entry_window_so_far = [c for c in today if c.ts.hour in CFG.entry_hours]

    print("=== Isaac Signal Scanner V2 ===")
    print(f"Strategy: {CFG.name}")
    print(f"As-of UTC: {latest.ts.isoformat()}")
    print(f"Latest close: {latest.close:.5f}")

    if CFG.skip_friday and latest.ts.strftime("%A") == "Friday":
        print("SIGNAL: SKIP_FRIDAY")
        return

    if CFG.skip_december and latest.ts.month == 12:
        print("SIGNAL: SKIP_DECEMBER")
        return

    if latest.ts.hour not in CFG.entry_hours:
        print("SIGNAL: OUTSIDE_WINDOW")
        return

    if len(asia) < 16:
        print("SIGNAL: ASIA_RANGE_INCOMPLETE")
        return

    asia_high = max(c.high for c in asia)
    asia_low = min(c.low for c in asia)
    asia_range = pips(asia_high - asia_low)

    print(f"Asian high: {asia_high:.5f}")
    print(f"Asian low: {asia_low:.5f}")
    print(f"Asian range: {asia_range:.2f} pips")

    if not (CFG.min_asia_range_pips <= asia_range <= CFG.max_asia_range_pips):
        print("SIGNAL: INVALID_ASIA_RANGE")
        return

    long_entry = asia_high + CFG.buffer_pips * CFG.pip_size
    short_entry = asia_low - CFG.buffer_pips * CFG.pip_size
    long_stop = asia_low - CFG.buffer_pips * CFG.pip_size
    short_stop = asia_high + CFG.buffer_pips * CFG.pip_size
    long_target = long_entry + CFG.target_r * (long_entry - long_stop)
    short_target = short_entry - CFG.target_r * (short_stop - short_entry)

    long_triggered = any(c.high >= long_entry for c in entry_window_so_far)
    short_triggered = any(c.low <= short_entry for c in entry_window_so_far)

    print(f"Long entry: {long_entry:.5f}")
    print(f"Long stop: {long_stop:.5f}")
    print(f"Long target: {long_target:.5f}")
    print(f"Short entry: {short_entry:.5f}")
    print(f"Short stop: {short_stop:.5f}")
    print(f"Short target: {short_target:.5f}")

    if long_triggered and short_triggered:
        print("SIGNAL: AMBIGUOUS_BOTH_SIDES_TRIGGERED")
    elif long_triggered:
        print("SIGNAL: LONG_TRIGGERED")
    elif short_triggered:
        print("SIGNAL: SHORT_TRIGGERED")
    else:
        print("SIGNAL: NO_TRADE_YET")


if __name__ == "__main__":
    main()
