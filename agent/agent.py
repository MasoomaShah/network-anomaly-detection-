"""
agent.py — LangChain ReAct Agent (LangGraph)
=============================================
Uses langgraph's create_react_agent — the modern, supported API.
Wires: LLM (config.py) + tools (tools.py) + prompts (prompts.py)
Captures intermediate steps for live dashboard display.
"""

import traceback
from langchain_core.tools import tool as tool_decorator
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from agent.config import get_llm
from agent.tools import TOOL_DEFINITIONS
from agent.prompts import SYSTEM_PROMPT, build_agent_input
from agent import memory


# ── Wrap tool functions for LangGraph ────────────────────────────────────

def _build_tools():
    """Convert our tool defs into langchain-compatible tool objects."""
    from langchain_core.tools import StructuredTool

    lc_tools = []
    for td in TOOL_DEFINITIONS:
        t = StructuredTool.from_function(
            func=td["func"],
            name=td["name"],
            description=td["description"],
        )
        lc_tools.append(t)
    return lc_tools


# ── Build the agent ─────────────────────────────────────────────────────

def _build_agent():
    """Construct the LangGraph ReAct agent with all tools."""
    llm = get_llm()
    tools = _build_tools()

    # create_react_agent from langgraph returns a compiled graph
    agent = create_react_agent(
        model=llm,
        tools=tools,
    )
    return agent


# ── Public API ──────────────────────────────────────────────────────────

def run_agent(alert: dict) -> dict:
    """
    Run the agent on an anomaly alert.

    Parameters
    ----------
    alert : dict
        An alert record from alerts.json (has id, anomaly_type, metrics, etc.)

    Returns
    -------
    dict with keys: final_answer, steps, outcome
    """
    alert_id = alert.get("id", 0)

    # Signal dashboard: agent is working
    memory.write_state("investigating", alert_id=alert_id)
    memory.update_alert_status(alert_id, "investigating")

    try:
        agent = _build_agent()
        user_input = build_agent_input(alert)

        # Build the system prompt with anomaly context
        metrics = alert.get("metrics", {})
        metric_lines = "\n".join(f"  {k}: {v}" for k, v in metrics.items())
        context = (
            f"Anomaly Type: {alert.get('anomaly_type', 'unknown')}\n"
            f"Severity: {alert.get('severity', 'medium')}\n"
            f"Metrics:\n{metric_lines}"
        )
        sys_prompt = SYSTEM_PROMPT.format(anomaly_context=context)

        memory.add_step("thought",
                        f"Anomaly detected: {alert.get('anomaly_type', 'unknown')} "
                        f"(severity: {alert.get('severity', 'medium')}). Starting investigation...")

        # Invoke the agent graph
        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=user_input),
        ]

        result = agent.invoke({"messages": messages})

        # Extract steps and final answer from the message history
        steps = []
        final_answer = ""

        for msg in result.get("messages", []):
            msg_type = type(msg).__name__

            if msg_type == "AIMessage":
                content = getattr(msg, "content", "")
                tool_calls = getattr(msg, "tool_calls", [])

                if content:
                    final_answer = content  # last AI message = final answer

                for tc in tool_calls:
                    memory.add_step(
                        "action",
                        f"Calling: {tc['name']}",
                        tool=tc["name"],
                        tool_input=str(tc.get("args", "")),
                    )
                    steps.append({
                        "tool": tc["name"],
                        "input": str(tc.get("args", "")),
                        "output": "",
                    })

            elif msg_type == "ToolMessage":
                content = getattr(msg, "content", "")
                display = content[:500] if len(content) > 500 else content
                memory.add_step("observation", display)
                if steps:
                    steps[-1]["output"] = display

        # Log completed session
        memory.append_log(alert, steps, final_answer, outcome="resolved")
        memory.update_alert_status(alert_id, "resolved")
        memory.write_state(
            "resolved", alert_id=alert_id,
            steps=memory.read_state().get("steps", []),
            final_answer=final_answer,
        )

        return {"final_answer": final_answer, "steps": steps, "outcome": "resolved"}

    except Exception as e:
        error_str = str(e).lower()
        is_connection_error = any(k in error_str for k in [
            "connection error", "name resolution", "getaddrinfo",
            "unreachable", "timed out", "connecttimeout",
        ])

        if is_connection_error:
            # Fallback: API unreachable (likely DNS is broken or no internet)
            anomaly = alert.get("anomaly_type", "unknown")
            metrics = alert.get("metrics", {})
            fallback = _build_fallback_diagnosis(anomaly, metrics)
            memory.add_step("thought",
                            "⚠️ Cannot reach LLM API (network may be down). "
                            "Using local fallback diagnosis.")
            memory.add_step("observation", fallback)
            memory.append_log(alert, [], fallback, outcome="resolved")
            memory.update_alert_status(alert_id, "resolved")
            memory.write_state(
                "resolved", alert_id=alert_id,
                steps=memory.read_state().get("steps", []),
                final_answer=fallback,
            )
            return {"final_answer": fallback, "steps": [], "outcome": "resolved"}
        else:
            error_msg = f"Agent error: {e}\n{traceback.format_exc()}"
            memory.add_step("error", error_msg)
            memory.append_log(alert, [], error_msg, outcome="error")
            memory.update_alert_status(alert_id, "error")
            memory.write_state(
                "error", alert_id=alert_id,
                steps=memory.read_state().get("steps", []),
                final_answer=error_msg,
            )
            return {"final_answer": error_msg, "steps": [], "outcome": "error"}


