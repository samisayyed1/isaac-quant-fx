from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List

from strategy_config_v1 import OPERATIONAL_STRATEGY as CFG

ROOT = Path("/home/sami/quant-fx")
MEMORY_DIR = ROOT / "memory"
EVENTS = MEMORY_DIR / "events.jsonl"
SNAPSHOT = MEMORY_DIR / "latest_snapshot.json"
REPORT = MEMORY_DIR / "latest_memory_report.md"

LEDGER = ROOT / "paper_trades.csv"
RUN_LOG = ROOT / "paper_live_runner_log.csv"
SIGNAL_LOG = ROOT / "live_signal_log.csv"
AUDIT = ROOT / "system_audit_v2.sh"

MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv(path: Path) -> List[dict[str, str]]:
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


def sha256_obj(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()


def max_drawdown(vals: List[float]) -> float:
    eq = peak = worst = 0.0
    for v in vals:
        eq += v
        peak = max(peak, eq)
        worst = min(worst, eq - peak)
    return worst


def profit_factor(vals: List[float]) -> float:
    wins = sum(v for v in vals if v > 0)
    losses = abs(sum(v for v in vals if v < 0))
    return wins / losses if losses else 999.0


def audit_status() -> str:
    if not AUDIT.exists():
        return "RED_MISSING_AUDIT"

    result = subprocess.run(
        [str(AUDIT)],
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )

    if result.returncode == 0 and "SYSTEM STATUS: GREEN" in result.stdout:
        return "GREEN"

    return "RED_AUDIT_FAILED"


def build_snapshot() -> dict[str, Any]:
    ledger = read_csv(LEDGER)
    runner = read_csv(RUN_LOG)
    signal = read_csv(SIGNAL_LOG)

    closed = [r for r in ledger if r.get("status") == "CLOSED"]
    open_trades = [r for r in ledger if r.get("status") == "OPEN"]
    vals = [float(r["net_pips"]) for r in closed if r.get("net_pips")]

    wins = [v for v in vals if v > 0]
    losses = [v for v in vals if v <= 0]

    stats = {
        "total_trades": len(ledger),
        "open_trades": len(open_trades),
        "closed_trades": len(closed),
        "total_net_pips": round(sum(vals), 2) if vals else 0.0,
        "avg_pips": round(sum(vals) / len(vals), 2) if vals else 0.0,
        "win_rate": round(len(wins) / len(vals) * 100, 2) if vals else 0.0,
        "profit_factor": round(profit_factor(vals), 2) if vals else 0.0,
        "max_drawdown_pips": round(max_drawdown(vals), 2) if vals else 0.0,
        "wins": len(wins),
        "losses": len(losses),
    }

    snapshot = {
        "created_at_utc": now(),
        "system": "isaac-quant-fx",
        "audit_status": audit_status(),
        "strategy": CFG.name,
        "mode": "PAPER_ONLY",
        "latest_runner_action": runner[-1] if runner else None,
        "latest_signal_action": signal[-1] if signal else None,
        "open_trades": open_trades,
        "stats": stats,
        "guardrails": {
            "live_execution_enabled": False,
            "max_paper_lot": CFG.max_paper_lot,
            "requires_3_month_paper_validation": True,
            "ai_may_not_auto_change_live_logic": True,
        },
    }

    snapshot["snapshot_hash"] = sha256_obj(snapshot)
    return snapshot


def append_event(kind: str, payload: dict[str, Any]) -> None:
    event = {
        "time_utc": now(),
        "kind": kind,
        "payload": payload,
    }
    event["event_hash"] = sha256_obj(event)

    with EVENTS.open("a") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def write_report(snapshot: dict[str, Any]) -> None:
    stats = snapshot["stats"]

    lines = [
        "# Isaac Research Memory Report",
        "",
        f"Generated UTC: {snapshot['created_at_utc']}",
        f"Audit status: {snapshot['audit_status']}",
        f"Mode: {snapshot['mode']}",
        f"Strategy: {snapshot['strategy']}",
        "",
        "## Paper Performance",
        f"- Total trades: {stats['total_trades']}",
        f"- Open trades: {stats['open_trades']}",
        f"- Closed trades: {stats['closed_trades']}",
        f"- Total net pips: {stats['total_net_pips']}",
        f"- Avg pips/trade: {stats['avg_pips']}",
        f"- Win rate: {stats['win_rate']}%",
        f"- Profit factor: {stats['profit_factor']}",
        f"- Max drawdown pips: {stats['max_drawdown_pips']}",
        "",
        "## Latest Runner Action",
        "```json",
        json.dumps(snapshot["latest_runner_action"], indent=2, sort_keys=True),
        "```",
        "",
        "## Isaac Decision",
    ]

    if snapshot["audit_status"] == "GREEN":
        lines.append("System remains eligible for paper-trading operation only.")
    else:
        lines.append("System is RED. Do not operate until fixed.")

    REPORT.write_text("\n".join(lines) + "\n")


def snapshot_cmd() -> None:
    snapshot = build_snapshot()
    SNAPSHOT.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    write_report(snapshot)
    append_event("SNAPSHOT", snapshot)

    print("=== Isaac Research Memory V1 ===")
    print(f"Audit: {snapshot['audit_status']}")
    print(f"Snapshot: {SNAPSHOT}")
    print(f"Report: {REPORT}")
    print(f"Events: {EVENTS}")
    print(f"Hash: {snapshot['snapshot_hash']}")


def note_cmd(text: str) -> None:
    append_event("MANUAL_NOTE", {"text": text})
    print("NOTE SAVED")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("snapshot")

    note = sub.add_parser("note")
    note.add_argument("text")

    args = parser.parse_args()

    if args.cmd == "snapshot":
        snapshot_cmd()
    elif args.cmd == "note":
        note_cmd(args.text)


if __name__ == "__main__":
    main()
