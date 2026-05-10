# Isaac Quant-FX System State

Status: GREEN

Mode: PAPER_ONLY

Primary data source:
- Dukascopy only

System components:
- Backtest engine
- Optimizer
- Candidate validator
- Risk engine
- Signal scanner
- Paper ledger
- Paper signal bridge
- Exit resolver
- Full replay validator
- Live data ingestion
- Paper live runner
- Daily report
- Scheduler
- Research memory loop
- Multi-year replay
- Multi-year stress test

Locked strategy:
EUR/USD M15 Asia Breakout V2

Rules:
- Asia range: 00:00-05:59 UTC
- Valid Asia range: 12-30 pips
- Entry window: 08:00-09:59 UTC
- Skip Fridays
- Buffer: 1 pip
- Target: 2R
- Max trades: 1 per day
- Cost model: 1.2 pips round-trip

Validated 2025 Replay:
- Trades: 115
- Total net pips: 1094.30
- Average pips/trade: 9.52
- Win rate: 56.52%
- Profit factor: 2.36
- Max drawdown: -67.90

Validated 2021-2025 Multi-Year Replay:
- Candles: 175,008
- Trades: 650
- Total net pips: 4022.60
- Average pips/trade: 6.19
- Win rate: 55.08%
- Profit factor: 1.79
- Max drawdown: -222.30

Multi-Year Yearly Results:
- 2021: +316.00 pips, PF 1.23
- 2022: +820.30 pips, PF 1.77
- 2023: +1184.60 pips, PF 2.11
- 2024: +607.40 pips, PF 1.79
- 2025: +1094.30 pips, PF 2.36

Multi-Year Stress:
- 3.0 pip cost: +2852.60 pips, PF 1.51
- 5.0 pip cost: +1552.60 pips, PF 1.25
- Monte Carlo median DD: -200.50 pips
- Monte Carlo 5% worst DD: -306.20 pips
- Monte Carlo 1% worst DD: -369.50 pips
- Monte Carlo 0.1% worst DD: -472.50 pips

Risk Planning:
- Planning drawdown: 400-500 pips
- Paper size: 0.01-0.05 lots
- No live deployment before 3 months paper validation
- AI may analyze and propose improvements, but must not auto-change live trading logic

Operational Paper Candidate V3:
- Same as V2, plus skip all December trades
- Trades: 594
- Total net pips: 4186.50
- Average pips/trade: 7.05
- Win rate: 56.57%
- Profit factor: 1.94
- Max drawdown: -188.00
- 3.0 pip cost: +3117.30 pips, PF 1.63
- Monte Carlo 0.1% worst DD: -409.20 pips

Current operating rule:
- Use V3 for paper trading
- Keep V2 as historical baseline

Operational Paper Candidate V3:
- Same as V2, plus skip all December trades
- Trades: 594
- Total net pips: 4186.50
- Average pips/trade: 7.05
- Win rate: 56.57%
- Profit factor: 1.94
- Max drawdown: -188.00
- 3.0 pip cost: +3117.30 pips, PF 1.63
- Monte Carlo 0.1% worst DD: -409.20 pips

Current operating rule:
- Use V3 for paper trading
- Keep V2 as historical baseline

Operational Paper Candidate V3:
- Same as V2, plus skip all December trades
- Trades: 594
- Total net pips: 4186.50
- Average pips/trade: 7.05
- Win rate: 56.57%
- Profit factor: 1.94
- Max drawdown: -188.00
- 3.0 pip cost: +3117.30 pips, PF 1.63
- Monte Carlo 0.1% worst DD: -409.20 pips

Current operating rule:
- Use V3 for paper trading
- Keep V2 as historical baseline

Operational Paper Candidate V3:
- Same as V2, plus skip all December trades
- Trades: 594
- Total net pips: 4186.50
- Average pips/trade: 7.05
- Win rate: 56.57%
- Profit factor: 1.94
- Max drawdown: -188.00
- 3.0 pip cost: +3117.30 pips, PF 1.63
- Monte Carlo 0.1% worst DD: -409.20 pips

Current operating rule:
- Use V3 for paper trading
- Keep V2 as historical baseline
