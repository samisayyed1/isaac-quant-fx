from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "combined" / "eurusd-m15-bid-2021-01-01-2026-01-01.csv"
OUT_DIR = ROOT / "agent_outputs"
RESULTS_CSV = OUT_DIR / "robustness_lab_results.csv"
REPORT_MD = OUT_DIR / "robustness_lab_report.md"

YEARS = ("2021", "2022", "2023", "2024", "2025")

PIP_SIZE = 0.0001
BASE_COST_PIPS = 1.2
ASIA_START_HOUR = 0
ASIA_END_HOUR = 6
EXIT_HOUR = 14
SKIP_FRIDAY = True
SKIP_DECEMBER = True

MIN_RANGE_GRID = (10.0, 12.0, 14.0, 16.0)
MAX_RANGE_GRID = (24.0, 28.0, 30.0, 34.0, 38.0)
BUFFER_GRID = (0.5, 1.0, 1.5, 2.0)
TARGET_R_GRID = (1.5, 2.0, 2.5)
ENTRY_HOUR_GRID = (
    ("A_8_ONLY", (8,)),
    ("B_8_9", (8, 9)),
    ("C_8_9_10", (8, 9, 10)),
)

CURRENT_V3 = {
    "min_range_pips": 12.0,
    "max_range_pips": 30.0,
    "buffer_pips": 1.0,
    "target_r": 2.0,
    "entry_label": "B_8_9",
}


@dataclass(frozen=True)
class Candle:
    ts: datetime
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class DayCandles:
    day: str
    year: str
    month: int
    weekday: str
    candles: tuple[Candle, ...]


@dataclass(frozen=True)
class Variant:
    min_range_pips: float
    max_range_pips: float
    buffer_pips: float
    target_r: float
    entry_label: str
    entry_hours: tuple[int, ...]

    @property
    def variant_id(self) -> str:
        hours = "-".join(str(h) for h in self.entry_hours)
        return (
            f"min{self.min_range_pips:g}_max{self.max_range_pips:g}_"
            f"buf{self.buffer_pips:g}_r{self.target_r:g}_h{hours}"
        )


def load_days() -> list[DayCandles]:
    if not DATA_PATH.exists():
        raise SystemExit(f"Missing data file: {DATA_PATH}")

    grouped: dict[str, list[Candle]] = defaultdict(list)

    with DATA_PATH.open() as f:
        reader = csv.DictReader(f)
        required = {"timestamp", "open", "high", "low", "close"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise SystemExit(f"CSV missing required columns: {required}")

        for row in reader:
            candle = Candle(
                ts=datetime.fromtimestamp(int(row["timestamp"]) / 1000, tz=timezone.utc),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
            )
            grouped[candle.ts.date().isoformat()].append(candle)

    days = []
    for day, candles in sorted(grouped.items()):
        candles = sorted(candles, key=lambda c: c.ts)
        first = candles[0]
        days.append(
            DayCandles(
                day=day,
                year=day[:4],
                month=first.ts.month,
                weekday=first.ts.strftime("%A"),
                candles=tuple(candles),
            )
        )

    return days


def pips(value: float) -> float:
    return value / PIP_SIZE


def max_drawdown(values: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    worst = 0.0

    for value in values:
        equity += value
        peak = max(peak, equity)
        worst = min(worst, equity - peak)

    return worst


def profit_factor(values: list[float]) -> float:
    wins = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))

    if losses == 0:
        return 999.0 if wins > 0 else 0.0

    return wins / losses


