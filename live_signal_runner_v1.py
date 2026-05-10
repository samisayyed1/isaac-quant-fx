from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from strategy_config_v1 import OPERATIONAL_STRATEGY as CFG

DEFAULT_DATA = Path("/home/sami/quant-fx/live_data/eurusd-m15-live.csv")
LOG_PATH = Path("/home/sami/quant-fx/live_signal_log.csv")

LOG_FIELDS = [
    "checked_at_utc",
    "latest_candle_utc",
    "signal",
    "side",
    "latest_close",
    "asia_high",
    "asia_low",
    "asia_range_pips",
    "entry",
    "stop",
    "target",
    "notes",
]


@dataclass(frozen=True)
class Candle:
    ts: datetime
    open: float
    high: float
    low: float
    close: float


def load_candles(path: Path) -> List[Candle]:
    if not path.exists():
        raise SystemExit(f"Missing data file: {path}")

    candles: List[Candle] = []

    with path.open() as f:
        reader = csv.DictReader(f)
        required = {"timestamp", "open", "high", "low", "close"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise SystemExit(f"CSV missing required columns: {required}")

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

    return sorted(candles, key=lambda c: c.ts)


def pips(x: float) -> float:
    return x / CFG.pip_size


def ensure_log() -> None:
    if LOG_PATH.exists():
        return

    with LOG_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        writer.writeheader()


def append_log(row: dict[str, str]) -> None:
    ensure_log()
    with LOG_PATH.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        writer.writerow(row)


def emit(
    latest: Candle,
    signal: str,
    side: str = "",
    asia_high: Optional[float] = None,
    asia_low: Optional[float] = None,
    asia_range: Optional[float] = None,
    entry: Optional[float] = None,
    stop: Optional[float] = None,
    target: Optional[float] = None,
    notes: str = "",
) -> None:
    row = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "latest_candle_utc": latest.ts.isoformat(),
        "signal": signal,
        "side": side,
        "latest_close": f"{latest.close:.5f}",
        "asia_high": "" if asia_high is None else f"{asia_high:.5f}",
        "asia_low": "" if asia_low is None else f"{asia_low:.5f}",
        "asia_range_pips": "" if asia_range is None else f"{asia_range:.2f}",
        "entry": "" if entry is None else f"{entry:.5f}",
        "stop": "" if stop is None else f"{stop:.5f}",
        "target": "" if target is None else f"{target:.5f}",
        "notes": notes,
    }

    append_log(row)

    print("=== Isaac Live Signal Runner V1 ===")
    print(f"Strategy: {CFG.name}")
    print(f"Latest candle UTC: {latest.ts.isoformat()}")
    print(f"Latest close: {latest.close:.5f}")
    print(f"SIGNAL: {signal}")

    if side:
        print(f"Side: {side}")
        print(f"Entry: {entry:.5f}")
        print(f"Stop: {stop:.5f}")
        print(f"Target: {target:.5f}")

    if notes:
        print(f"Notes: {notes}")

    print(f"Logged: {LOG_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    args = parser.parse_args()

    candles = load_candles(Path(args.data))
    if not candles:
        raise SystemExit("No candles loaded.")

    latest = candles[-1]
    day = latest.ts.date()

    today = [c for c in candles if c.ts.date() == day]
    asia = [c for c in today if CFG.asia_start_hour <= c.ts.hour < CFG.asia_end_hour]
    entry_window_so_far = [c for c in today if c.ts.hour in CFG.entry_hours]

    if CFG.skip_friday and latest.ts.strftime("%A") == "Friday":
        emit(latest, "SKIP_FRIDAY")
        return

    if CFG.skip_december and latest.ts.month == 12:
        emit(latest, "SKIP_DECEMBER")
        return

    if latest.ts.hour not in CFG.entry_hours:
        emit(latest, "OUTSIDE_WINDOW")
        return

    if len(asia) < 16:
        emit(latest, "ASIA_RANGE_INCOMPLETE", notes=f"asia_candles={len(asia)}")
        return

    asia_high = max(c.high for c in asia)
    asia_low = min(c.low for c in asia)
    asia_range = pips(asia_high - asia_low)

    if not (CFG.min_asia_range_pips <= asia_range <= CFG.max_asia_range_pips):
        emit(
            latest,
            "INVALID_ASIA_RANGE",
            asia_high=asia_high,
            asia_low=asia_low,
            asia_range=asia_range,
        )
        return

    long_entry = asia_high + CFG.buffer_pips * CFG.pip_size
    short_entry = asia_low - CFG.buffer_pips * CFG.pip_size

    long_stop = asia_low - CFG.buffer_pips * CFG.pip_size
    short_stop = asia_high + CFG.buffer_pips * CFG.pip_size

    long_target = long_entry + CFG.target_r * (long_entry - long_stop)
    short_target = short_entry - CFG.target_r * (short_stop - short_entry)

    long_triggered = any(c.high >= long_entry for c in entry_window_so_far)
    short_triggered = any(c.low <= short_entry for c in entry_window_so_far)

    if long_triggered and short_triggered:
        emit(
            latest,
            "AMBIGUOUS_BOTH_SIDES_TRIGGERED",
            asia_high=asia_high,
            asia_low=asia_low,
            asia_range=asia_range,
            notes="Rejected by ambiguity rule.",
        )
        return

    if long_triggered:
        emit(
            latest,
            "LONG_TRIGGERED",
            side="LONG",
            asia_high=asia_high,
            asia_low=asia_low,
            asia_range=asia_range,
            entry=long_entry,
            stop=long_stop,
            target=long_target,
        )
        return

    if short_triggered:
        emit(
            latest,
            "SHORT_TRIGGERED",
            side="SHORT",
            asia_high=asia_high,
            asia_low=asia_low,
            asia_range=asia_range,
            entry=short_entry,
            stop=short_stop,
            target=short_target,
        )
        return

    emit(
        latest,
        "NO_TRADE_YET",
        asia_high=asia_high,
        asia_low=asia_low,
        asia_range=asia_range,
    )


if __name__ == "__main__":
    main()
