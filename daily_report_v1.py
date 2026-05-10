from __future__ import annotations

import csv
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List

ROOT = Path("/home/sami/quant-fx")

LIVE_DATA = ROOT / "live_data" / "eurusd-m15-live.csv"
LEDGER = ROOT / "paper_trades.csv"
RUN_LOG = ROOT / "paper_live_runner_log.csv"
SIGNAL_LOG = ROOT / "live_signal_log.csv"
AUDIT = ROOT / "system_audit_v1.sh"

PIP_VALUE_PER_STANDARD_LOT = 10.0


def read_csv(path: Path) -> List[dict[str, str]]:
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


def latest_candle() -> dict[str, str] | None:
    rows = read_csv(LIVE_DATA)
    return rows[-1] if rows else None


def ms_to_utc(ms: str) -> str:
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat()


def max_drawdown(vals: List[float]) -> float:
    equity = 0.0
    peak = 0.0
    worst = 0.0

    for v in vals:
        equity += v
        peak = max(peak, equity)
        worst = min(worst, equity - peak)

    return worst


def profit_factor(vals: List[float]) -> float:
    wins = sum(v for v in vals if v > 0)
    losses = abs(sum(v for v in vals if v < 0))
    return wins / losses if losses else 999.0


def audit_status() -> str:
    if not AUDIT.exists():
        return "RED: missing system audit script"

    try:
        result = subprocess.run(
            [str(AUDIT)],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except Exception as e:
        return f"RED: audit failed to run: {e}"

    if result.returncode == 0 and "SYSTEM STATUS: GREEN" in result.stdout:
        return "GREEN"

    return "RED: replay audit failed"


def main() -> None:
    print("=== Isaac Daily Quant-FX Report V1 ===")
    print(f"Generated UTC: {datetime.now(timezone.utc).isoformat()}")
    print("")

    status = audit_status()
    print(f"System audit: {status}")

    candle = latest_candle()
    if candle:
        print("")
        print("=== Latest Live Candle ===")
        print(f"UTC: {ms_to_utc(candle['timestamp'])}")
        print(f"Open: {float(candle['open']):.5f}")
        print(f"High: {float(candle['high']):.5f}")
        print(f"Low: {float(candle['low']):.5f}")
        print(f"Close: {float(candle['close']):.5f}")
    else:
        print("")
        print("Latest live candle: MISSING")

    runner_rows = read_csv(RUN_LOG)
    print("")
    print("=== Latest Runner Action ===")
    if runner_rows:
        r = runner_rows[-1]
        print(f"Run time: {r.get('run_time_utc', '')}")
        print(f"Latest candle: {r.get('latest_candle_utc', '')}")
        print(f"Action: {r.get('action', '')}")
        print(f"Signal: {r.get('signal', '')}")
        print(f"Trade ID: {r.get('trade_id', '') or '-'}")
        print(f"Side: {r.get('side', '') or '-'}")
        print(f"Notes: {r.get('notes', '') or '-'}")
    else:
        print("No runner actions logged yet.")

    ledger_rows = read_csv(LEDGER)
    open_trades = [r for r in ledger_rows if r.get("status") == "OPEN"]
    closed_trades = [r for r in ledger_rows if r.get("status") == "CLOSED"]
    vals = [float(r["net_pips"]) for r in closed_trades if r.get("net_pips")]

    print("")
    print("=== Paper Ledger ===")
    print(f"Total trades: {len(ledger_rows)}")
    print(f"Open trades: {len(open_trades)}")
    print(f"Closed trades: {len(closed_trades)}")

    if open_trades:
        print("")
        print("=== Open Trade ===")
        for t in open_trades:
            print(f"Trade: {t['trade_id']} {t['side']} {t['pair']}")
            print(f"Entry time: {t['entry_time_utc']}")
            print(f"Entry: {t['entry_price']}")
            print(f"Stop: {t['stop_price']}")
            print(f"Target: {t['target_price']}")
            print(f"Lot: {t['lot_size']}")

    if vals:
        wins = [v for v in vals if v > 0]
        losses = [v for v in vals if v <= 0]

        print("")
        print("=== Closed Trade Stats ===")
        print(f"Total net pips: {sum(vals):.2f}")
        print(f"Average pips/trade: {sum(vals) / len(vals):.2f}")
        print(f"Win rate: {len(wins) / len(vals) * 100:.2f}%")
        print(f"Profit factor: {profit_factor(vals):.2f}")
        print(f"Max drawdown pips: {max_drawdown(vals):.2f}")
        print(f"Wins: {len(wins)}")
        print(f"Losses: {len(losses)}")
    else:
        print("")
        print("Closed trade stats: no closed live-paper trades yet.")

    print("")
    print("=== Isaac Decision ===")
    if status == "GREEN":
        print("System is operational for paper trading only.")
    else:
        print("Do not operate. Fix RED status first.")


if __name__ == "__main__":
    main()