def replay_variant(days: Iterable[DayCandles], variant: Variant) -> list[tuple[str, float]]:
    trades: list[tuple[str, float]] = []
    entry_hours = set(variant.entry_hours)

    for day in days:
        if SKIP_FRIDAY and day.weekday == "Friday":
            continue

        if SKIP_DECEMBER and day.month == 12:
            continue

        asia = [
            candle for candle in day.candles
            if ASIA_START_HOUR <= candle.ts.hour < ASIA_END_HOUR
        ]
        entry_window = [candle for candle in day.candles if candle.ts.hour in entry_hours]

        if len(asia) < 16 or not entry_window:
            continue

        asia_high = max(candle.high for candle in asia)
        asia_low = min(candle.low for candle in asia)
        asia_range = pips(asia_high - asia_low)

        if not (variant.min_range_pips <= asia_range <= variant.max_range_pips):
            continue

        long_entry = asia_high + variant.buffer_pips * PIP_SIZE
        short_entry = asia_low - variant.buffer_pips * PIP_SIZE
        long_stop = asia_low - variant.buffer_pips * PIP_SIZE
        short_stop = asia_high + variant.buffer_pips * PIP_SIZE
        long_target = long_entry + variant.target_r * (long_entry - long_stop)
        short_target = short_entry - variant.target_r * (short_stop - short_entry)

        for candle in entry_window:
            long_trigger = candle.high >= long_entry
            short_trigger = candle.low <= short_entry

            if long_trigger and short_trigger:
                continue

            if long_trigger:
                side = "LONG"
                entry = long_entry
                stop = long_stop
                target = long_target
            elif short_trigger:
                side = "SHORT"
                entry = short_entry
                stop = short_stop
                target = short_target
            else:
                continue

            future = [
                future_candle for future_candle in day.candles
                if candle.ts <= future_candle.ts and future_candle.ts.hour < EXIT_HOUR
            ]
            if not future:
                continue

            exit_price = None

            for future_candle in future:
                if side == "LONG":
                    hit_stop = future_candle.low <= stop
                    hit_target = future_candle.high >= target
                else:
                    hit_stop = future_candle.high >= stop
                    hit_target = future_candle.low <= target

                if hit_stop and hit_target:
                    exit_price = stop
                elif hit_stop:
                    exit_price = stop
                elif hit_target:
                    exit_price = target

                if exit_price is not None:
                    break

            if exit_price is None:
                exit_price = future[-1].close

            gross_pips = (
                pips(exit_price - entry)
                if side == "LONG"
                else pips(entry - exit_price)
            )
            trades.append((day.year, gross_pips - BASE_COST_PIPS))
            break

    return trades


def cost_stress_total(values: list[float], cost_pips: float) -> float:
    gross = [value + BASE_COST_PIPS for value in values]
    return sum(value - cost_pips for value in gross)


def largest_year_share(yearly: dict[str, float], total_net: float) -> float:
    if total_net <= 0:
        return 999.0
    return max(yearly.values()) / total_net


def score_row(row: dict[str, float | int | str | bool]) -> float:
    trades = int(row["trades"])
    total = float(row["total_net_pips"])
    avg = float(row["avg_pips_per_trade"])
    pf = float(row["profit_factor"])
    max_dd = float(row["max_drawdown_pips"])
    positive_years = int(row["positive_years"])
    cost_3 = float(row["cost_3_total_net_pips"])
    cost_5 = float(row["cost_5_total_net_pips"])
    dependency = float(row["largest_year_share"])

    score = 0.0
    score += min(max((pf - 1.0) * 80.0, 0.0), 100.0)
    score += min(max(avg, 0.0) * 6.0, 80.0)
    score += positive_years * 25.0
    score += max(0.0, 75.0 + max_dd / 4.0)
    score += min(max(cost_3, 0.0) / 60.0, 50.0)
    score += min(max(cost_5, 0.0) / 40.0, 50.0)
    score += min(trades / 10.0, 50.0)

    if trades < 250:
        score -= (250 - trades) * 0.5
    if positive_years < len(YEARS):
        score -= (len(YEARS) - positive_years) * 50.0
    if max_dd < -500.0:
        score -= 100.0 + (abs(max_dd) - 500.0) / 2.0
    if pf < 1.30:
        score -= 100.0 + (1.30 - pf) * 100.0
    if dependency > 0.45:
        score -= min((dependency - 0.45) * 200.0, 150.0)
    if total <= 0:
        score -= 200.0

    return score


def build_row(variant: Variant, trades: list[tuple[str, float]]) -> dict[str, float | int | str | bool]:
    values = [value for _, value in trades]
    yearly = {year: 0.0 for year in YEARS}
    for year, value in trades:
        if year in yearly:
            yearly[year] += value

    wins = [value for value in values if value > 0]
    total = sum(values)
    avg = total / len(values) if values else 0.0
    win_rate = len(wins) / len(values) * 100.0 if values else 0.0
    pf = profit_factor(values)
    dd = max_drawdown(values)
    positive_years = sum(1 for value in yearly.values() if value > 0)
    worst_year = min(yearly.values()) if yearly else 0.0

    row: dict[str, float | int | str | bool] = {
        "rank": 0,
        "score": 0.0,
        "variant_id": variant.variant_id,
        "is_current_v3": is_current_v3(variant),
        "near_current_v3": False,
        "dominates_current_v3": False,
        "entry_label": variant.entry_label,
        "entry_hours": ",".join(str(hour) for hour in variant.entry_hours),
        "min_range_pips": variant.min_range_pips,
        "max_range_pips": variant.max_range_pips,
        "buffer_pips": variant.buffer_pips,
        "target_r": variant.target_r,
        "skip_december": SKIP_DECEMBER,
        "skip_friday": SKIP_FRIDAY,
        "trades": len(values),
        "total_net_pips": total,
        "avg_pips_per_trade": avg,
        "win_rate_pct": win_rate,
        "profit_factor": pf,
        "max_drawdown_pips": dd,
        "positive_years": positive_years,
        "worst_year_net_pips": worst_year,
        "cost_3_total_net_pips": cost_stress_total(values, 3.0),
        "cost_5_total_net_pips": cost_stress_total(values, 5.0),
        "largest_year_share": largest_year_share(yearly, total),
    }

    for year in YEARS:
        row[f"year_{year}_net_pips"] = yearly[year]

    row["score"] = score_row(row)
    return row


