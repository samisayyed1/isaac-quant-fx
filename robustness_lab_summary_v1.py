from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
RESULTS_CSV = ROOT / "agent_outputs" / "robustness_lab_results.csv"


def read_rows() -> list[dict[str, str]]:
    if not RESULTS_CSV.exists():
        raise SystemExit(f"Missing robustness results: {RESULTS_CSV}. Run robustness_lab_v1.py first.")

    with RESULTS_CSV.open() as f:
        return list(csv.DictReader(f))


def f(row: dict[str, str], key: str) -> float:
    return float(row[key])


def b(row: dict[str, str], key: str) -> bool:
    return row[key].strip().lower() == "true"


def decision(current: dict[str, str], nearby_dominators: list[dict[str, str]]) -> str:
    if (
        int(current["trades"]) < 250
        or f(current, "profit_factor") < 1.30
        or int(current["positive_years"]) < 3
        or f(current, "cost_5_total_net_pips") <= 0
    ):
        return "REJECT_STRATEGY"

    if nearby_dominators and f(nearby_dominators[0], "score") >= f(current, "score") + 10.0:
        return "REVIEW_ALTERNATIVE"

    return "KEEP_V3"


def print_row(prefix: str, row: dict[str, Any]) -> None:
    print(
        f"{prefix} rank={row['rank']} score={f(row, 'score'):.2f} "
        f"id={row['variant_id']} trades={row['trades']} "
        f"total={f(row, 'total_net_pips'):.2f} pf={f(row, 'profit_factor'):.2f} "
        f"avg={f(row, 'avg_pips_per_trade'):.2f} dd={f(row, 'max_drawdown_pips'):.2f} "
        f"years={row['positive_years']} cost3={f(row, 'cost_3_total_net_pips'):.2f} "
        f"cost5={f(row, 'cost_5_total_net_pips'):.2f}"
    )


def main() -> None:
    rows = read_rows()
    rows.sort(key=lambda row: int(row["rank"]))

    current = next(row for row in rows if b(row, "is_current_v3"))
    nearby = [row for row in rows if b(row, "near_current_v3")]
    nearby_dominators = [row for row in nearby if b(row, "dominates_current_v3")]
    lab_decision = decision(current, nearby_dominators)

    print("=== Isaac Robustness Lab Summary V1 ===")
    print(f"Results: {RESULTS_CSV}")
    print("")

    print("Top 10 variants:")
    for row in rows[:10]:
        print_row("-", row)

    print("")
    print("Current V3 row:")
    print_row("-", current)

    print("")
    print("Strongest nearby alternatives:")
    for row in nearby[:10]:
        marker = "dominates_v3" if b(row, "dominates_current_v3") else "nearby"
        print_row(f"- {marker}", row)

    print("")
    print(f"Nearby strict dominators: {len(nearby_dominators)}")
    print(f"Isaac decision: {lab_decision}")
    print("No strategy change is authorized by this report.")


if __name__ == "__main__":
    main()
