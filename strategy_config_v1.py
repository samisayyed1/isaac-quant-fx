from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    pair: str
    timeframe: str
    pip_size: float
    round_trip_cost_pips: float

    asia_start_hour: int
    asia_end_hour: int
    entry_hours: FrozenSet[int]
    exit_hour: int

    min_asia_range_pips: float
    max_asia_range_pips: float
    buffer_pips: float
    target_r: float

    skip_friday: bool
    skip_december: bool
    max_trades_per_day: int
    max_paper_lot: float


OPERATIONAL_STRATEGY = StrategyConfig(
    name="EURUSD_ASIA_BREAKOUT_V3_NO_DECEMBER",
    pair="EUR/USD",
    timeframe="M15",
    pip_size=0.0001,
    round_trip_cost_pips=1.2,

    asia_start_hour=0,
    asia_end_hour=6,
    entry_hours=frozenset({8, 9}),
    exit_hour=14,

    min_asia_range_pips=12.0,
    max_asia_range_pips=30.0,
    buffer_pips=1.0,
    target_r=2.0,

    skip_friday=True,
    skip_december=True,
    max_trades_per_day=1,
    max_paper_lot=0.05,
)


BASELINE_STRATEGY_V2 = StrategyConfig(
    name="EURUSD_ASIA_BREAKOUT_V2_BASELINE",
    pair="EUR/USD",
    timeframe="M15",
    pip_size=0.0001,
    round_trip_cost_pips=1.2,

    asia_start_hour=0,
    asia_end_hour=6,
    entry_hours=frozenset({8, 9}),
    exit_hour=14,

    min_asia_range_pips=12.0,
    max_asia_range_pips=30.0,
    buffer_pips=1.0,
    target_r=2.0,

    skip_friday=True,
    skip_december=False,
    max_trades_per_day=1,
    max_paper_lot=0.05,
)
