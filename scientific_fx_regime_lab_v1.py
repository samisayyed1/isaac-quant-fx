from __future__ import annotations

import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "combined" / "eurusd-m15-bid-2021-01-01-2026-01-01.csv"
TRADES_PATH = ROOT / "data" / "combined" / "multiyear_replay_trades.csv"
OUT_DIR = ROOT / "agent_outputs"
REPORT_PATH = OUT_DIR / "scientific_fx_regime_lab_report.md"
RESULTS_PATH = OUT_DIR / "scientific_fx_regime_lab_results.csv"

PIP_SIZE = 0.0001
ASIA_START_HOUR = 0
ASIA_END_HOUR = 6
ROLLING_DAYS = 20

ACTIONABLE_FAMILIES = {
    "CompressionZ bucket": "COMPRESSION",
    "VolatilityRegime": "VOLATILITY",
    "Weekday": "TIME",
    "Entry hour": "TIME",
    "Month number excluding December": "TIME",
}

DECISION_BY_FAMILY = {
    "COMPRESSION": "REVIEW_COMPRESSION_FILTER",
    "VOLATILITY": "REVIEW_VOLATILITY_FILTER",
    "TIME": "REVIEW_TIME_FILTER",
}


@dataclass(frozen=True)
class Candle:
    ts: datetime
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class DayFeature:
    day: str
    year: str
    month: int
    weekday: str
    asia_range_pips: float
    rolling_median_asia_range: float | None
    rolling_mad_asia_range: float | None
    compression_z: float | None
    compression_bucket: str
    realized_volatility: float
    prior_day_realized_volatility: float | None
    rolling_median_realized_volatility: float | None
    volatility_regime: str


@dataclass(frozen=True)
class TradeRecord:
    day: str
    year: str
    month_num: str
    weekday: str
    entry_hour: str
    side: str
    exit_reason: str
    net_pips: float
    asia_range_pips: float
    rolling_median_asia_range: float | None
    rolling_mad_asia_range: float | None
    compression_z: float | None
    compression_bucket: str
    prior_day_realized_volatility: float | None
    rolling_median_realized_volatility: float | None
    volatility_regime: str


def load_candles_by_day() -> dict[str, list[Candle]]:
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

    for candles in grouped.values():
        candles.sort(key=lambda c: c.ts)

    return dict(sorted(grouped.items()))


def daily_asia_range(candles: list[Candle]) -> float:
    asia = [
        candle for candle in candles
        if ASIA_START_HOUR <= candle.ts.hour < ASIA_END_HOUR
    ]
    if not asia:
        return 0.0
    return (max(c.high for c in asia) - min(c.low for c in asia)) / PIP_SIZE


def daily_realized_volatility(candles: list[Candle]) -> float:
    if len(candles) < 2:
        return 0.0

    total = 0.0
    previous = candles[0].close
    for candle in candles[1:]:
        if previous > 0 and candle.close > 0:
            ret = math.log(candle.close / previous)
            total += ret * ret
        previous = candle.close

    return math.sqrt(total)


def mad(values: list[float], center: float) -> float:
    return median([abs(value - center) for value in values])


def compression_bucket(value: float | None) -> str:
    if value is None:
        return "UNKNOWN"
    if value <= -1.0:
        return "<= -1"
    if value <= 0.0:
        return "-1 to 0"
    if value <= 1.0:
        return "0 to 1"
    return "> 1"


def volatility_regime(prior_rv: float | None, rolling_median_rv: float | None) -> str:
    if prior_rv is None or rolling_median_rv is None or rolling_median_rv <= 0:
        return "UNKNOWN"
    if prior_rv < 0.75 * rolling_median_rv:
        return "LOW"
    if prior_rv > 1.50 * rolling_median_rv:
        return "HIGH"
    return "NORMAL"


def build_day_features(candles_by_day: dict[str, list[Candle]]) -> dict[str, DayFeature]:
    days = list(candles_by_day)
    asia_ranges = [daily_asia_range(candles_by_day[day]) for day in days]
    realized_vols = [daily_realized_volatility(candles_by_day[day]) for day in days]

    features: dict[str, DayFeature] = {}

    for idx, day in enumerate(days):
        candles = candles_by_day[day]
        first = candles[0]

        asia_window = asia_ranges[max(0, idx - ROLLING_DAYS + 1):idx + 1]
        rolling_median_asia = median(asia_window) if asia_window else None
        rolling_mad_asia = (
            mad(asia_window, rolling_median_asia)
            if rolling_median_asia is not None and asia_window
            else None
        )

        compression_z = None
        if rolling_median_asia is not None and rolling_mad_asia is not None and rolling_mad_asia > 1e-12:
            compression_z = (asia_ranges[idx] - rolling_median_asia) / rolling_mad_asia

        prior_rv = realized_vols[idx - 1] if idx > 0 else None
        rv_window = realized_vols[max(0, idx - ROLLING_DAYS):idx]
        rolling_median_rv = median(rv_window) if rv_window else None

        features[day] = DayFeature(
            day=day,
            year=day[:4],
            month=first.ts.month,
            weekday=first.ts.strftime("%A"),
            asia_range_pips=asia_ranges[idx],
            rolling_median_asia_range=rolling_median_asia,
            rolling_mad_asia_range=rolling_mad_asia,
            compression_z=compression_z,
            compression_bucket=compression_bucket(compression_z),
            realized_volatility=realized_vols[idx],
            prior_day_realized_volatility=prior_rv,
            rolling_median_realized_volatility=rolling_median_rv,
            volatility_regime=volatility_regime(prior_rv, rolling_median_rv),
        )

    return features


