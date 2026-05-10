from __future__ import annotations

ACCOUNT_BALANCE = 10_000.00
RISK_PER_TRADE_PCT = 0.50
MAX_DAILY_LOSS_PCT = 1.00
MAX_WEEKLY_LOSS_PCT = 3.00
MC_WORST_DD_PIPS = 250.0

PIP_VALUE_PER_STANDARD_LOT = 10.0  # EUR/USD approx: $10 per pip per 1.00 lot

risk_per_trade_usd = ACCOUNT_BALANCE * (RISK_PER_TRADE_PCT / 100)
max_daily_loss_usd = ACCOUNT_BALANCE * (MAX_DAILY_LOSS_PCT / 100)
max_weekly_loss_usd = ACCOUNT_BALANCE * (MAX_WEEKLY_LOSS_PCT / 100)

# Conservative assumption: strategy can suffer 250 pip sequence drawdown.
# Size so that 250 pips does not exceed weekly loss budget.
lot_size_by_mc_dd = max_weekly_loss_usd / (MC_WORST_DD_PIPS * PIP_VALUE_PER_STANDARD_LOT)

print("=== Risk Engine V1 ===")
print(f"Account balance: ${ACCOUNT_BALANCE:,.2f}")
print(f"Risk per trade: {RISK_PER_TRADE_PCT:.2f}% = ${risk_per_trade_usd:.2f}")
print(f"Max daily loss: {MAX_DAILY_LOSS_PCT:.2f}% = ${max_daily_loss_usd:.2f}")
print(f"Max weekly loss: {MAX_WEEKLY_LOSS_PCT:.2f}% = ${max_weekly_loss_usd:.2f}")
print(f"Monte Carlo planning DD: {MC_WORST_DD_PIPS:.1f} pips")
print(f"Max safe lot size by MC DD: {lot_size_by_mc_dd:.2f} lots")
print("")
print("Isaac rule:")
print("- Start paper trading at 0.01 to 0.05 lots only.")
print("- No live deployment until 3 months paper results match backtest behavior.")
print("- Stop trading for the day after daily loss limit.")
print("- Stop trading for the week after weekly loss limit.")
