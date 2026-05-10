from __future__ import annotations

from strategy_config_v1 import BASELINE_STRATEGY_V2, OPERATIONAL_STRATEGY


def describe(name: str, cfg) -> None:
    print(f"=== {name} ===")
    print(f"Name: {cfg.name}")
    print(f"Pair: {cfg.pair}")
    print(f"Timeframe: {cfg.timeframe}")
    print(f"Asia window UTC: {cfg.asia_start_hour:02d}:00-{cfg.asia_end_hour - 1:02d}:59")
    print(f"Entry hours UTC: {sorted(cfg.entry_hours)}")
    print(f"Exit hour UTC: {cfg.exit_hour}")
    print(f"Range filter: {cfg.min_asia_range_pips}-{cfg.max_asia_range_pips} pips")
    print(f"Buffer: {cfg.buffer_pips} pip")
    print(f"Target: {cfg.target_r}R")
    print(f"Round-trip cost: {cfg.round_trip_cost_pips} pips")
    print(f"Skip Friday: {cfg.skip_friday}")
    print(f"Skip December: {cfg.skip_december}")
    print(f"Max paper lot: {cfg.max_paper_lot}")
    print("")


def main() -> None:
    print("=== Isaac Strategy Config Audit V1 ===")
    describe("Operational Strategy", OPERATIONAL_STRATEGY)
    describe("Baseline Strategy", BASELINE_STRATEGY_V2)

    assert OPERATIONAL_STRATEGY.skip_december is True
    assert BASELINE_STRATEGY_V2.skip_december is False
    assert OPERATIONAL_STRATEGY.entry_hours == frozenset({8, 9})
    assert OPERATIONAL_STRATEGY.max_paper_lot == 0.05

    print("CONFIG STATUS: GREEN")


if __name__ == "__main__":
    main()