# ── Fallback diagnosis when LLM is unreachable ─────────────────────────

_FALLBACK_DIAGNOSES = {
    "dns_failure": (
        "🌐 DNS FAILURE DETECTED\n\n"
        "Diagnosis: DNS resolution is failing — the configured DNS server is "
        "unreachable or unresponsive.\n\n"
        "Recommended fix:\n"
        "  1. Switch DNS to Google Public DNS: 8.8.8.8 / 8.8.4.4\n"
        "  2. Or Cloudflare DNS: 1.1.1.1\n"
        "  3. Run: netsh interface ip set dns \"Wi-Fi\" dhcp\n\n"
        "Note: LLM agent could not connect to OpenAI API because DNS is down. "
        "This diagnosis was generated locally."
    ),
    "high_packet_loss": (
        "📉 HIGH PACKET LOSS DETECTED\n\n"
        "Diagnosis: Significant packet loss detected on the network.\n\n"
        "Possible causes:\n"
        "  - Network congestion or overloaded router\n"
        "  - Faulty network cable or Wi-Fi interference\n"
        "  - ISP-side issue\n\n"
        "Recommended fix:\n"
        "  1. Restart your router/access point\n"
        "  2. Move closer to the Wi-Fi access point\n"
        "  3. Check for bandwidth-heavy applications\n"
        "  4. Contact ISP if issue persists"
    ),
    "bandwidth_saturation": (
        "🌊 BANDWIDTH SATURATION DETECTED\n\n"
        "Diagnosis: Network bandwidth is fully utilized.\n\n"
        "Possible causes:\n"
        "  - Large file upload/download in progress\n"
        "  - Multiple devices streaming simultaneously\n"
        "  - Background cloud sync or updates\n\n"
        "Recommended fix:\n"
        "  1. Identify and throttle heavy bandwidth users\n"
        "  2. Pause cloud backups or large downloads\n"
        "  3. Enable QoS on your router if available"
    ),
    "unexpected_devices": (
        "📱 UNEXPECTED DEVICES DETECTED\n\n"
        "Diagnosis: New or unknown devices have joined the network.\n\n"
        "Recommended fix:\n"
        "  1. Review connected devices on your router admin page\n"
        "  2. Change Wi-Fi password if unauthorized devices found\n"
        "  3. Enable MAC address filtering on your router"
    ),
    "gateway_unreachable": (
        "🔌 GATEWAY UNREACHABLE\n\n"
        "Diagnosis: Cannot reach the default gateway (router).\n\n"
        "Recommended fix:\n"
        "  1. Check physical cable connections\n"
        "  2. Restart router and network adapter\n"
        "  3. Run: ipconfig /release && ipconfig /renew"
    ),
}


def _build_fallback_diagnosis(anomaly_type: str, metrics: dict) -> str:
    """Build a local diagnosis when the LLM API is unreachable."""
    base = _FALLBACK_DIAGNOSES.get(anomaly_type)
    if not base:
        base = (
            f"⚠️ ANOMALY DETECTED: {anomaly_type}\n\n"
            "The LLM agent could not connect to the API to provide a detailed "
            "diagnosis. Please check your network connection and try again."
        )

    metric_lines = "\n".join(f"  {k}: {v}" for k, v in metrics.items())
    return f"{base}\n\nCurrent Metrics:\n{metric_lines}"
