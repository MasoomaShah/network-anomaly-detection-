"""
process_manager.py — Background Process Manager
=================================================
Spawns inference.py + main.py --mode lstm as subprocesses.
Pipes stdout/stderr to log files so the dashboard can display them.
"""

import os
import sys
import signal
import subprocess
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

INFERENCE_LOG = os.path.join(DATA_DIR, "inference.log")
AGENT_LOG = os.path.join(DATA_DIR, "agent.log")

# Global process handles
_inference_proc = None
_agent_proc = None
_lock = threading.Lock()


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def start_monitoring():
    """Start inference + agent as background subprocesses."""
    global _inference_proc, _agent_proc

    with _lock:
        if is_running():
            return "Already running."

        _ensure_data_dir()

        python = sys.executable  # same Python that runs Streamlit

        # Clear old logs
        for lp in [INFERENCE_LOG, AGENT_LOG]:
            with open(lp, "w") as f:
                f.write("")

        # Start inference.py
        inf_log_fh = open(INFERENCE_LOG, "a", buffering=1, encoding="utf-8")
        _inference_proc = subprocess.Popen(
            [python, "-u", os.path.join(BASE_DIR, "inference", "inference.py")],
            stdout=inf_log_fh,
            stderr=subprocess.STDOUT,
            cwd=BASE_DIR,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            if sys.platform == "win32" else 0,
        )

        # Start agent in LSTM watcher mode
        agt_log_fh = open(AGENT_LOG, "a", buffering=1, encoding="utf-8")
        _agent_proc = subprocess.Popen(
            [python, "-u", os.path.join(BASE_DIR, "main.py"), "--mode", "lstm"],
            stdout=agt_log_fh,
            stderr=subprocess.STDOUT,
            cwd=BASE_DIR,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            if sys.platform == "win32" else 0,
        )

        return "Started."


def stop_monitoring():
    """Stop both subprocesses."""
    global _inference_proc, _agent_proc

    with _lock:
        for proc in [_inference_proc, _agent_proc]:
            if proc and proc.poll() is None:
                try:
                    if sys.platform == "win32":
                        proc.terminate()
                    else:
                        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass

        _inference_proc = None
        _agent_proc = None
        return "Stopped."


def is_running():
    """Check if monitoring processes are alive."""
    inf_alive = _inference_proc is not None and _inference_proc.poll() is None
    agt_alive = _agent_proc is not None and _agent_proc.poll() is None
    return inf_alive or agt_alive


def get_status():
    """Get detailed status of both processes."""
    inf_alive = _inference_proc is not None and _inference_proc.poll() is None
    agt_alive = _agent_proc is not None and _agent_proc.poll() is None
    return {
        "inference": "running" if inf_alive else "stopped",
        "agent": "running" if agt_alive else "stopped",
        "overall": "running" if (inf_alive or agt_alive) else "stopped",
    }


def read_log_tail(source="inference", n=60):
    """Read last N lines from a log file."""
    path = INFERENCE_LOG if source == "inference" else AGENT_LOG
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-n:])
    except Exception:
        return ""
