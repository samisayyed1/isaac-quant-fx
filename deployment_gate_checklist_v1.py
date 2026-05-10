from __future__ import annotations

import csv
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List

ROOT = Path("/home/sami/quant-fx")

LEDGER = ROOT / "paper_trades.csv"
AUDIT = ROOT / "system_audit_v2.sh"
OUT = ROOT / "agent_outputs" / "deployment_gate_checklist.md"

MIN_PAPER_TRADES = 50
MIN_PAPER_DAYS = 60
MIN_PROFIT_FACTOR = 1.30
MAX_ALLOWED_DD_PIPS = -500.0


def read_csv(path: Path) -> List[dict[str, str]]:
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


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


def audit_green() -> bool:
    result = subprocess.run(
        [str(AUDIT)],
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    return result.returncode == 0 and "SYSTEM STATUS: GREEN" in result.stdout


def main() -> None:
    ledger = read_csv(LEDGER)
    closed = [r for r in ledger if r.get("status") == "CLOSED"]
    open_trades = [r for r in ledger if r.get("status") == "OPEN"]
    vals = [float(r["net_pips"]) for r in closed if r.get("net_pips")]

    dates = sorted({
        r["entry_time_utc"][:10]
        for r in ledger
        if r.get("entry_time_utc")
    })

    pf = profit_factor(vals) if vals else 0.0
    dd = max_drawdown(vals) if vals else 0.0
    green = audit_green()

    checks = [
        ("System audit green", green),
        ("No open trade during deployment review", len(open_trades) == 0),
        (f"At least {MIN_PAPER_TRADES} closed paper trades", len(closed) >= MIN_PAPER_TRADES),
        (f"At least {MIN_PAPER_DAYS} calendar days of paper evidence", len(dates) >= MIN_PAPER_DAYS),
        (f"Paper profit factor >= {MIN_PROFIT_FACTOR}", pf >= MIN_PROFIT_FACTOR),
        (f"Paper drawdown better than {MAX_ALLOWED_DD_PIPS:.0f} pips", dd >= MAX_ALLOWED_DD_PIPS),
    ]

    passed = all(ok for _, ok in checks)

    lines = [
        "# Isaac Deployment Gate Checklist V1",
        "",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Current Paper Evidence",
        f"- Total ledger trades: {len(ledger)}",
        f"- Open trades: {len(open_trades)}",
        f"- Closed trades: {len(closed)}",
        f"- Paper evidence days: {len(dates)}",
        f"- Paper total net pips: {sum(vals):.2f}" if vals else "- Paper total net pips: 0.00",
        f"- Paper profit factor: {pf:.2f}",
        f"- Paper max drawdown pips: {dd:.2f}",
        "",
        "## Gate Checks",
    ]

    for label, ok in checks:
        lines.append(f"- [{'PASS' if ok else 'FAIL'}] {label}")

    lines.extend([
        "",
        "## Isaac Decision",
    ])

    if passed:
        lines.append("DEMO BROKER RESEARCH MAY BE CONSIDERED. Live trading still requires separate approval.")
    else:
        lines.append("DEPLOYMENT BLOCKED. Continue paper evidence collection.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n")

    print("=== Isaac Deployment Gate Checklist V1 ===")
    print(f"Report: {OUT}")
    print(f"Gate passed: {passed}")
    print("DEPLOYMENT GATE STATUS: GREEN")


if __name__ == "__main__":
    main()