def load_v3_trades(day_features: dict[str, DayFeature]) -> list[TradeRecord]:
    if not TRADES_PATH.exists():
        raise SystemExit(f"Missing replay trades file: {TRADES_PATH}")

    records: list[TradeRecord] = []

    with TRADES_PATH.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            entry = datetime.fromisoformat(row["entry_time"])
            if entry.month == 12:
                continue

            feature = day_features.get(row["day"])
            if feature is None:
                raise SystemExit(f"Missing day features for trade day: {row['day']}")

            records.append(
                TradeRecord(
                    day=row["day"],
                    year=row["year"],
                    month_num=f"{entry.month:02d}",
                    weekday=entry.strftime("%A"),
                    entry_hour=f"{entry.hour:02d}",
                    side=row["side"],
                    exit_reason=row["reason"],
                    net_pips=float(row["net_pips"]),
                    asia_range_pips=feature.asia_range_pips,
                    rolling_median_asia_range=feature.rolling_median_asia_range,
                    rolling_mad_asia_range=feature.rolling_mad_asia_range,
                    compression_z=feature.compression_z,
                    compression_bucket=feature.compression_bucket,
                    prior_day_realized_volatility=feature.prior_day_realized_volatility,
                    rolling_median_realized_volatility=feature.rolling_median_realized_volatility,
                    volatility_regime=feature.volatility_regime,
                )
            )

    return sorted(records, key=lambda r: (r.day, r.entry_hour))


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


def warning_flags(values: list[float], pf: float, avg: float, dd: float, total: float) -> list[str]:
    flags: list[str] = []
    trades = len(values)

    if trades >= 30 and pf < 1.20:
        flags.append("PF_LT_1_20")
    if trades >= 30 and avg < 2.0:
        flags.append("AVG_LT_2")
    if dd < -250.0:
        flags.append("DD_WORSE_THAN_-250")
    if total < 0.0:
        flags.append("NEGATIVE_TOTAL")

    return flags


def stats_for_group(
    dimension: str,
    group: str,
    records: list[TradeRecord],
) -> dict[str, str]:
    values = [record.net_pips for record in records]
    wins = [value for value in values if value > 0]
    total = sum(values)
    avg = total / len(values) if values else 0.0
    win_rate = len(wins) / len(values) * 100.0 if values else 0.0
    pf = profit_factor(values)
    dd = max_drawdown(values)
    worst = min(values) if values else 0.0
    best = max(values) if values else 0.0
    flags = warning_flags(values, pf, avg, dd, total)

    return {
        "dimension": dimension,
        "group": group,
        "research_family": ACTIONABLE_FAMILIES.get(dimension, "DIAGNOSTIC"),
        "trades": str(len(values)),
        "total_net_pips": f"{total:.2f}",
        "avg_pips_per_trade": f"{avg:.2f}",
        "win_rate_pct": f"{win_rate:.2f}",
        "profit_factor": f"{pf:.2f}",
        "max_drawdown_pips": f"{dd:.2f}",
        "worst_trade_pips": f"{worst:.2f}",
        "best_trade_pips": f"{best:.2f}",
        "warning_flags": ",".join(flags),
    }


def grouped_stats(
    dimension: str,
    records: list[TradeRecord],
    key_fn: Callable[[TradeRecord], str],
) -> list[dict[str, str]]:
    grouped: dict[str, list[TradeRecord]] = defaultdict(list)
    for record in records:
        grouped[key_fn(record)].append(record)

    rows = [
        stats_for_group(dimension, group, grouped[group])
        for group in sorted(grouped)
    ]
    rows.sort(key=lambda row: (row["dimension"], row["group"]))
    return rows


def baseline_stats(records: list[TradeRecord]) -> dict[str, float]:
    values = [record.net_pips for record in records]
    wins = [value for value in values if value > 0]
    return {
        "trades": float(len(values)),
        "total": sum(values),
        "avg": sum(values) / len(values) if values else 0.0,
        "win_rate": len(wins) / len(values) * 100.0 if values else 0.0,
        "pf": profit_factor(values),
        "dd": max_drawdown(values),
        "worst": min(values) if values else 0.0,
        "best": max(values) if values else 0.0,
    }


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


