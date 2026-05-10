from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict

DATA_PATH = Path("/home/sami/download/eurusd-m15-bid-2025-01-01-2026-01-01.csv")
LEDGER = Path("/home/sami/quant-fx/paper_trades.csv")
PIP = 0.0001
ROUND_TRIP_COST_PIPS = 1.2
EXIT_HOUR = 14

FIELDS = [
    "trade_id", "strategy", "pair", "side", "status",
    "entry_time_utc", "entry_price", "stop_price", "target_price",
    "lot_size", "exit_time_utc", "exit_price", "net_pips", "notes",
]


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def load_candles() -> List[dict]:
    rows = []
    with DATA_PATH.open() as f:
        for r in csv.DictReader(f):
            rows.append({
                "ts": datetime.fromtimestamp(int(r["timestamp"]) / 1000, tz=timezone.utc),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
            })
    return sorted(rows, key=lambda x: x["ts"])


def read_ledger() -> List[Dict[str, str]]:
    with LEDGER.open() as f:
        return list(csv.DictReader(f))


def write_ledger(rows: List[Dict[str, str]]) -> None:
    with LEDGER.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--at", required=True, help="Resolve up to UTC timestamp, e.g. 2025-09-03T14:00:00Z")
    args = parser.parse_args()

    resolve_until = parse_dt(args.at)
    candles = load_candles()
    rows = read_ledger()

    open_trades = [r for r in rows if r["status"] == "OPEN"]

    if not open_trades:
        print("NO OPEN TRADES")
        return

    for trade in open_trades:
        entry_time = parse_dt(trade["entry_time_utc"])
        entry = float(trade["entry_price"])
        stop = float(trade["stop_price"])
        target = float(trade["target_price"])
        side = trade["side"]

        future = [
            c for c in candles
            if entry_time <= c["ts"] <= resolve_until and c["ts"].date() == entry_time.date()
        ]

        if not future:
            print(f"{trade['trade_id']}: no candles available after entry")
            continue

        exit_price = None
        exit_time = None
        reason = None

        for c in future:
            if side == "LONG":
                hit_stop = c["low"] <= stop
                hit_target = c["high"] >= target

                if hit_stop and hit_target:
                    exit_price = stop
                    reason = "STOP_AMBIGUOUS"
                elif hit_stop:
                    exit_price = stop
                    reason = "STOP"
                elif hit_target:
                    exit_price = target
                    reason = "TARGET"

            elif side == "SHORT":
                hit_stop = c["high"] >= stop
                hit_target = c["low"] <= target

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
                raise SystemExit(f"Invalid side: {side}")

            if exit_price is not None:
                exit_time = c["ts"]
                break

            if c["ts"].hour >= EXIT_HOUR:
                exit_price = c["close"]
                exit_time = c["ts"]
                reason = "TIME_EXIT"
                break

        if exit_price is None:
            print(f"{trade['trade_id']}: still open as of {resolve_until.isoformat()}")
            continue

        if side == "LONG":
            net_pips = (exit_price - entry) / PIP
        else:
            net_pips = (entry - exit_price) / PIP

        trade["status"] = "CLOSED"
        trade["exit_time_utc"] = exit_time.isoformat()
        trade["exit_price"] = f"{exit_price:.5f}"
        trade["net_pips"] = f"{net_pips - ROUND_TRIP_COST_PIPS:.2f}"
        trade["notes"] = (trade["notes"] + f" | exit_reason={reason}").strip(" |")

        print("CLOSED PAPER TRADE")
        print(trade)

    write_ledger(rows)


if __name__ == "__main__":
    main()
