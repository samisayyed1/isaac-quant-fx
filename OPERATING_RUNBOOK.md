# Isaac Quant-FX Operating Runbook

## Current Mode

- Mode: PAPER_ONLY
- Active strategy: EURUSD_ASIA_BREAKOUT_V3_NO_DECEMBER
- Primary data source: Dukascopy

## Scheduled Cadence

Paper runner cadence:

```cron
*/15 8-14 * * 1-4 scheduled_paper_run_v1.sh
```

AI research loop cadence:

```cron
15 15 * * 1-4 ai_research_loop_v1.sh
```

Weekly review cadence:

```cron
30 15 * * 5 operating_review_v1.sh
```

## Manual Daily Check

Run these commands from the repository root:

```bash
git status
crontab -l
python3 daily_report_v1.py
python3 deployment_gate_checklist_v1.py
```

## Manual Live Paper Cycle

Run this cycle only in paper mode:

```bash
python3 paper_live_runner_v2.py --lot 0.01
python3 daily_report_v1.py
python3 weekly_paper_evidence_report_v1.py
```

## Expected Outside-Window Result

When the latest candle is outside the active entry window, the expected result is:

- Signal: OUTSIDE_WINDOW
- No trade opened
- System green

## First Real Signal Review

If `LONG_TRIGGERED` or `SHORT_TRIGGERED` appears, do not change strategy.

Review:

- Paper ledger
- Runner log
- Latest candle
- Entry
- Stop
- Target
- Exit resolver behavior

## Live Account Rule

Live trading is prohibited until `deployment_gate_checklist_v1.py` passes.
