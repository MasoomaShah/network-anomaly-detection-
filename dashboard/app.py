"""
app.py — Network Troubleshooter Live Dashboard
================================================
Run:  streamlit run dashboard/app.py
"""

import os
import sys
import json
import html as html_lib
import datetime
import threading
import time as _time

# Path setup
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BASE)

import streamlit as st

from agent.config import (
    ALERTS_PATH, AGENT_STATE_PATH, AGENT_LOG_PATH,
    LIVE_METRICS_PATH, get_llm_display_name,
)
from agent import memory
from agent.trigger import trigger_demo, DEMO_SCENARIOS
from dashboard.process_manager import (
    start_monitoring, stop_monitoring, is_running, get_status,
    read_log_tail,
)

# Auto-refresh (install: pip install streamlit-autorefresh)
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

# ── Page Config ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Network Troubleshooter",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Reset & Base ────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] * {
    font-family: 'Inter', sans-serif;
}
[data-testid="stAppViewContainer"] {
    background: #0d1117;
    color: #c9d1d9;
}
[data-testid="stSidebar"] {
    background: #0d1117;
    border-right: 1px solid #21262d;
}
[data-testid="stSidebar"] * {
    color: #c9d1d9;
}

/* ── Remove Streamlit chrome ─────────────────────────── */
.block-container {
    padding: 2rem 2.5rem 1rem 2.5rem;
    max-width: 100%;
}
header[data-testid="stHeader"] {
    background: transparent;
}
#MainMenu, footer { visibility: hidden; }

/* ── Metric Card ─────────────────────────────────────── */
.mc {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 1.1rem 1.2rem;
    text-align: center;
    transition: border-color 0.2s;
}
.mc:hover { border-color: #388bfd; }
.mc-lbl {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #8b949e;
    margin-bottom: 0.35rem;
}
.mc-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.45rem;
    font-weight: 700;
    line-height: 1.2;
}
.mc-unit {
    font-size: 0.7rem;
    color: #8b949e;
    font-weight: 400;
}