def is_current_v3(variant: Variant) -> bool:
    return (
        variant.min_range_pips == CURRENT_V3["min_range_pips"]
        and variant.max_range_pips == CURRENT_V3["max_range_pips"]
        and variant.buffer_pips == CURRENT_V3["buffer_pips"]
        and variant.target_r == CURRENT_V3["target_r"]
        and variant.entry_label == CURRENT_V3["entry_label"]
    )


def is_near_current(row: dict[str, float | int | str | bool]) -> bool:
    return (
        not bool(row["is_current_v3"])
        and abs(float(row["min_range_pips"]) - float(CURRENT_V3["min_range_pips"])) <= 2.0
        and abs(float(row["max_range_pips"]) - float(CURRENT_V3["max_range_pips"])) <= 4.0
        and abs(float(row["buffer_pips"]) - float(CURRENT_V3["buffer_pips"])) <= 0.5
        and abs(float(row["target_r"]) - float(CURRENT_V3["target_r"])) <= 0.5
    )


def dominates(row: dict[str, float | int | str | bool], current: dict[str, float | int | str | bool]) -> bool:
    checks = [
        float(row["score"]) > float(current["score"]),
        float(row["total_net_pips"]) >= float(current["total_net_pips"]),
        float(row["avg_pips_per_trade"]) >= float(current["avg_pips_per_trade"]),
        float(row["profit_factor"]) >= float(current["profit_factor"]),
        float(row["max_drawdown_pips"]) >= float(current["max_drawdown_pips"]),
        int(row["positive_years"]) >= int(current["positive_years"]),
        float(row["cost_3_total_net_pips"]) >= float(current["cost_3_total_net_pips"]),
        float(row["cost_5_total_net_pips"]) >= float(current["cost_5_total_net_pips"]),
    ]
    strict = [
        float(row["total_net_pips"]) > float(current["total_net_pips"]),
        float(row["profit_factor"]) > float(current["profit_factor"]),
        float(row["max_drawdown_pips"]) > float(current["max_drawdown_pips"]),
        float(row["cost_5_total_net_pips"]) > float(current["cost_5_total_net_pips"]),
    ]
    return all(checks) and any(strict)


def variants() -> Iterable[Variant]:
    for min_range, max_range, buffer, target_r, entry in product(
        MIN_RANGE_GRID,
        MAX_RANGE_GRID,
        BUFFER_GRID,
        TARGET_R_GRID,
        ENTRY_HOUR_GRID,
    ):
        entry_label, entry_hours = entry
        if min_range > max_range:
            continue
        yield Variant(
            min_range_pips=min_range,
            max_range_pips=max_range,
            buffer_pips=buffer,
            target_r=target_r,
            entry_label=entry_label,
            entry_hours=entry_hours,
        )


def fmt(value: float | int | str | bool) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def write_results(rows: list[dict[str, float | int | str | bool]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "rank",
        "score",
        "variant_id",
        "is_current_v3",
        "near_current_v3",
        "dominates_current_v3",
        "entry_label",
        "entry_hours",
        "min_range_pips",
        "max_range_pips",
        "buffer_pips",
        "target_r",
        "skip_december",
        "skip_friday",
        "trades",
        "total_net_pips",
        "avg_pips_per_trade",
        "win_rate_pct",
        "profit_factor",
        "max_drawdown_pips",
        *[f"year_{year}_net_pips" for year in YEARS],
        "positive_years",
        "worst_year_net_pips",
        "cost_3_total_net_pips",
        "cost_5_total_net_pips",
        "largest_year_share",
    ]

    with RESULTS_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: fmt(row[key]) for key in fieldnames})


def decision(current: dict[str, float | int | str | bool], nearby_dominators: list[dict[str, float | int | str | bool]]) -> str:
    if (
        int(current["trades"]) < 250
        or float(current["profit_factor"]) < 1.30
        or int(current["positive_years"]) < 3
        or float(current["cost_5_total_net_pips"]) <= 0
    ):
        return "REJECT_STRATEGY"

    if nearby_dominators and float(nearby_dominators[0]["score"]) >= float(current["score"]) + 10.0:
        return "REVIEW_ALTERNATIVE"

    return "KEEP_V3"


