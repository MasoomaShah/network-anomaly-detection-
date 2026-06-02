"""
server.py — FastAPI Backend for Next.js Dashboard
===================================================
Thin proxy that exposes the existing JSON data files as REST endpoints
and wraps process_manager.py controls.

Run:  uvicorn dashboard.server:app --host 0.0.0.0 --port 8001 --reload
"""

import os
import sys
import json

# Ensure project root is on sys.path
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from agent.config import (
    ALERTS_PATH,
    AGENT_STATE_PATH,
    AGENT_LOG_PATH,
    LIVE_METRICS_PATH,
    DATA_DIR,
    get_llm_display_name,
)
from agent.trigger import inject_demo_alert, DEMO_SCENARIOS
from dashboard.process_manager import (
    start_monitoring,
    stop_monitoring,
    get_status,
    read_log_tail,
    INFERENCE_LOG,
    AGENT_LOG,
)

app = FastAPI(title="Network Troubleshooter API", version="1.0.0")

# CORS — allow localhost in dev and the deployed frontend in production.
# Set ALLOWED_ORIGINS env var to your Vercel URL in production, e.g.:
#   ALLOWED_ORIGINS=https://my-app.vercel.app
import os as _os
_raw = _os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:7860")
_origins = [o.strip() for o in _raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _load_json(path, default=None):
    """Safely load a JSON file, returning default on any error."""
    if default is None:
        default = {}
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


# ── Data Endpoints ──────────────────────────────────────────────────────

@app.get("/api/metrics")
def get_metrics():
    """Current live network metrics."""
    return _load_json(LIVE_METRICS_PATH, {})


@app.get("/api/agent-state")
def get_agent_state():
    """Current agent reasoning state."""
    data = _load_json(AGENT_STATE_PATH, {})
    if not data:
        return {"status": "idle", "steps": [], "final_answer": None}
    if "steps" not in data:
        data["steps"] = []
    return data


@app.get("/api/alerts")
def get_alerts():
    """All anomaly alerts."""
    return _load_json(ALERTS_PATH, [])


@app.get("/api/sessions")
def get_sessions():
    """Agent session log (action history)."""
    return _load_json(AGENT_LOG_PATH, [])


@app.get("/api/logs/inference")
def get_inference_logs(n: int = Query(default=200, ge=1, le=2000)):
    """Tail of the inference log file."""
    text = read_log_tail("inference", n)
    return {"lines": text.splitlines() if text else []}


@app.get("/api/logs/agent")
def get_agent_logs(n: int = Query(default=200, ge=1, le=2000)):
    """Tail of the agent log file."""
    text = read_log_tail("agent", n)
    return {"lines": text.splitlines() if text else []}


# ── Process Control ─────────────────────────────────────────────────────

@app.get("/api/status")
def api_status():
    """Get inference + agent process status."""
    return get_status()


@app.get("/api/llm-info")
def api_llm_info():
    """Get the currently configured LLM display name."""
    try:
        name = get_llm_display_name()
    except Exception:
        name = "unknown"
    return {"name": name}


@app.post("/api/start")
def api_start():
    """Start monitoring (inference + agent)."""
    msg = start_monitoring()
    return {"message": msg, "status": get_status()}


@app.post("/api/stop")
def api_stop():
    """Stop monitoring."""
    msg = stop_monitoring()
    return {"message": msg, "status": get_status()}


@app.post("/api/demo/{scenario}")
def api_demo(scenario: str):
    """Inject a demo alert for a given scenario."""
    valid = list(DEMO_SCENARIOS.keys())
    if scenario not in valid:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario '{scenario}'. Valid: {valid}",
        )
    alert = inject_demo_alert(scenario)
    return {"message": f"Injected {scenario}", "alert": alert}


@app.post("/api/reset")
def api_reset():
    """Reset all data files to their empty defaults."""
    _ensure_data_dir()
    defaults = {
        ALERTS_PATH: "[]",
        AGENT_STATE_PATH: "{}",
        AGENT_LOG_PATH: "[]",
        LIVE_METRICS_PATH: "{}",
    }
    for path, default in defaults.items():
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(default)
        except Exception:
            pass

    # Also clear log files
    for lp in [INFERENCE_LOG, AGENT_LOG]:
        try:
            with open(lp, "w", encoding="utf-8") as f:
                f.write("")
        except Exception:
            pass

    return {"message": "All data reset."}
