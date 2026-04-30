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
