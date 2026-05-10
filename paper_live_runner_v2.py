from __future__ import annotations

import argparse
import csv
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from strategy_config_v1 import OPERATIONAL_STRATEGY as CFG

ROOT = Path("/home/sami/quant-fx")
DATA_PATH = ROOT / "live_data" / "eurusd-m15-live.csv"
LEDGER_PATH = ROOT / "paper_trades.csv"
RUN_LOG_PATH = ROOT / "paper_live_runner_log.csv"
UPDATE_SCRIPT = ROOT / "live_data_update_v1.sh"

LEDGER_FIELDS = [
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

RUN_LOG_FIELDS = [
    "run_time_utc",
    "latest_candle_utc",
    "action",
    "signal",
    "trade_id",
    "side",
    "entry",
    "stop",
    "target",
    "exit_price",
    "net_pips",
    "notes",
]


@dataclass(frozen=True)
class Candle:
    ts: datetime
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class Signal:
    name: str
    side: str = ""
    entry: Optional[float] = None
    stop: Optional[float] = None
    target: Optional[float] = None
    notes: str = ""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def pips(value: float) -> float:
    return value / CFG.pip_size


def run_update() -> None:
    if not UPDATE_SCRIPT.exists():
        raise SystemExit(f"Missing update script: {UPDATE_SCRIPT}")

    subprocess.run([str(UPDATE_SCRIPT)], check=True)


def load_candles() -> List[Candle]:
    if not DATA_PATH.exists():
        raise SystemExit(f"Missing live data file: {DATA_PATH}")

    candles: List[Candle] = []

    with DATA_PATH.open() as f:
        reader = csv.DictReader(f)
        required = {"timestamp", "open", "high", "low", "close"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise SystemExit(f"Live CSV missing required columns: {required}")

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

    if not candles:
        raise SystemExit("Live CSV contains no candles.")

    return sorted(candles, key=lambda c: c.ts)


def ensure_csv(path: Path, fields: List[str]) -> None:
    if path.exists():
        return

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()


def read_ledger() -> List[dict[str, str]]:
    ensure_csv(LEDGER_PATH, LEDGER_FIELDS)
    with LEDGER_PATH.open() as f:
        return list(csv.DictReader(f))


def write_ledger(rows: List[dict[str, str]]) -> None:
    with LEDGER_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def append_run_log(row: dict[str, str]) -> None:
    ensure_csv(RUN_LOG_PATH, RUN_LOG_FIELDS)
    with RUN_LOG_PATH.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RUN_LOG_FIELDS)
        writer.writerow(row)


def next_trade_id(rows: List[dict[str, str]]) -> str:
    nums: List[int] = []
    for row in rows:
        try:
            nums.append(int(row["trade_id"].replace("T", "")))
        except ValueError:
            continue
    return f"T{max(nums, default=0) + 1:04d}"


def log_action(
    latest: Candle,
    action: str,
    signal: str,
    trade_id: str = "",
    side: str = "",
    entry: Optional[float] = None,
    stop: Optional[float] = None,
    target: Optional[float] = None,
    exit_price: Optional[float] = None,
    net_pips: Optional[float] = None,
    notes: str = "",
) -> None:
    append_run_log(
        {
            "run_time_utc": now_utc(),
            "latest_candle_utc": latest.ts.isoformat(),
            "action": action,
            "signal": signal,
            "trade_id": trade_id,
            "side": side,
            "entry": "" if entry is None else f"{entry:.5f}",
            "stop": "" if stop is None else f"{stop:.5f}",
            "target": "" if target is None else f"{target:.5f}",
            "exit_price": "" if exit_price is None else f"{exit_price:.5f}",
            "net_pips": "" if net_pips is None else f"{net_pips:.2f}",
            "notes": notes,
        }
    )


def evaluate_signal(candles: List[Candle]) -> Signal:
    latest = candles[-1]
    day = latest.ts.date()

    if CFG.skip_friday and latest.ts.strftime("%A") == "Friday":
        return Signal("SKIP_FRIDAY")

    if CFG.skip_december and latest.ts.month == 12:
        return Signal("SKIP_DECEMBER")

    if latest.ts.hour not in CFG.entry_hours:
        return Signal("OUTSIDE_WINDOW")

    today = [c for c in candles if c.ts.date() == day]
    asia = [c for c in today if CFG.asia_start_hour <= c.ts.hour < CFG.asia_end_hour]
    entry_window = [c for c in today if c.ts.hour in CFG.entry_hours]

    if len(asia) < 16:
        return Signal("ASIA_RANGE_INCOMPLETE", notes=f"asia_candles={len(asia)}")

    asia_high = max(c.high for c in asia)
    asia_low = min(c.low for c in asia)
    asia_range = pips(asia_high - asia_low)

    if not (CFG.min_asia_range_pips <= asia_range <= CFG.max_asia_range_pips):
        return Signal("INVALID_ASIA_RANGE", notes=f"asia_range={asia_range:.2f}")

    long_entry = asia_high + CFG.buffer_pips * CFG.pip_size
    short_entry = asia_low - CFG.buffer_pips * CFG.pip_size

    long_stop = asia_low - CFG.buffer_pips * CFG.pip_size
    short_stop = asia_high + CFG.buffer_pips * CFG.pip_size

    long_target = long_entry + CFG.target_r * (long_entry - long_stop)
    short_target = short_entry - CFG.target_r * (short_stop - short_entry)

    long_triggered = any(c.high >= long_entry for c in entry_window)
    short_triggered = any(c.low <= short_entry for c in entry_window)

    if long_triggered and short_triggered:
        return Signal("AMBIGUOUS_BOTH_SIDES_TRIGGERED", notes="Rejected.")

    if long_triggered:
        return Signal(
            "LONG_TRIGGERED",
            side="LONG",
            entry=long_entry,
            stop=long_stop,
            target=long_target,
            notes=f"asia_range={asia_range:.2f}",
        )

    if short_triggered:
        return Signal(
            "SHORT_TRIGGERED",
            side="SHORT",
            entry=short_entry,
            stop=short_stop,
            target=short_target,
            notes=f"asia_range={asia_range:.2f}",
        )

    return Signal("NO_TRADE_YET", notes=f"asia_range={asia_range:.2f}")


def resolve_open_trades(candles: List[Candle], rows: List[dict[str, str]]) -> bool:
    latest = candles[-1]
    changed = False

    for trade in [r for r in rows if r["status"] == "OPEN"]:
        entry_time = parse_dt(trade["entry_time_utc"])
        entry = float(trade["entry_price"])
        stop = float(trade["stop_price"])
        target = float(trade["target_price"])
        side = trade["side"]

        future = [
            c for c in candles
            if entry_time <= c.ts <= latest.ts and c.ts.date() == entry_time.date()
        ]

        if not future:
            continue

        exit_price: Optional[float] = None
        exit_time: Optional[datetime] = None
        reason = ""

        for candle in future:
            if side == "LONG":
                hit_stop = candle.low <= stop
                hit_target = candle.high >= target

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
                hit_stop = candle.high >= stop
                hit_target = candle.low <= target

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
                raise SystemExit(f"Invalid side in ledger: {side}")

            if exit_price is not None:
                exit_time = candle.ts
                break

            if candle.ts.hour >= CFG.exit_hour:
                exit_price = candle.close
                exit_time = candle.ts
                reason = "TIME_EXIT"
                break

        if exit_price is None or exit_time is None:
            continue

        gross_pips = (exit_price - entry) / CFG.pip_size if side == "LONG" else (entry - exit_price) / CFG.pip_size
        net = gross_pips - CFG.round_trip_cost_pips

        trade["status"] = "CLOSED"
        trade["exit_time_utc"] = exit_time.isoformat()
        trade["exit_price"] = f"{exit_price:.5f}"
        trade["net_pips"] = f"{net:.2f}"
        trade["notes"] = (trade["notes"] + f" | live_exit={reason}").strip(" |")

        log_action(
            latest=latest,
            action="CLOSED_TRADE",
            signal=reason,
            trade_id=trade["trade_id"],
            side=side,
            exit_price=exit_price,
            net_pips=net,
            notes=trade["notes"],
        )

        print(f"CLOSED {trade['trade_id']} {side} {net:.2f} pips via {reason}")
        changed = True

    return changed


def open_trade_if_needed(candles: List[Candle], rows: List[dict[str, str]], lot: float) -> bool:
    latest = candles[-1]
    signal = evaluate_signal(candles)

    print("=== Isaac Paper Live Runner V2 ===")
    print(f"Strategy: {CFG.name}")
    print(f"Latest candle UTC: {latest.ts.isoformat()}")
    print(f"Latest close: {latest.close:.5f}")
    print(f"Signal: {signal.name}")

    if signal.notes:
        print(f"Notes: {signal.notes}")

    if signal.name not in {"LONG_TRIGGERED", "SHORT_TRIGGERED"}:
        log_action(latest, "NO_OPEN", signal.name, notes=signal.notes)
        return False

    if any(r["status"] == "OPEN" for r in rows):
        log_action(latest, "NO_OPEN", signal.name, notes="Open trade already exists.")
        print("No open: existing OPEN trade.")
        return False

    day = latest.ts.date().isoformat()
    if any(r["entry_time_utc"].startswith(day) for r in rows):
        log_action(latest, "NO_OPEN", signal.name, notes="Trade already recorded for day.")
        print("No open: trade already recorded for today.")
        return False

    assert signal.entry is not None
    assert signal.stop is not None
    assert signal.target is not None

    trade_id = next_trade_id(rows)

    trade = {
        "trade_id": trade_id,
        "strategy": CFG.name,
        "pair": CFG.pair,
        "side": signal.side,
        "status": "OPEN",
        "entry_time_utc": latest.ts.isoformat(),
        "entry_price": f"{signal.entry:.5f}",
        "stop_price": f"{signal.stop:.5f}",
        "target_price": f"{signal.target:.5f}",
        "lot_size": f"{lot:.2f}",
        "exit_time_utc": "",
        "exit_price": "",
        "net_pips": "",
        "notes": f"paper live runner v2 | {signal.notes}",
    }

    rows.append(trade)

    log_action(
        latest=latest,
        action="OPENED_TRADE",
        signal=signal.name,
        trade_id=trade_id,
        side=signal.side,
        entry=signal.entry,
        stop=signal.stop,
        target=signal.target,
        notes=trade["notes"],
    )

    print(f"OPENED {trade_id} {signal.side}")
    print(f"Entry: {signal.entry:.5f}")
    print(f"Stop: {signal.stop:.5f}")
    print(f"Target: {signal.target:.5f}")

    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lot", type=float, default=0.01)
    parser.add_argument("--skip-update", action="store_true")
    args = parser.parse_args()

    if args.lot <= 0:
        raise SystemExit("Lot size must be positive.")

    if args.lot > CFG.max_paper_lot:
        raise SystemExit(f"Paper lot capped at {CFG.max_paper_lot:.2f} by Isaac risk rule.")

    if not args.skip_update:
        run_update()

    candles = load_candles()
    rows = read_ledger()

    changed = resolve_open_trades(candles, rows)
    if changed:
        write_ledger(rows)
        rows = read_ledger()

    opened = open_trade_if_needed(candles, rows, args.lot)
    if opened:
        write_ledger(rows)

    print(f"Ledger: {LEDGER_PATH}")
    print(f"Run log: {RUN_LOG_PATH}")


if __name__ == "__main__":
    main()