def format_table(rows: list[dict[str, str]]) -> list[str]:
    lines = [
        "| Dimension | Group | Trades | Total | Avg | Win % | PF | Max DD | Worst | Best | Warnings |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['dimension']} | {row['group']} | {row['trades']} | "
            f"{row['total_net_pips']} | {row['avg_pips_per_trade']} | "
            f"{row['win_rate_pct']} | {row['profit_factor']} | "
            f"{row['max_drawdown_pips']} | {row['worst_trade_pips']} | "
            f"{row['best_trade_pips']} | {row['warning_flags'] or '-'} |"
        )
    return lines


def strongest_rows(rows: list[dict[str, str]], limit: int = 10) -> list[dict[str, str]]:
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
    return eligible[:limit]


def weakest_rows(rows: list[dict[str, str]], limit: int = 10) -> list[dict[str, str]]:
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
    return eligible[:limit]


def write_results(rows: list[dict[str, str]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "dimension",
        "group",
        "research_family",
        "trades",
        "total_net_pips",
        "avg_pips_per_trade",
        "win_rate_pct",
        "profit_factor",
        "max_drawdown_pips",
        "worst_trade_pips",
        "best_trade_pips",
        "warning_flags",
    ]
    with RESULTS_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_report(records: list[TradeRecord], rows: list[dict[str, str]]) -> None:
    stats = baseline_stats(records)
    warnings = [row for row in rows if row["warning_flags"]]
    decision = research_decision(rows)

    lines = [
        "# Isaac Scientific FX Regime Lab V1",
        "",
        "Research-only diagnostics for EURUSD_ASIA_BREAKOUT_V3_NO_DECEMBER. No strategy change is authorized by this report.",
        "",
        "## Inputs",
        "",
        f"- M15 data: `{DATA_PATH.relative_to(ROOT)}`",
        f"- Replay trades: `{TRADES_PATH.relative_to(ROOT)}`",
        "- Baseline: current V3 trades, produced by excluding December from the validated multi-year replay trades.",
        "",
        "## Method",
        "",
        "- Asia range uses 00:00-05:59 UTC candles.",
        "- CompressionZ uses current known Asia range against a trailing 20-day median and MAD of Asia ranges.",
        "- Realized volatility uses prior-day M15 close-to-close log returns.",
        "- VolatilityRegime compares prior-day RV with the trailing 20-day median prior RV.",
        "- Decision families are compression, volatility, and time. Side and exit-reason groups are diagnostics only.",
        "",
        "## V3 Baseline",
        "",
        f"- Trades: {int(stats['trades'])}",
        f"- Total net pips: {stats['total']:.2f}",
        f"- Average pips/trade: {stats['avg']:.2f}",
        f"- Win rate: {stats['win_rate']:.2f}%",
        f"- Profit factor: {stats['pf']:.2f}",
        f"- Max drawdown: {stats['dd']:.2f}",
        f"- Worst trade: {stats['worst']:.2f}",
        f"- Best trade: {stats['best']:.2f}",
        "",
        "## Research Decision",
        "",
        f"- Decision: {decision}",
        "- No strategy change authorized.",
        "",
        "## Regime Warnings",
        "",
    ]

    if warnings:
        lines.extend(format_table(warnings))
    else:
        lines.append("No warning groups found.")

    lines.extend([
        "",
        "## Strongest Regimes",
        "",
        *format_table(strongest_rows(rows)),
        "",
        "## Weakest Regimes",
        "",
        *format_table(weakest_rows(rows)),
        "",
        "## Full Group Results",
        "",
        *format_table(rows),
        "",
        "## Output Files",
        "",
        f"- Results CSV: `{RESULTS_PATH.relative_to(ROOT)}`",
        f"- Report: `{REPORT_PATH.relative_to(ROOT)}`",
    ])

    REPORT_PATH.write_text("\n".join(lines) + "\n")


def build_group_rows(records: list[TradeRecord]) -> list[dict[str, str]]:
    dimensions: list[tuple[str, Callable[[TradeRecord], str]]] = [
        ("CompressionZ bucket", lambda r: r.compression_bucket),
        ("VolatilityRegime", lambda r: r.volatility_regime),
        ("Weekday", lambda r: r.weekday),
        ("Entry hour", lambda r: r.entry_hour),
        ("Year", lambda r: r.year),
        ("Month number excluding December", lambda r: r.month_num),
        ("Side", lambda r: r.side),
        ("Exit reason", lambda r: r.exit_reason),
    ]

    rows: list[dict[str, str]] = []
    for dimension, key_fn in dimensions:
        rows.extend(grouped_stats(dimension, records, key_fn))
    return rows


def main() -> None:
    day_features = build_day_features(load_candles_by_day())
    records = load_v3_trades(day_features)
    rows = build_group_rows(records)

    write_results(rows)
    write_report(records, rows)

    print("=== Isaac Scientific FX Regime Lab V1 ===")
    print(f"V3 trades analyzed: {len(records)}")
    print(f"Results: {RESULTS_PATH}")
    print(f"Report: {REPORT_PATH}")
    print(f"Research decision: {research_decision(rows)}")
    print("No strategy change authorized.")
    print("SCIENTIFIC FX REGIME LAB STATUS: GREEN")


if __name__ == "__main__":
    main()
