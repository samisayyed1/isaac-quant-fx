from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path("/home/sami/quant-fx")
NOTE_JSON = ROOT / "agent_outputs" / "latest_cloud_research_note.json"
EVENTS = ROOT / "memory" / "events.jsonl"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing cloud research note: {path}")
    return json.loads(path.read_text())


def main() -> None:
    note = read_json(NOTE_JSON)

    EVENTS.parent.mkdir(parents=True, exist_ok=True)

    event = {
        "time_utc": now(),
        "kind": "CLOUD_RESEARCH_NOTE",
        "source": str(NOTE_JSON),
        "payload": {
            "model": note.get("model"),
            "generated_at_utc": note.get("generated_at_utc"),
            "current_risk_state": note.get("current_risk_state"),
            "anomalies": note.get("anomalies", []),
            "next_research_question": note.get("next_research_question"),
            "human_review_needed": note.get("human_review_needed", True),
            "forbidden_actions_confirmed": note.get("forbidden_actions_confirmed", []),
        },
    }

    with EVENTS.open("a") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")

    print("=== Isaac Cloud Research Memory Ingest V1 ===")
    print(f"Memory events: {EVENTS}")
    print(f"Ingested model: {event['payload']['model']}")
    print(f"Risk state: {event['payload']['current_risk_state']}")
    print("INGEST STATUS: GREEN")


if __name__ == "__main__":
    main()
