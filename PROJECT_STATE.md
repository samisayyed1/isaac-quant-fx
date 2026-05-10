# Isaac Quant-FX System State

Status: GREEN

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
- System audit

Locked strategy:
EUR/USD M15 Asia Breakout V2

Rules:
- Asia range: 00:00–05:59 UTC
- Valid Asia range: 12–30 pips
- Entry window: 08:00–09:59 UTC
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

Risk Planning:
- Monte Carlo planning drawdown: 200–250 pips
- Paper size: 0.01–0.05 lots
- No live deployment before 3 months paper validation