def table(rows: list[dict[str, float | int | str | bool]]) -> list[str]:
    lines = [
        "| Rank | Variant | Score | Trades | Total | PF | Avg | DD | +Years | Cost 3 | Cost 5 |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['rank']} | {row['variant_id']} | {float(row['score']):.2f} | "
            f"{row['trades']} | {float(row['total_net_pips']):.2f} | "
            f"{float(row['profit_factor']):.2f} | {float(row['avg_pips_per_trade']):.2f} | "
            f"{float(row['max_drawdown_pips']):.2f} | {row['positive_years']} | "
            f"{float(row['cost_3_total_net_pips']):.2f} | "
            f"{float(row['cost_5_total_net_pips']):.2f} |"
        )
    return lines


def write_report(rows: list[dict[str, float | int | str | bool]]) -> None:
    current = next(row for row in rows if row["is_current_v3"])
    nearby = [row for row in rows if row["near_current_v3"]]
    nearby_dominators = [row for row in nearby if row["dominates_current_v3"]]
    lab_decision = decision(current, nearby_dominators)

    if lab_decision == "REJECT_STRATEGY":
        robustness = "FRAGILE"
        change_text = "Reject live progression and continue research. Do not change strategy automatically."
    elif lab_decision == "REVIEW_ALTERNATIVE":
        robustness = "ROBUST BUT CHALLENGED"
        change_text = "Nearby variants dominate V3. Consider only human-reviewed follow-up validation."
    else:
        robustness = "ROBUST"
        change_text = "Reject automatic changes. Keep V3 unless separate human-approved validation begins."

    lines = [
        "# Isaac Robustness Lab V1",
        "",
        "This is a robustness and anti-overfit validation report, not an optimizer.",
        "",
        "## Scope",
        "",
        f"- Data: `{DATA_PATH.relative_to(ROOT)}`",
        "- Base V3: skip Friday, skip December, Asia 00:00-05:59 UTC, entry 08:00-09:59 UTC, range 12-30 pips, buffer 1 pip, target 2R, cost 1.2 pips",
        "- Variant grid: min range 10/12/14/16, max range 24/28/30/34/38, buffer 0.5/1.0/1.5/2.0, target R 1.5/2.0/2.5, entry hours A/B/C",
        "- Fixed filters in this run: skip Friday true, skip December true",
        "- Guardrail: strategy changes require human review and separate validation.",
        "",
        "## Current V3",
        "",
        f"- Rank: {current['rank']} of {len(rows)}",
        f"- Score: {float(current['score']):.2f}",
        f"- Trades: {current['trades']}",
        f"- Total net pips: {float(current['total_net_pips']):.2f}",
        f"- Average pips/trade: {float(current['avg_pips_per_trade']):.2f}",
        f"- Win rate: {float(current['win_rate_pct']):.2f}%",
        f"- Profit factor: {float(current['profit_factor']):.2f}",
        f"- Max drawdown: {float(current['max_drawdown_pips']):.2f}",
        f"- Positive years: {current['positive_years']} of {len(YEARS)}",
        f"- Worst year net pips: {float(current['worst_year_net_pips']):.2f}",
        f"- 3.0 pip cost total: {float(current['cost_3_total_net_pips']):.2f}",
        f"- 5.0 pip cost total: {float(current['cost_5_total_net_pips']):.2f}",
        "",
        "## Top 10 Variants",
        "",
        *table(rows[:10]),
        "",
        "## Nearby Alternatives",
        "",
        *table(nearby[:10]),
        "",
        "## Dominance Check",
        "",
        f"- Nearby variants that strictly dominate current V3: {len(nearby_dominators)}",
        f"- Robustness verdict: {robustness}",
        f"- Isaac decision: {lab_decision}",
        f"- Change policy: {change_text}",
        "",
        "## Output Files",
        "",
        f"- Results CSV: `{RESULTS_CSV.relative_to(ROOT)}`",
        f"- Report: `{REPORT_MD.relative_to(ROOT)}`",
    ]

    REPORT_MD.write_text("\n".join(lines) + "\n")


def main() -> None:
    days = load_days()
    rows = [build_row(variant, replay_variant(days, variant)) for variant in variants()]
    rows.sort(
        key=lambda row: (
            float(row["score"]),
            float(row["profit_factor"]),
            float(row["total_net_pips"]),
            int(row["positive_years"]),
        ),
        reverse=True,
    )

    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank

    current = next(row for row in rows if row["is_current_v3"])
    for row in rows:
        row["near_current_v3"] = is_near_current(row)
        row["dominates_current_v3"] = bool(row["near_current_v3"]) and dominates(row, current)

    write_results(rows)
    write_report(rows)

    print("=== Isaac Robustness Lab V1 ===")
    print(f"Variants tested: {len(rows)}")
    print(f"Current V3 rank: {current['rank']} of {len(rows)}")
    print(f"Report: {REPORT_MD}")
    print(f"Results: {RESULTS_CSV}")
    print("ROBUSTNESS LAB STATUS: GREEN")


if __name__ == "__main__":
    main()
