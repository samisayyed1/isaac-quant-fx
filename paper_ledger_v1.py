from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

LEDGER = Path("/home/sami/quant-fx/paper_trades.csv")

FIELDS = [
    "trade_id",
    "strategy",
    "pair",
    "side",
    "status",
    "entry_time_utc",
    "entry_price",
    "stop_price",
    "target_price",
    "lot_size",
    "exit_time_utc",
    "exit_price",
    "net_pips",
    "notes",
]

PIP = 0.0001


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_ledger() -> None:
    if LEDGER.exists():
        return

    with LEDGER.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()


def read_trades() -> List[Dict[str, str]]:
    ensure_ledger()
    with LEDGER.open() as f:
        return list(csv.DictReader(f))


def write_trades(rows: List[Dict[str, str]]) -> None:
    with LEDGER.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def next_trade_id(rows: List[Dict[str, str]]) -> str:
    if not rows:
        return "T0001"

    nums = []
    for r in rows:
        try:
            nums.append(int(r["trade_id"].replace("T", "")))
        except ValueError:
            continue

    return f"T{max(nums, default=0) + 1:04d}"


def open_trade(args: argparse.Namespace) -> None:
    rows = read_trades()

    active = [r for r in rows if r["status"] == "OPEN"]
    if active:
        raise SystemExit("Refusing to open: there is already an OPEN paper trade.")

    trade = {
        "trade_id": next_trade_id(rows),
        "strategy": "EURUSD_ASIA_BREAKOUT_V2",
        "pair": "EUR/USD",
        "side": args.side.upper(),
        "status": "OPEN",
        "entry_time_utc": args.time or now_utc(),
        "entry_price": f"{args.entry:.5f}",
        "stop_price": f"{args.stop:.5f}",
        "target_price": f"{args.target:.5f}",
        "lot_size": f"{args.lot:.2f}",
        "exit_time_utc": "",
        "exit_price": "",
        "net_pips": "",
        "notes": args.notes or "",
    }

    rows.append(trade)
    write_trades(rows)

    print("OPENED PAPER TRADE")
    print(trade)


def close_trade(args: argparse.Namespace) -> None:
    rows = read_trades()

    open_rows = [r for r in rows if r["status"] == "OPEN"]
    if len(open_rows) != 1:
        raise SystemExit(f"Expected exactly 1 OPEN trade, found {len(open_rows)}.")

    trade = open_rows[0]
    entry = float(trade["entry_price"])
    exit_price = args.exit

    if trade["side"] == "LONG":
        net_pips = (exit_price - entry) / PIP
    elif trade["side"] == "SHORT":
        net_pips = (entry - exit_price) / PIP
    else:
        raise SystemExit(f"Invalid side: {trade['side']}")

    trade["status"] = "CLOSED"
    trade["exit_time_utc"] = args.time or now_utc()
    trade["exit_price"] = f"{exit_price:.5f}"
    trade["net_pips"] = f"{net_pips:.2f}"

    if args.notes:
        trade["notes"] = (trade["notes"] + " | " + args.notes).strip(" |")

    write_trades(rows)

    print("CLOSED PAPER TRADE")
    print(trade)


def summary() -> None:
    rows = read_trades()
    closed = [r for r in rows if r["status"] == "CLOSED"]
    open_rows = [r for r in rows if r["status"] == "OPEN"]

    vals = [float(r["net_pips"]) for r in closed if r["net_pips"]]
    wins = [v for v in vals if v > 0]
    losses = [v for v in vals if v <= 0]

    print("=== Paper Ledger Summary ===")
    print(f"Ledger: {LEDGER}")
    print(f"Total trades: {len(rows)}")
    print(f"Open trades: {len(open_rows)}")
    print(f"Closed trades: {len(closed)}")

    if vals:
        print(f"Total net pips: {sum(vals):.2f}")
        print(f"Avg pips/trade: {sum(vals) / len(vals):.2f}")
        print(f"Win rate: {len(wins) / len(vals) * 100:.2f}%")
        print(f"Wins: {len(wins)}")
        print(f"Losses: {len(losses)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")

    open_cmd = sub.add_parser("open")
    open_cmd.add_argument("--side", required=True, choices=["LONG", "SHORT"])
    open_cmd.add_argument("--entry", required=True, type=float)
    open_cmd.add_argument("--stop", required=True, type=float)
    open_cmd.add_argument("--target", required=True, type=float)
    open_cmd.add_argument("--lot", required=True, type=float)
    open_cmd.add_argument("--time")
    open_cmd.add_argument("--notes")

    close_cmd = sub.add_parser("close")
    close_cmd.add_argument("--exit", required=True, type=float)
    close_cmd.add_argument("--time")
    close_cmd.add_argument("--notes")

    sub.add_parser("summary")

    args = parser.parse_args()

    if args.cmd == "init":
        ensure_ledger()
        print(f"Ledger ready: {LEDGER}")
    elif args.cmd == "open":
        open_trade(args)
    elif args.cmd == "close":
        close_trade(args)
    elif args.cmd == "summary":
        summary()


if __name__ == "__main__":
    main()
