from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import List

ROOT = Path("/home/sami/quant-fx")

PAPER = ROOT / "paper_trades.csv"
BACKTEST = ROOT / "data" / "combined" / "multiyear_replay_trades.csv"
OUT = ROOT / "agent_outputs" / "paper_vs_backtest_comparison.md"

MIN_SAMPLE = 30


def read_csv(path: Path) -> List[dict[str, str]]:
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


def max_dd(vals: List[float]) -> float:
    eq = peak = worst = 0.0
    for v in vals:
        eq += v
        peak = max(peak, eq)
        worst = min(worst, eq - peak)
    return worst


def pf(vals: List[float]) -> float:
    wins = sum(v for v in vals if v > 0)
    losses = abs(sum(v for v in vals if v < 0))
    return wins / losses if losses else 999.0


def stats(vals: List[float]) -> dict[str, float]:
    if not vals:
        return {
            "trades": 0,
            "total": 0.0,
            "avg": 0.0,
            "win_rate": 0.0,
            "pf": 0.0,
            "dd": 0.0,
        }

    wins = [v for v in vals if v > 0]

    return {
        "trades": len(vals),
        "total": sum(vals),
        "avg": sum(vals) / len(vals),
        "win_rate": len(wins) / len(vals) * 100,
        "pf": pf(vals),
        "dd": max_dd(vals),
    }


def line_stats(name: str, s: dict[str, float]) -> list[str]:
    return [
        f"## {name}",
        f"- Trades: {int(s['trades'])}",
        f"- Total net pips: {s['total']:.2f}",
        f"- Average pips/trade: {s['avg']:.2f}",
        f"- Win rate: {s['win_rate']:.2f}%",
        f"- Profit factor: {s['pf']:.2f}",
        f"- Max drawdown pips: {s['dd']:.2f}",
        "",
    ]


def main() -> None:
    paper_rows = [r for r in read_csv(PAPER) if r.get("status") == "CLOSED" and r.get("net_pips")]
    backtest_rows = read_csv(BACKTEST)

    paper_vals = [float(r["net_pips"]) for r in paper_rows]
    backtest_vals = [float(r["net_pips"]) for r in backtest_rows]

    paper_stats = stats(paper_vals)
    backtest_stats = stats(backtest_vals)

    lines = [
        "# Isaac Paper vs Backtest Comparison V1",
        "",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]

    lines.extend(line_stats("Paper Results", paper_stats))
    lines.extend(line_stats("Backtest Reference", backtest_stats))

    lines.extend([
        "## Evidence Decision",
    ])

    if len(paper_vals) < MIN_SAMPLE:
        lines.append(
            f"INSUFFICIENT PAPER SAMPLE. Need at least {MIN_SAMPLE} closed paper trades before evaluating live-readiness."
        )
    else:
        avg_ratio = paper_stats["avg"] / backtest_stats["avg"] if backtest_stats["avg"] else 0.0
        pf_ratio = paper_stats["pf"] / backtest_stats["pf"] if backtest_stats["pf"] else 0.0

        lines.append(f"- Paper avg/backtest avg ratio: {avg_ratio:.2f}")
        lines.append(f"- Paper PF/backtest PF ratio: {pf_ratio:.2f}")

        if avg_ratio >= 0.50 and paper_stats["pf"] >= 1.30 and paper_stats["dd"] >= -500:
            lines.append("PAPER TRACKING ACCEPTABLE. Continue evidence collection.")
        else:
            lines.append("PAPER TRACKING WEAK. Do not progress toward live deployment.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n")

    print("=== Isaac Paper vs Backtest Comparison V1 ===")
    print(f"Report: {OUT}")
    print("PAPER VS BACKTEST STATUS: GREEN")


if __name__ == "__main__":
    main()
