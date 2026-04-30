"""
memory.py — Agent State & Action Log
=====================================
File-based state for dashboard communication.
- agent_state.json  : real-time agent status (dashboard polls this)
- agent_log.json    : full history of all agent sessions
"""

import os
import json
import datetime

from agent.config import AGENT_STATE_PATH, AGENT_LOG_PATH, DATA_DIR


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


# ── Agent State (real-time, dashboard reads this) ────────────────────────

def write_state(status: str, alert_id=None, steps=None, final_answer=None):
    """
    Write current agent state for the dashboard to display.
    status: idle | investigating | acting | resolved | error
    """
    _ensure_dir()
    state = {
        "status": status,
        "alert_id": alert_id,
        "updated_at": datetime.datetime.now().isoformat(),
        "steps": steps or [],
        "final_answer": final_answer,
    }
    with open(AGENT_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def read_state() -> dict:
    """Read current agent state."""
    if not os.path.exists(AGENT_STATE_PATH):
        return {"status": "idle", "steps": [], "final_answer": None}
    try:
        with open(AGENT_STATE_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"status": "idle", "steps": [], "final_answer": None}


def add_step(step_type: str, content: str, tool=None, tool_input=None):
    """Append a reasoning step to the current state (for live display)."""
    state = read_state()
    state["steps"].append({
        "type": step_type,    # thought | action | observation | error
        "content": content,
        "tool": tool,
        "tool_input": tool_input,
        "timestamp": datetime.datetime.now().isoformat(),
    })
    state["updated_at"] = datetime.datetime.now().isoformat()
    with open(AGENT_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


# ── Agent Log (persistent history) ──────────────────────────────────────

def append_log(alert: dict, steps: list, final_answer: str, outcome: str):
    """
    Append a completed agent session to the persistent log.
    outcome: resolved | escalated | error
    """
    _ensure_dir()

    if os.path.exists(AGENT_LOG_PATH):
        try:
            with open(AGENT_LOG_PATH, "r") as f:
                log = json.load(f)
        except (json.JSONDecodeError, IOError):
            log = []
    else:
        log = []

    entry = {
        "session_id": len(log) + 1,
        "timestamp": datetime.datetime.now().isoformat(),
        "alert_id": alert.get("id"),
        "anomaly_type": alert.get("anomaly_type", "unknown"),
        "severity": alert.get("severity", "medium"),
        "steps": steps,
        "final_answer": final_answer,
        "outcome": outcome,
    }
    log.append(entry)

    with open(AGENT_LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)

    return entry


def read_log() -> list:
    """Read full agent action log."""
    if not os.path.exists(AGENT_LOG_PATH):
        return []
    try:
        with open(AGENT_LOG_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def update_alert_status(alert_id: int, new_status: str):
    """Update an alert's status in alerts.json (pending → resolved)."""
    from agent.config import ALERTS_PATH
    if not os.path.exists(ALERTS_PATH):
        return
    try:
        with open(ALERTS_PATH, "r") as f:
            alerts = json.load(f)
        for alert in alerts:
            if alert.get("id") == alert_id:
                alert["status"] = new_status
        with open(ALERTS_PATH, "w") as f:
            json.dump(alerts, f, indent=2)
    except Exception:
        pass
