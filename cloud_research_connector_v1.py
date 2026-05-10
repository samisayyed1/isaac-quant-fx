from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path("/home/sami/quant-fx")
PROMPT = ROOT / "agent_outputs" / "latest_llm_prompt.md"
OUT_DIR = ROOT / "agent_outputs"
OUT_JSON = OUT_DIR / "latest_cloud_research_note.json"
OUT_MD = OUT_DIR / "latest_cloud_research_note.md"

MODEL = "gpt-4.1-mini"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_output_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str) and data["output_text"].strip():
        return data["output_text"].strip()

    chunks: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                chunks.append(content.get("text", ""))

    return "\n".join(chunks).strip()


def call_openai(prompt: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Missing OPENAI_API_KEY environment variable.")

    payload = {
        "model": MODEL,
        "input": prompt,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "isaac_research_note",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "current_risk_state": {"type": "string"},
                        "anomalies": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "next_research_question": {"type": "string"},
                        "human_review_needed": {"type": "boolean"},
                        "forbidden_actions_confirmed": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "current_risk_state",
                        "anomalies",
                        "next_research_question",
                        "human_review_needed",
                        "forbidden_actions_confirmed",
                    ],
                },
            }
        },
        "max_output_tokens": 600,
    }

    result = subprocess.run(
        [
            "curl",
            "-s",
            "https://api.openai.com/v1/responses",
            "-H",
            f"Authorization: Bearer {api_key}",
            "-H",
            "Content-Type: application/json",
            "-d",
            json.dumps(payload),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    if result.returncode != 0:
        raise SystemExit(result.stderr)

    data = json.loads(result.stdout)

    if data.get("error") is not None:
        raise SystemExit(json.dumps(data["error"], indent=2))

    output = extract_output_text(data)
    if not output:
        raise SystemExit(f"No output text found. Raw response: {json.dumps(data)[:1500]}")

    return output


def fallback_note(raw: str) -> dict[str, Any]:
    return {
        "current_risk_state": "MODEL_OUTPUT_PARSE_FAILED",
        "anomalies": [raw[:1000]],
        "next_research_question": "Fix cloud connector JSON parsing before trusting cloud research notes.",
        "human_review_needed": True,
        "forbidden_actions_confirmed": [
            "No live trading recommendation made.",
            "No strategy config change made.",
            "No risk increase made.",
            "No trades invented.",
        ],
    }


def main() -> None:
    if not PROMPT.exists():
        raise SystemExit("Missing prompt. Run: python3 local_research_agent_v1.py")

    source_prompt = PROMPT.read_text(errors="ignore")[:10000]

    guarded_prompt = f"""
You are a cloud research analyst for Isaac Quant-FX.

Rules:
- Do not recommend live trading.
- Do not suggest increasing risk.
- Do not suggest automatic strategy changes.
- Do not invent trades.
- Do not alter strategy config.
- You may only analyse, flag anomalies, and propose research questions.
- Only call something an anomaly if it is directly supported by the provided system context.
- If latest signal is OUTSIDE_WINDOW, SKIP_FRIDAY, or SKIP_DECEMBER, then zero trades is normal.
- If paper ledger has zero trades, do not call it an anomaly unless the latest signal was LONG_TRIGGERED or SHORT_TRIGGERED and no trade was recorded.
- forbidden_actions_confirmed must contain at least these four strings:
  "No live trading recommendation made."
  "No strategy config change made."
  "No risk increase made."
  "No trades invented."

Return JSON only according to the schema.

System context:
{source_prompt}
"""

    raw = call_openai(guarded_prompt)

    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            parsed = fallback_note(raw)
    except json.JSONDecodeError:
        parsed = fallback_note(raw)

    parsed["generated_at_utc"] = now()
    parsed["model"] = MODEL

    OUT_JSON.write_text(json.dumps(parsed, indent=2, sort_keys=True) + "\n")

    md = [
        "# Isaac Cloud Research Note V1",
        "",
        f"Generated UTC: {parsed['generated_at_utc']}",
        f"Model: {MODEL}",
        "",
        "## Current Risk State",
        parsed["current_risk_state"],
        "",
        "## Anomalies",
    ]

    for item in parsed["anomalies"]:
        md.append(f"- {item}")

    md.extend([
        "",
        "## Next Research Question",
        parsed["next_research_question"],
        "",
        "## Human Review Needed",
        str(parsed["human_review_needed"]),
        "",
        "## Forbidden Actions Confirmed",
    ])

    for item in parsed["forbidden_actions_confirmed"]:
        md.append(f"- {item}")

    OUT_MD.write_text("\n".join(md) + "\n")

    print("=== Isaac Cloud Research Connector V1 ===")
    print(f"Model: {MODEL}")
    print(f"JSON: {OUT_JSON}")
    print(f"Report: {OUT_MD}")
    print("CLOUD CONNECTOR STATUS: GREEN")


if __name__ == "__main__":
    main()
