from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path("/home/sami/quant-fx")
MEMORY = ROOT / "memory" / "latest_snapshot.json"
PROJECT_STATE = ROOT / "PROJECT_STATE.md"
DAILY_REPORT = ROOT / "agent_outputs" / "latest_daily_report.md"
AGENT_DIR = ROOT / "agent_outputs"
AGENT_REPORT = AGENT_DIR / "latest_agent_report.md"
AGENT_PROMPT = AGENT_DIR / "latest_llm_prompt.md"
AUDIT = ROOT / "system_audit_v2.sh"

AGENT_DIR.mkdir(parents=True, exist_ok=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(errors="ignore")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def run_cmd(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    return result.returncode, result.stdout + result.stderr


def main() -> None:
    audit_code, audit_out = run_cmd([str(AUDIT)])
    daily_code, daily_out = run_cmd(["python3", "daily_report_v1.py"])

    DAILY_REPORT.write_text(daily_out)

    snapshot = read_json(MEMORY)
    project_state = read_text(PROJECT_STATE)

    audit_green = audit_code == 0 and "SYSTEM STATUS: GREEN" in audit_out
    stats = snapshot.get("stats", {})
    latest_runner = snapshot.get("latest_runner_action")

    report = [
        "# Isaac Local Research Agent V1",
        "",
        f"Generated UTC: {now()}",
        f"Audit green: {audit_green}",
        f"Mode: {snapshot.get('mode', 'UNKNOWN')}",
        f"Strategy: {snapshot.get('strategy', 'UNKNOWN')}",
        "",
        "## Paper Stats",
        f"- Total trades: {stats.get('total_trades', 0)}",
        f"- Open trades: {stats.get('open_trades', 0)}",
        f"- Closed trades: {stats.get('closed_trades', 0)}",
        f"- Total net pips: {stats.get('total_net_pips', 0)}",
        f"- Win rate: {stats.get('win_rate', 0)}%",
        f"- Profit factor: {stats.get('profit_factor', 0)}",
        f"- Max drawdown pips: {stats.get('max_drawdown_pips', 0)}",
        "",
        "## Current Agent Assessment",
    ]

    if not audit_green:
        report.append("- RED: system audit failed. Do not operate paper runner until fixed.")
    elif stats.get("open_trades", 0) > 1:
        report.append("- RED: more than one open trade detected. This violates max-trade discipline.")
    else:
        report.append("- GREEN: system is eligible for paper-only operation.")

    report.extend([
        "",
        "## Latest Runner Action",
        "```json",
        json.dumps(latest_runner, indent=2, sort_keys=True),
        "```",
        "",
        "## Guardrails",
        "- Agent may analyse and write notes.",
        "- Agent may not change strategy config.",
        "- Agent may not execute trades.",
        "- Agent may not approve live deployment.",
        "- Human approval required for all strategy changes.",
    ])

    AGENT_REPORT.write_text("\n".join(report) + "\n")

    prompt = [
        "# Local LLM Research Prompt",
        "",
        "You are a local research analyst for Isaac Quant-FX.",
        "You may analyse the system state and propose research questions.",
        "You must not recommend live deployment unless paper validation requirements are met.",
        "You must not alter strategy rules.",
        "",
        "## Project State",
        "```md",
        project_state,
        "```",
        "",
        "## Latest Memory Snapshot",
        "```json",
        json.dumps(snapshot, indent=2, sort_keys=True),
        "```",
        "",
        "## Latest Daily Report",
        "```text",
        daily_out,
        "```",
        "",
        "Return only:",
        "1. Current risk state",
        "2. Anomalies",
        "3. Next research question",
        "4. Whether human review is needed",
    ]

    AGENT_PROMPT.write_text("\n".join(prompt) + "\n")

    print("=== Isaac Local Research Agent V1 ===")
    print(f"Audit green: {audit_green}")
    print(f"Agent report: {AGENT_REPORT}")
    print(f"LLM prompt: {AGENT_PROMPT}")

    if audit_green:
        print("AGENT STATUS: GREEN")
    else:
        print("AGENT STATUS: RED")


if __name__ == "__main__":
    main()
