from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from strategy_config_v1 import OPERATIONAL_STRATEGY as CFG

DATA_PATH = Path("/home/sami/download/eurusd-m15-bid-2025-01-01-2026-01-01.csv")
LEDGER = Path("/home/sami/quant-fx/paper_trades.csv")

FIELDS = [
    "trade_id", "strategy", "pair", "side", "status",
    "entry_time_utc", "entry_price", "stop_price", "target_price",
    "lot_size", "exit_time_utc", "exit_price", "net_pips", "notes",
]


@dataclass(frozen=True)
class Candle:
    ts: datetime
    open: float
    high: float
    low: float
    close: float


def parse_at(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def load_candles() -> List[Candle]:
    out: List[Candle] = []
    with DATA_PATH.open() as f:
        for r in csv.DictReader(f):
            out.append(Candle(
                ts=datetime.fromtimestamp(int(r["timestamp"]) / 1000, tz=timezone.utc),
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
            ))
    return sorted(out, key=lambda c: c.ts)


def ensure_ledger() -> None:
    if LEDGER.exists():
        return
    with LEDGER.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()


def read_ledger() -> List[dict[str, str]]:
    ensure_ledger()
    with LEDGER.open() as f:
        return list(csv.DictReader(f))


def write_ledger(rows: List[dict[str, str]]) -> None:
    with LEDGER.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def next_trade_id(rows: List[dict[str, str]]) -> str:
    nums = []
    for r in rows:
        try:
            nums.append(int(r["trade_id"].replace("T", "")))
        except ValueError:
            pass
    return f"T{max(nums, default=0) + 1:04d}"


def pips(x: float) -> float:
    return x / CFG.pip_size


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--at", required=True, help="UTC replay time, e.g. 2025-09-03T08:15:00Z")
    parser.add_argument("--lot", type=float, default=0.01)
    args = parser.parse_args()

    if args.lot <= 0:
        raise SystemExit("Lot size must be positive.")

    if args.lot > CFG.max_paper_lot:
        raise SystemExit(f"Paper lot capped at {CFG.max_paper_lot:.2f} by Isaac risk rule.")

    at = parse_at(args.at)
    candles = [c for c in load_candles() if c.ts <= at]
    if not candles:
        raise SystemExit("No candles found before timestamp.")

    latest = candles[-1]
    day = latest.ts.date()

    rows = read_ledger()

    if any(r["status"] == "OPEN" for r in rows):
        raise SystemExit("Refusing: one paper trade is already OPEN.")

    if any(r["entry_time_utc"].startswith(day.isoformat()) for r in rows):
        raise SystemExit("Refusing: trade already recorded for this day.")

    if CFG.skip_friday and latest.ts.strftime("%A") == "Friday":
        print("NO TRADE: Friday filter.")
        return

    if CFG.skip_december and latest.ts.month == 12:
        print("NO TRADE: December filter.")
        return

    if latest.ts.hour not in CFG.entry_hours:
        print("NO TRADE: outside entry window.")
        return

    today = [c for c in candles if c.ts.date() == day]
    asia = [c for c in today if CFG.asia_start_hour <= c.ts.hour < CFG.asia_end_hour]
    entry_window = [c for c in today if c.ts.hour in CFG.entry_hours]

    if len(asia) < 16:
        print("NO TRADE: Asia range incomplete.")
        return

    asia_high = max(c.high for c in asia)
    asia_low = min(c.low for c in asia)
    asia_range = pips(asia_high - asia_low)

    if not (CFG.min_asia_range_pips <= asia_range <= CFG.max_asia_range_pips):
        print(f"NO TRADE: invalid Asia range {asia_range:.2f} pips.")
        return

    long_entry = asia_high + CFG.buffer_pips * CFG.pip_size
    short_entry = asia_low - CFG.buffer_pips * CFG.pip_size

    long_stop = asia_low - CFG.buffer_pips * CFG.pip_size
    short_stop = asia_high + CFG.buffer_pips * CFG.pip_size

    long_target = long_entry + CFG.target_r * (long_entry - long_stop)
    short_target = short_entry - CFG.target_r * (short_stop - short_entry)

    long_triggered = any(c.high >= long_entry for c in entry_window)
    short_triggered = any(c.low <= short_entry for c in entry_window)

    if long_triggered and short_triggered:
        print("NO TRADE: ambiguous both-side trigger.")
        return

    if long_triggered:
        side = "LONG"
        entry = long_entry
        stop = long_stop
        target = long_target
    elif short_triggered:
        side = "SHORT"
        entry = short_entry
        stop = short_stop
        target = short_target
    else:
        print("NO TRADE: no breakout yet.")
        return

    trade = {
        "trade_id": next_trade_id(rows),
        "strategy": CFG.name,
        "pair": CFG.pair,
        "side": side,
        "status": "OPEN",
        "entry_time_utc": latest.ts.isoformat(),
        "entry_price": f"{entry:.5f}",
        "stop_price": f"{stop:.5f}",
        "target_price": f"{target:.5f}",
        "lot_size": f"{args.lot:.2f}",
        "exit_time_utc": "",
        "exit_price": "",
        "net_pips": "",
        "notes": f"paper bridge v1 | asia_range={asia_range:.2f}",
    }

    rows.append(trade)
    write_ledger(rows)

    print("OPENED PAPER TRADE")
    print(trade)


if __name__ == "__main__":
    main()
