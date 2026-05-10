from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

ROOT = Path("/home/sami/quant-fx")

LEDGER = ROOT / "paper_trades.csv"
RUN_LOG = ROOT / "paper_live_runner_log.csv"
EVENTS = ROOT / "memory" / "events.jsonl"
OUT = ROOT / "agent_outputs" / "weekly_paper_evidence_report.md"


def read_csv(path: Path) -> List[dict[str, str]]:
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


def read_events(path: Path) -> List[dict]:
    if not path.exists():
        return []

    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


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


def main() -> None:
    ledger = read_csv(LEDGER)
    runs = read_csv(RUN_LOG)
    events = read_events(EVENTS)

    open_trades = [r for r in ledger if r.get("status") == "OPEN"]
    closed_trades = [r for r in ledger if r.get("status") == "CLOSED"]
    vals = [float(r["net_pips"]) for r in closed_trades if r.get("net_pips")]

    signals = {}
    for r in runs:
        signal = r.get("signal", "UNKNOWN") or "UNKNOWN"
        signals[signal] = signals.get(signal, 0) + 1

    cloud_notes = [e for e in events if e.get("kind") == "CLOUD_RESEARCH_NOTE"]
    latest_cloud = cloud_notes[-1] if cloud_notes else None

    wins = [v for v in vals if v > 0]
    losses = [v for v in vals if v <= 0]

    lines = [
        "# Isaac Weekly Paper Evidence Report V1",
        "",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Evidence Status",
    ]

    if not ledger:
        lines.append("- Paper ledger is clean. No paper trades recorded yet.")
    elif open_trades:
        lines.append("- Paper system has open trade exposure.")
    else:
        lines.append("- Paper system has no open exposure.")

    lines.extend([
        "",
        "## Paper Ledger",
        f"- Total trades: {len(ledger)}",
        f"- Open trades: {len(open_trades)}",
        f"- Closed trades: {len(closed_trades)}",
    ])

    if vals:
        lines.extend([
            f"- Total net pips: {sum(vals):.2f}",
            f"- Average pips/trade: {sum(vals) / len(vals):.2f}",
            f"- Win rate: {len(wins) / len(vals) * 100:.2f}%",
            f"- Profit factor: {profit_factor(vals):.2f}",
            f"- Max drawdown pips: {max_drawdown(vals):.2f}",
            f"- Wins: {len(wins)}",
            f"- Losses: {len(losses)}",
        ])
    else:
        lines.append("- Closed trade stats: no closed paper trades yet.")

    lines.extend([
        "",
        "## Runner Signal Counts",
    ])

    if signals:
        for signal, count in sorted(signals.items()):
            lines.append(f"- {signal}: {count}")
    else:
        lines.append("- No runner signals logged yet.")

    lines.extend([
        "",
        "## Latest Cloud Research Note",
    ])

    if latest_cloud:
        payload = latest_cloud.get("payload", {})
        lines.extend([
            f"- Model: {payload.get('model')}",
            f"- Risk state: {payload.get('current_risk_state')}",
            f"- Human review needed: {payload.get('human_review_needed')}",
            f"- Next research question: {payload.get('next_research_question')}",
        ])

        anomalies = payload.get("anomalies", [])
        if anomalies:
            lines.append("- Anomalies:")
            for item in anomalies:
                lines.append(f"  - {item}")
        else:
            lines.append("- Anomalies: none")
    else:
        lines.append("- No cloud research notes ingested yet.")

    lines.extend([
        "",
        "## Isaac Decision",
    ])

    if open_trades:
        lines.append("Paper trading is active. Monitor open trade resolution.")
    elif not vals:
        lines.append("System is ready for paper evidence collection. No live-account decision can be made yet.")
    else:
        lines.append("Paper evidence exists. Continue collecting until sample size is meaningful.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n")

    print("=== Isaac Weekly Paper Evidence Report V1 ===")
    print(f"Report: {OUT}")
    print("WEEKLY EVIDENCE REPORT STATUS: GREEN")


if __name__ == "__main__":
    main()
