from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List

DATA_PATH = Path("/home/sami/download/eurusd-m15-bid-2025-01-01-2026-01-01.csv")

PIP = 0.0001

ASIA_END = 6
ENTRY_HOURS = {8, 9}
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


def load_candles(path: Path) -> List[Candle]:
    candles: List[Candle] = []
    with path.open() as f:
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


def main() -> None:
    candles = load_candles(DATA_PATH)
    latest = candles[-1]
    day = latest.ts.date()

    today = [c for c in candles if c.ts.date() == day]
    asia = [c for c in today if 0 <= c.ts.hour < ASIA_END]
    entry_window = [c for c in today if c.ts.hour in ENTRY_HOURS]

    print("=== Isaac Signal Scanner V1 ===")
    print(f"Latest candle UTC: {latest.ts.isoformat()}")
    print(f"Latest close: {latest.close}")

    if latest.ts.strftime("%A") == "Friday":
        print("SIGNAL: SKIP_FRIDAY")
        return

    if latest.ts.hour not in ENTRY_HOURS:
        print("SIGNAL: OUTSIDE_WINDOW")
        return

    if len(asia) < 16:
        print("SIGNAL: ASIA_RANGE_INCOMPLETE")
        return

    asia_high = max(c.high for c in asia)
    asia_low = min(c.low for c in asia)
    asia_range_pips = pips(asia_high - asia_low)

    print(f"Asian high: {asia_high}")
    print(f"Asian low: {asia_low}")
    print(f"Asian range: {asia_range_pips:.2f} pips")

    if not (MIN_RANGE_PIPS <= asia_range_pips <= MAX_RANGE_PIPS):
        print("SIGNAL: INVALID_ASIA_RANGE")
        return

    long_entry = asia_high + BUFFER_PIPS * PIP
    short_entry = asia_low - BUFFER_PIPS * PIP

    long_stop = asia_low - BUFFER_PIPS * PIP
    short_stop = asia_high + BUFFER_PIPS * PIP

    long_target = long_entry + TP_R * (long_entry - long_stop)
    short_target = short_entry - TP_R * (short_stop - short_entry)

    triggered_long = any(c.high >= long_entry for c in entry_window)
    triggered_short = any(c.low <= short_entry for c in entry_window)

    print(f"Long entry: {long_entry:.5f}")
    print(f"Long stop: {long_stop:.5f}")
    print(f"Long target: {long_target:.5f}")
    print(f"Short entry: {short_entry:.5f}")
    print(f"Short stop: {short_stop:.5f}")
    print(f"Short target: {short_target:.5f}")

    if triggered_long and triggered_short:
        print("SIGNAL: AMBIGUOUS_BOTH_SIDES_TRIGGERED")
    elif triggered_long:
        print("SIGNAL: LONG_TRIGGERED")
    elif triggered_short:
        print("SIGNAL: SHORT_TRIGGERED")
    else:
        print("SIGNAL: NO_TRADE_YET")


if __name__ == "__main__":
    main()
