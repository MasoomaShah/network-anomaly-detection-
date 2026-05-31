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
from agent.tools import TOOL_DEFINITIONS, FIX_TOOL_NAMES
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

        # ── PRE-AGENT FIX: DNS failure catch-22 ─────────────────────────
        # Problem: If DNS is broken, we can't reach the OpenAI API to think.
        # Solution: Fix DNS FIRST, then let the LLM reason and verify.
        pre_fix_result = None
        anomaly_type = alert.get("anomaly_type", "")

        if anomaly_type == "dns_failure":
            from agent.tools import switch_dns, check_dns
            memory.add_step("thought",
                            "DNS is broken — OpenAI API needs DNS to work. "
                            "Fixing DNS first so I can reason about this properly...")
            memory.write_state("acting", alert_id=alert_id)

            # Try switching to Google DNS
            pre_fix_result = switch_dns("8.8.8.8")
            memory.add_step("fix", "🔧 Fixing: switch_dns",
                            tool="switch_dns", tool_input="8.8.8.8")
            memory.add_step("observation", pre_fix_result)

            # If Google DNS didn't work, try Cloudflare
            if "❌" in pre_fix_result or "failed" in pre_fix_result.lower():
                pre_fix_result = switch_dns("1.1.1.1")
                memory.add_step("fix", "🔧 Fixing: switch_dns (Cloudflare fallback)",
                                tool="switch_dns", tool_input="1.1.1.1")
                memory.add_step("observation", pre_fix_result)

            import time as _time
            _time.sleep(2)  # let DNS propagate

            # Verify DNS is working now
            dns_check = check_dns("google.com")
            memory.add_step("observation", f"DNS verification after fix:\n{dns_check}")

            memory.add_step("thought",
                            "DNS fix applied. Now connecting to LLM to analyze "
                            "what happened and produce a full report...")
            memory.write_state("investigating", alert_id=alert_id)

        elif anomaly_type == "high_packet_loss":
            from agent.tools import terminate_clumsy, restart_interface
            memory.add_step("thought",
                            "High packet loss detected. If this is a simulated disruption using Clumsy, "
                            "terminating the simulation process first...")
            memory.write_state("acting", alert_id=alert_id)

            pre_fix_result = terminate_clumsy("")
            memory.add_step("fix", "🔧 Fixing: terminate_clumsy",
                            tool="terminate_clumsy", tool_input="")
            memory.add_step("observation", pre_fix_result)

            # Also restart the network interface to clear any hanging packets/connections
            memory.add_step("thought", "Restarting network interface to fully restore connectivity...")
            iface_result = restart_interface("")
            memory.add_step("fix", "🔧 Fixing: restart_interface",
                            tool="restart_interface", tool_input="")
            memory.add_step("observation", iface_result)

            pre_fix_result = f"{pre_fix_result}\n{iface_result}"

            import time as _time
            _time.sleep(3)
            memory.add_step("thought", "Fixes applied. Now connecting to LLM for analysis...")
            memory.write_state("investigating", alert_id=alert_id)

        elif anomaly_type == "gateway_unreachable":
            # If gateway is unreachable, try restart_interface first
            # so the LLM API becomes reachable
            import socket as _socket
            try:
                _socket.setdefaulttimeout(5)
                _socket.gethostbyname("api.openai.com")
            except Exception:
                # API unreachable — fix connectivity first
                from agent.tools import restart_interface
                memory.add_step("thought",
                                "Gateway/network appears down — can't reach LLM API. "
                                "Restarting network interface first...")
                memory.write_state("acting", alert_id=alert_id)

                pre_fix_result = restart_interface("")
                memory.add_step("fix", "🔧 Fixing: restart_interface",
                                tool="restart_interface", tool_input="")
                memory.add_step("observation", pre_fix_result)

                import time as _time
                _time.sleep(3)

                memory.add_step("thought",
                                "Interface restarted. Now connecting to LLM for analysis...")
                memory.write_state("investigating", alert_id=alert_id)

        # Invoke the agent graph
        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=user_input),
        ]

        # Add context about pre-fix if one was applied
        if pre_fix_result:
            messages.append(HumanMessage(
                content=f"NOTE: Before you started, the system automatically applied a fix:\n"
                        f"{pre_fix_result}\n\n"
                        f"Please verify if this fix resolved the issue and provide your analysis."
            ))

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
                    tool_name = tc['name']
                    is_fix = tool_name in FIX_TOOL_NAMES

                    # Update state to "acting" when a fix tool is called
                    if is_fix:
                        memory.write_state("acting", alert_id=alert_id)

                    step_type = "fix" if is_fix else "action"
                    memory.add_step(
                        step_type,
                        f"{'🔧 Fixing' if is_fix else 'Calling'}: {tool_name}",
                        tool=tool_name,
                        tool_input=str(tc.get("args", "")),
                    )
                    steps.append({
                        "tool": tool_name,
                        "input": str(tc.get("args", "")),
                        "output": "",
                        "is_fix": is_fix,
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
        "Note: LLM agent could not connect to OpenAI API because DNS is down. "
        "This diagnosis was generated locally."
    ),
    "high_packet_loss": (
        "📉 HIGH PACKET LOSS DETECTED\n\n"
        "Diagnosis: Significant packet loss detected on the network.\n\n"
        "Possible causes:\n"
        "  - Network congestion or overloaded router\n"
        "  - Faulty network cable or Wi-Fi interference\n"
        "  - ISP-side issue"
    ),
    "bandwidth_saturation": (
        "🌊 BANDWIDTH SATURATION DETECTED\n\n"
        "Diagnosis: Network bandwidth is fully utilized.\n\n"
        "Possible causes:\n"
        "  - Large file upload/download in progress\n"
        "  - Multiple devices streaming simultaneously\n"
        "  - Background cloud sync or updates"
    ),
    "unexpected_devices": (
        "📱 UNEXPECTED DEVICES DETECTED\n\n"
        "Diagnosis: New or unknown devices have joined the network."
    ),
    "gateway_unreachable": (
        "🔌 GATEWAY UNREACHABLE\n\n"
        "Diagnosis: Cannot reach the default gateway (router)."
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