/* ── Colors ──────────────────────────────────────────── */
.cg  { color: #3fb950; }
.cy  { color: #d29922; }
.cr  { color: #f85149; }
.cb  { color: #58a6ff; }
.cp  { color: #bc8cff; }

/* ── Section Header ──────────────────────────────────── */
.shdr {
    font-size: 0.85rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #8b949e;
    padding-bottom: 0.6rem;
    margin-bottom: 0.9rem;
    border-bottom: 1px solid #21262d;
}

/* ── Agent Step ──────────────────────────────────────── */
.astep {
    background: #161b22;
    border-left: 3px solid #21262d;
    padding: 0.65rem 0.9rem;
    margin-bottom: 0.5rem;
    border-radius: 0 6px 6px 0;
    font-size: 0.82rem;
    line-height: 1.55;
    color: #c9d1d9;
}
.astep-t   { border-left-color: #bc8cff; }
.astep-a   { border-left-color: #58a6ff; }
.astep-o   { border-left-color: #3fb950; }
.astep-e   { border-left-color: #f85149; }
.astep-f   { border-left-color: #d29922; }
.stype {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.2rem;
}

/* ── Alert Row ───────────────────────────────────────── */
.arow {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 0.65rem 0.9rem;
    margin-bottom: 0.45rem;
    display: flex;
    align-items: center;
    gap: 0.8rem;
    font-size: 0.8rem;
    color: #c9d1d9;
}
.bdg {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    font-weight: 600;
    padding: 0.15rem 0.5rem;
    border-radius: 20px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    display: inline-block;
}
.bdg-hi  { background: rgba(248,81,73,0.15); color: #f85149; }
.bdg-md  { background: rgba(210,153,34,0.15); color: #d29922; }
.bdg-lo  { background: rgba(63,185,80,0.15);  color: #3fb950; }
.bdg-pn  { background: rgba(88,166,255,0.12); color: #58a6ff; }
.bdg-ok  { background: rgba(63,185,80,0.12);  color: #3fb950; }
.bdg-inv { background: rgba(188,140,255,0.12); color: #bc8cff; }
.bdg-err { background: rgba(248,81,73,0.12);  color: #f85149; }

/* ── Status Banner ───────────────────────────────────── */
.stban {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.6rem 1rem;
    border-radius: 8px;
    font-size: 0.82rem;
    font-weight: 500;
    margin-bottom: 1.2rem;
    color: #c9d1d9;
}
.stban-idle { background: rgba(63,185,80,0.08);  border: 1px solid rgba(63,185,80,0.2); }
.stban-inv  { background: rgba(188,140,255,0.08); border: 1px solid rgba(188,140,255,0.2); }
.stban-ok   { background: rgba(63,185,80,0.08);  border: 1px solid rgba(63,185,80,0.2); }
.stban-err  { background: rgba(248,81,73,0.08);  border: 1px solid rgba(248,81,73,0.2); }

/* ── Buttons ─────────────────────────────────────────── */
div.stButton > button {
    width: 100%;
    background: #161b22;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 0.55rem 1rem;
    font-family: 'Inter', sans-serif;
    font-size: 0.8rem;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
}
div.stButton > button:hover {
    background: #1c2128;
    border-color: #58a6ff;
    color: #f0f6fc;
}

/* ── Scroll ──────────────────────────────────────────── */
.sbox {
    max-height: 420px;
    overflow-y: auto;
    padding-right: 0.4rem;
}
.sbox::-webkit-scrollbar { width: 4px; }
.sbox::-webkit-scrollbar-thumb { background: #30363d; border-radius: 4px; }

/* ── Diagnosis Box ───────────────────────────────────── */
.diag-box {
    background: #0d2818;
    border: 1px solid #238636;
    border-radius: 8px;
    padding: 0.8rem 1rem;
    margin-top: 0.6rem;
}
.diag-hdr {
    font-size: 0.72rem;
    font-weight: 600;
    color: #3fb950;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 0.3rem;
}
.diag-body {
    font-size: 0.82rem;
    color: #c9d1d9;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
}

/* ── Error Box ───────────────────────────────────────── */
.err-box {
    background: #2d1215;
    border: 1px solid #6e3630;
    border-radius: 8px;
    padding: 0.8rem 1rem;
    margin-top: 0.6rem;
}
.err-hdr {
    font-size: 0.72rem;
    font-weight: 600;
    color: #f85149;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 0.3rem;
}
.err-body {
    font-size: 0.78rem;
    color: #f0a8a8;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: 'JetBrains Mono', monospace;
}

/* ── Mono span ───────────────────────────────────────── */
.mono {
    font-family: 'JetBrains Mono', monospace;
}

/* ── Empty state ─────────────────────────────────────── */
.empty-state {
    text-align: center;
    padding: 3rem 1rem;
    color: #484f58;
}
.empty-icon { font-size: 2rem; margin-bottom: 0.5rem; }
.empty-text { font-size: 0.85rem; }

/* ── Log Drawer (HF-style) ─────────────────────────── */
.log-drawer-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 9999;
    background: #0d1117;
    border-top: 1px solid #30363d;
    cursor: pointer;
    display: flex;
    align-items: center;
    padding: 0.45rem 1.2rem;
    gap: 0.6rem;
    font-family: 'Inter', sans-serif;
    transition: background 0.15s;
}
.log-drawer-bar:hover { background: #161b22; }
.log-drawer-arrow {
    font-size: 0.7rem;
    color: #8b949e;
    transition: transform 0.25s;
}
.log-drawer-arrow.open { transform: rotate(180deg); }
.log-drawer-title {
    font-size: 0.75rem;
    font-weight: 600;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
.log-drawer-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    display: inline-block;
}
.log-drawer-dot.running { background: #3fb950; animation: pulse-dot 1.5s infinite; }
.log-drawer-dot.stopped { background: #484f58; }
@keyframes pulse-dot {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
}
.log-drawer-panel {
    position: fixed;
    bottom: 34px;
    left: 0;
    right: 0;
    z-index: 9998;
    background: #0d1117;
    border-top: 1px solid #30363d;
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.35s ease;
}
.log-drawer-panel.open { max-height: 320px; }
.log-tabs {
    display: flex;
    gap: 0;
    border-bottom: 1px solid #21262d;
    padding: 0 1rem;
}
.log-tab {
    padding: 0.4rem 1rem;
    font-size: 0.72rem;
    font-weight: 600;
    color: #8b949e;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    transition: color 0.15s, border-color 0.15s;
}
.log-tab:hover { color: #c9d1d9; }
.log-tab.active { color: #58a6ff; border-bottom-color: #58a6ff; }
.log-content {
    display: none;
    height: 260px;
    overflow-y: auto;
    padding: 0.6rem 1rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    line-height: 1.65;
    color: #8b949e;
    white-space: pre-wrap;
    word-break: break-all;
}
.log-content.active { display: block; }
.log-content::-webkit-scrollbar { width: 4px; }
.log-content::-webkit-scrollbar-thumb { background: #30363d; border-radius: 4px; }

/* Push main content above drawer bar */
.block-container { padding-bottom: 3rem !important; }
</style>
""", unsafe_allow_html=True)

# ── Auto-refresh while monitoring ────────────────────────────────────────
if HAS_AUTOREFRESH and is_running():
    st_autorefresh(interval=4000, limit=None, key="monitor_refresh")


# ── Data Loaders ─────────────────────────────────────────────────────────

def load_json(path, default=None):
    if default is None:
        default = {}
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default


def esc(text: str) -> str:
    """HTML-escape user/agent content to prevent rendering issues."""
    return html_lib.escape(str(text)) if text else ""


# ── Metric Helpers ───────────────────────────────────────────────────────

METRIC_CONFIG = {
    "latency_ms":        {"label": "Latency",   "unit": "ms",   "green": 50,  "yellow": 200,  "dir": "lower"},
    "packet_loss_pct":   {"label": "Pkt Loss",  "unit": "%",    "green": 1,   "yellow": 10,   "dir": "lower"},
    "download_mbps":     {"label": "Download",  "unit": "Mbps", "green": 10,  "yellow": 1,    "dir": "higher"},
    "upload_mbps":       {"label": "Upload",    "unit": "Mbps", "green": 5,   "yellow": 1,    "dir": "higher"},
    "connected_devices": {"label": "Devices",   "unit": "",     "green": 10,  "yellow": 15,   "dir": "lower"},
    "dns_response_ms":   {"label": "DNS",       "unit": "ms",   "green": 100, "yellow": 1000, "dir": "lower"},
    "gateway_ping_ms":   {"label": "Gateway",   "unit": "ms",   "green": 20,  "yellow": 100,  "dir": "lower"},
    "jitter_ms":         {"label": "Jitter",    "unit": "ms",   "green": 20,  "yellow": 80,   "dir": "lower"},
}


def metric_color(key: str, value: float) -> str:
    cfg = METRIC_CONFIG.get(key, {})
    g, y = cfg.get("green", 0), cfg.get("yellow", 0)
    if cfg.get("dir") == "higher":
        if value >= g:   return "cg"
        if value >= y:   return "cy"
        return "cr"
    else:
        if value <= g:   return "cg"
        if value <= y:   return "cy"
        return "cr"


def render_metric_card(key: str, value):
    cfg = METRIC_CONFIG.get(key, {"label": key, "unit": ""})
    color = metric_color(key, float(value)) if value is not None else "cb"
    display_val = f"{value:.1f}" if isinstance(value, float) else str(value)
    unit = cfg["unit"]

    st.markdown(
        f'<div class="mc">'
        f'<div class="mc-lbl">{esc(cfg["label"])}</div>'
        f'<div class="mc-val {color}">{esc(display_val)}'
        f' <span class="mc-unit">{esc(unit)}</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Severity / status badge helper ──────────────────────────────────────

def sev_class(s: str) -> str:
    return {"high": "bdg-hi", "medium": "bdg-md", "low": "bdg-lo"}.get(s, "bdg-md")


def status_class(s: str) -> str:
    return {
        "pending": "bdg-pn", "resolved": "bdg-ok",
        "investigating": "bdg-inv", "error": "bdg-err",
    }.get(s, "bdg-pn")


# ── Sidebar ──────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🛡️ Network Agent")
    st.caption(f"LLM: {get_llm_display_name()}")
    st.markdown("---")

    st.markdown("**Demo Controls**")
    st.caption("Trigger a scenario to watch the agent investigate in real time.")

    scenario_labels = {
        "bandwidth_flood": "🌊  Bandwidth Flood",
        "unknown_device":  "📱  Unknown Device",
        "dns_failure":     "🌐  DNS Failure",
        "packet_loss":     "📉  Packet Loss",
    }

    for key, label in scenario_labels.items():
        if st.button(label, key=f"demo_{key}", use_container_width=True):
            with st.spinner(f"Agent investigating {key.replace('_', ' ')}…"):
                thread = threading.Thread(target=trigger_demo, args=(key,), daemon=True)
                thread.start()
                thread.join(timeout=90)
            st.rerun()

    st.markdown("---")

    # ── Monitoring Controls ──────────────────────────────────────────
    st.markdown("**Live Monitoring**")
    proc_status = get_status()
    monitoring_active = proc_status["overall"] == "running"

    if monitoring_active:
        inf_dot = "🟢" if proc_status["inference"] == "running" else "🔴"
        agt_dot = "🟢" if proc_status["agent"] == "running" else "🔴"
        st.caption(f"{inf_dot} Inference &nbsp; {agt_dot} Agent")
        if st.button("⏹  Stop Monitoring", key="stop_mon", use_container_width=True):
            stop_monitoring()
            st.rerun()
    else:
        st.caption("Start inference + agent with one click.")
        if st.button("▶  Start Monitoring", key="start_mon", use_container_width=True):
            start_monitoring()
            _time.sleep(1)  # let processes start
            st.rerun()

    st.markdown("---")
    if st.button("🔄  Refresh", use_container_width=True):
        st.rerun()

    st.markdown("---")
    st.caption("Built for DNN Course — 6th Semester AI")


# ── Main Layout ──────────────────────────────────────────────────────────

agent_state = memory.read_state()
status = agent_state.get("status", "idle")

status_icons = {"idle": "🟢", "investigating": "🔵", "resolved": "✅", "error": "🔴", "acting": "⚡"}
status_labels = {
    "idle": "Monitoring — All Clear",
    "investigating": "Agent Investigating Anomaly…",
    "resolved": "Issue Resolved",
    "error": "Agent Encountered Error",
    "acting": "Agent Taking Action…",
}
ban_cls = {"idle": "stban-idle", "investigating": "stban-inv", "resolved": "stban-ok", "error": "stban-err"}

now_str = datetime.datetime.now().strftime("%H:%M:%S")

st.markdown(
    f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.3rem;">'
    f'<div style="font-size:1.4rem;font-weight:700;color:#f0f6fc;">Network Troubleshooter</div>'
    f'<div class="mono" style="font-size:0.75rem;color:#8b949e;">{now_str}</div>'
    f'</div>',
    unsafe_allow_html=True,
)

st.markdown(
    f'<div class="stban {ban_cls.get(status, "stban-idle")}">'
    f'<span style="font-size:1.1rem;">{status_icons.get(status, "⚪")}</span>'
    f'<span>{esc(status_labels.get(status, status.title()))}</span>'
    f'</div>',
    unsafe_allow_html=True,
)


# ── Metric Cards ────────────────────────────────────────────────────────
metrics = load_json(LIVE_METRICS_PATH, {}).get("metrics", {})

st.markdown('<div class="shdr">Live Network Metrics</div>', unsafe_allow_html=True)

if metrics:
    cols = st.columns(8)
    for i, key in enumerate(METRIC_CONFIG.keys()):
        with cols[i]:
            render_metric_card(key, metrics.get(key, 0))
else:
    st.info("No live metrics yet. Start the trigger or click a demo scenario.")


st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

# ── Two-Column Layout ───────────────────────────────────────────────────
col_left, col_right = st.columns([3, 2])

# ── LEFT: Agent Reasoning ───────────────────────────────────────────────
with col_left:
    st.markdown('<div class="shdr">Agent Reasoning</div>', unsafe_allow_html=True)

    steps = agent_state.get("steps", [])
    final = agent_state.get("final_answer")
    is_error = status == "error"

    if not steps and not final:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-icon">🤖</div>'
            '<div class="empty-text">Agent is idle. Trigger a demo scenario to see it reason.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        step_icons = {"thought": "💭", "action": "⚡", "observation": "👁️", "error": "❌", "final": "✅"}
        step_cls   = {"thought": "astep-t", "action": "astep-a", "observation": "astep-o", "error": "astep-e", "final": "astep-f"}
        step_clr   = {"thought": "#bc8cff", "action": "#58a6ff", "observation": "#3fb950", "error": "#f85149", "final": "#d29922"}

        parts = []
        for step in steps:
            stype = step.get("type", "thought")
            icon  = step_icons.get(stype, "•")
            content = esc(step.get("content", "")[:600])
            tool  = step.get("tool")
            tinp  = step.get("tool_input")

            tool_line = ""
            if tool:
                tool_line = f'<span class="mono cb" style="font-size:0.75rem;">{esc(tool)}({esc(tinp or "")})</span><br/>'

            parts.append(
                f'<div class="astep {step_cls.get(stype, "")}">'
                f'<div class="stype" style="color:{step_clr.get(stype, "#8b949e")};">{icon} {esc(stype)}</div>'
                f'{tool_line}'
                f'<div>{content}</div>'
                f'</div>'
            )

        st.markdown('<div class="sbox">' + "".join(parts) + '</div>', unsafe_allow_html=True)

    # Final answer / error box
    if final:
        if is_error:
            # Show a clean error message, not a raw traceback
            short_err = str(final).split("Traceback")[0].strip()
            if not short_err:
                short_err = str(final)[:300]
            st.markdown(
                f'<div class="err-box">'
                f'<div class="err-hdr">❌ Error</div>'
                f'<div class="err-body">{esc(short_err)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="diag-box">'
                f'<div class="diag-hdr">✅ Diagnosis Report</div>'
                f'<div class="diag-body">{esc(final[:1000])}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ── RIGHT: Anomaly Feed + Action Log ────────────────────────────────────
with col_right:
    st.markdown('<div class="shdr">Anomaly Feed</div>', unsafe_allow_html=True)

    alerts = load_json(ALERTS_PATH, [])

    if not alerts:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-icon">📡</div>'
            '<div class="empty-text">No anomalies detected yet.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        rows = []
        for alert in reversed(alerts[-15:]):
            aid = alert.get("id", "?")
            atype = esc(alert.get("anomaly_type", "unknown").replace("_", " ").title())
            sev = alert.get("severity", "medium")
            ast = alert.get("status", "pending")
            ts = alert.get("timestamp", "")
            try:
                ts_short = datetime.datetime.fromisoformat(ts).strftime("%H:%M")
            except Exception:
                ts_short = ts[:5]

            rows.append(
                f'<div class="arow">'
                f'<span class="mono" style="font-size:0.72rem;color:#484f58;min-width:2rem;">#{aid}</span>'
                f'<span style="font-size:0.75rem;color:#8b949e;min-width:3rem;">{esc(ts_short)}</span>'
                f'<span class="bdg {sev_class(sev)}">{esc(sev)}</span>'
                f'<span style="flex:1;font-size:0.78rem;">{atype}</span>'
                f'<span class="bdg {status_class(ast)}">{esc(ast)}</span>'
                f'</div>'
            )

        st.markdown('<div class="sbox">' + "".join(rows) + '</div>', unsafe_allow_html=True)

    # ── Action Log ───────────────────────────────────────────────────────
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    st.markdown('<div class="shdr">Action Log</div>', unsafe_allow_html=True)

    log_entries = memory.read_log()

    if not log_entries:
        st.markdown(
            '<div class="empty-state" style="padding:1.5rem 1rem;">'
            '<div class="empty-text">No actions taken yet.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        rows = []
        for entry in reversed(log_entries[-10:]):
            sid = entry.get("session_id", "?")
            outcome = entry.get("outcome", "unknown")
            atype = esc(entry.get("anomaly_type", "unknown").replace("_", " ").title())
            n_steps = len(entry.get("steps", []))
            ts = entry.get("timestamp", "")
            try:
                ts_short = datetime.datetime.fromisoformat(ts).strftime("%H:%M")
            except Exception:
                ts_short = ""

            o_cls = {"resolved": "bdg-ok", "error": "bdg-err", "escalated": "bdg-md"}.get(outcome, "bdg-pn")

            rows.append(
                f'<div class="arow">'
                f'<span class="mono" style="font-size:0.72rem;color:#484f58;">S{sid}</span>'
                f'<span style="font-size:0.75rem;color:#8b949e;">{esc(ts_short)}</span>'
                f'<span style="flex:1;font-size:0.78rem;">{atype}</span>'
                f'<span style="font-size:0.72rem;color:#484f58;">{n_steps} steps</span>'
                f'<span class="bdg {o_cls}">{esc(outcome)}</span>'
                f'</div>'
            )

        st.markdown('<div class="sbox">' + "".join(rows) + '</div>', unsafe_allow_html=True)


# ── Log Drawer (HF-style collapsible panel) ─────────────────────────────

_drawer_running = is_running()
_dot_cls = "running" if _drawer_running else "stopped"
_inf_logs = esc(read_log_tail("inference", 80)) or "No inference logs yet. Click ▶ Start Monitoring."
_agt_logs = esc(read_log_tail("agent", 80)) or "No agent logs yet. Click ▶ Start Monitoring."

st.markdown(f'''
<!-- Log Panel (hidden by default) -->
<div class="log-drawer-panel" id="logPanel">
  <div class="log-tabs">
    <div class="log-tab active" id="tabInf" onclick="switchTab('inference')">Inference</div>
    <div class="log-tab" id="tabAgt" onclick="switchTab('agent')">Agent</div>
  </div>
  <div class="log-content active" id="logInference">{_inf_logs}</div>
  <div class="log-content" id="logAgent">{_agt_logs}</div>
</div>

<!-- Toggle Bar (always visible at bottom) -->
<div class="log-drawer-bar" id="logBar" onclick="toggleDrawer()">
  <span class="log-drawer-arrow" id="logArrow">▲</span>
  <span class="log-drawer-dot {_dot_cls}"></span>
  <span class="log-drawer-title">Logs</span>
</div>

<script>
function toggleDrawer() {{
    const panel = document.getElementById('logPanel');
    const arrow = document.getElementById('logArrow');
    panel.classList.toggle('open');
    arrow.classList.toggle('open');
    // Auto-scroll logs to bottom when opened
    if (panel.classList.contains('open')) {{
        document.querySelectorAll('.log-content').forEach(el => {{
            el.scrollTop = el.scrollHeight;
        }});
    }}
}}
function switchTab(tab) {{
    document.getElementById('tabInf').classList.toggle('active', tab === 'inference');
    document.getElementById('tabAgt').classList.toggle('active', tab === 'agent');
    document.getElementById('logInference').classList.toggle('active', tab === 'inference');
    document.getElementById('logAgent').classList.toggle('active', tab === 'agent');
    // Scroll to bottom of active tab
    const active = document.querySelector('.log-content.active');
    if (active) active.scrollTop = active.scrollHeight;
}}
</script>
''', unsafe_allow_html=True)
