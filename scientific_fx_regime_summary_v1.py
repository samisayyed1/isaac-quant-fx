from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS_PATH = ROOT / "agent_outputs" / "scientific_fx_regime_lab_results.csv"

DECISION_BY_FAMILY = {
    "COMPRESSION": "REVIEW_COMPRESSION_FILTER",
    "VOLATILITY": "REVIEW_VOLATILITY_FILTER",
    "TIME": "REVIEW_TIME_FILTER",
}


def read_rows() -> list[dict[str, str]]:
    if not RESULTS_PATH.exists():
        raise SystemExit(f"Missing regime lab results: {RESULTS_PATH}. Run scientific_fx_regime_lab_v1.py first.")

    with RESULTS_PATH.open() as f:
        return list(csv.DictReader(f))


def research_decision(rows: list[dict[str, str]]) -> str:
    families = {
        row["research_family"]
        for row in rows
        if row["warning_flags"] and row["research_family"] in {"COMPRESSION", "VOLATILITY", "TIME"}
    }

    if not families:
        return "KEEP_V3_NO_CHANGE"
    if len(families) > 1:
        return "REVIEW_MULTIPLE_FILTERS"
    return DECISION_BY_FAMILY[next(iter(families))]


def print_row(prefix: str, row: dict[str, str]) -> None:
    warnings = row["warning_flags"] or "-"
    print(
        f"{prefix} {row['dimension']}={row['group']} "
        f"trades={row['trades']} total={float(row['total_net_pips']):.2f} "
        f"avg={float(row['avg_pips_per_trade']):.2f} "
        f"pf={float(row['profit_factor']):.2f} "
        f"dd={float(row['max_drawdown_pips']):.2f} "
        f"worst={float(row['worst_trade_pips']):.2f} "
        f"best={float(row['best_trade_pips']):.2f} "
        f"warnings={warnings}"
    )


def strongest(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    eligible = [
        row for row in rows
        if row["dimension"] != "Exit reason" and int(row["trades"]) >= 20
    ]
    eligible.sort(
        key=lambda row: (
            float(row["profit_factor"]),
            float(row["avg_pips_per_trade"]),
            float(row["total_net_pips"]),
        ),
        reverse=True,
    )
    return eligible[:10]


def weakest(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    eligible = [
        row for row in rows
        if row["dimension"] != "Exit reason" and int(row["trades"]) >= 20
    ]
    eligible.sort(
        key=lambda row: (
            float(row["total_net_pips"]),
            float(row["avg_pips_per_trade"]),
            float(row["profit_factor"]),
        )
    )
    return eligible[:10]


def main() -> None:
    rows = read_rows()
    warnings = [row for row in rows if row["warning_flags"]]
    decision = research_decision(rows)

    print("=== Isaac Scientific FX Regime Summary V1 ===")
    print(f"Results: {RESULTS_PATH}")
    print("")

    print("Strongest regimes:")
    for row in strongest(rows):
        print_row("-", row)

    print("")
    print("Weakest regimes:")
    for row in weakest(rows):
        print_row("-", row)

    print("")
    print("Warning groups:")
    if warnings:
        for row in warnings:
            print_row("-", row)
    else:
        print("- none")

    print("")
    print(f"Final research decision: {decision}")
    print("No strategy change authorized.")


if __name__ == "__main__":
    main()
