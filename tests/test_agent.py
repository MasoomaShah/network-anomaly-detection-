"""
test_agent.py — Unit tests for the agent module
==================================================
Tests config, prompts, memory, tools, and trigger logic.
"""

import os
import sys
import json
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "collector"))


# ── Config Tests ─────────────────────────────────────────────────────────

class TestConfig:
    """Test agent configuration module."""

    def test_paths_are_absolute(self):
        from agent.config import BASE_DIR, DATA_DIR, ALERTS_PATH
        assert os.path.isabs(BASE_DIR)
        assert os.path.isabs(DATA_DIR)
        assert os.path.isabs(ALERTS_PATH)

    def test_platform_detection(self):
        from agent.config import IS_WINDOWS, IS_LINUX
        import platform
        if platform.system() == "Windows":
            assert IS_WINDOWS is True
        elif platform.system() == "Linux":
            assert IS_LINUX is True

    def test_llm_display_name(self):
        from agent.config import get_llm_display_name
        name = get_llm_display_name()
        assert isinstance(name, str)
        assert len(name) > 0

    def test_get_llm_raises_without_key(self, monkeypatch):
        """get_llm should raise if GROQ_API_KEY is empty and provider is groq."""
        monkeypatch.setenv("LLM_PROVIDER", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "")
        from agent.config import get_llm
        with pytest.raises(ValueError, match="GROQ_API_KEY"):
            get_llm()

    def test_unknown_provider_raises(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "invalid_provider")
        from agent.config import get_llm
        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
            get_llm()


# ── Prompts Tests ────────────────────────────────────────────────────────

class TestPrompts:
    """Test prompt templates."""

    def test_system_prompt_has_placeholder(self):
        from agent.prompts import SYSTEM_PROMPT
        assert "{anomaly_context}" in SYSTEM_PROMPT

    def test_system_prompt_not_empty(self):
        from agent.prompts import SYSTEM_PROMPT
        assert len(SYSTEM_PROMPT) > 100

    def test_build_agent_input(self, sample_alert):
        from agent.prompts import build_agent_input
        result = build_agent_input(sample_alert)
        assert isinstance(result, str)
        assert "high_packet_loss" in result
        assert len(result) > 50


# ── Memory Tests ─────────────────────────────────────────────────────────

class TestMemory:
    """Test agent memory read/write operations."""

    def test_write_and_read_state(self, tmp_path, monkeypatch):
        from agent import memory
        state_path = str(tmp_path / "agent_state.json")
        monkeypatch.setattr("agent.config.AGENT_STATE_PATH", state_path)

        memory.write_state("investigating", alert_id=42)
        state = memory.read_state()

        assert state["status"] == "investigating"
        assert state["alert_id"] == 42

    def test_add_step(self, tmp_path, monkeypatch):
        from agent import memory
        state_path = str(tmp_path / "agent_state.json")
        monkeypatch.setattr("agent.config.AGENT_STATE_PATH", state_path)

        memory.write_state("investigating")
        memory.add_step("thought", "Testing step")
        state = memory.read_state()

        assert len(state.get("steps", [])) >= 1
        assert state["steps"][-1]["type"] == "thought"
        assert state["steps"][-1]["content"] == "Testing step"

    def test_append_log(self, tmp_path, monkeypatch, sample_alert):
        from agent import memory
        log_path = str(tmp_path / "agent_log.json")
        monkeypatch.setattr("agent.config.AGENT_LOG_PATH", log_path)
        monkeypatch.setattr("agent.config.DATA_DIR", str(tmp_path))

        memory.append_log(sample_alert, [], "Test answer", outcome="resolved")

        with open(log_path) as f:
            logs = json.load(f)
        assert len(logs) == 1
        assert logs[0]["outcome"] == "resolved"

    def test_update_alert_status(self, tmp_path, monkeypatch, sample_alert):
        from agent import memory
        alerts_path = str(tmp_path / "alerts.json")
        with open(alerts_path, "w") as f:
            json.dump([sample_alert], f)
        monkeypatch.setattr("agent.config.ALERTS_PATH", alerts_path)

        memory.update_alert_status(1, "resolved")

        with open(alerts_path) as f:
            alerts = json.load(f)
        assert alerts[0]["status"] == "resolved"


# ── Trigger Tests ────────────────────────────────────────────────────────

class TestTrigger:
    """Test the trigger module — rule checking and demo scenarios."""

    def test_demo_scenarios_exist(self):
        from agent.trigger import DEMO_SCENARIOS
        assert len(DEMO_SCENARIOS) >= 4
        assert "dns_failure" in DEMO_SCENARIOS
        assert "packet_loss" in DEMO_SCENARIOS
        assert "bandwidth_flood" in DEMO_SCENARIOS
        assert "unknown_device" in DEMO_SCENARIOS

    def test_demo_scenario_format(self):
        from agent.trigger import DEMO_SCENARIOS
        for name, scenario in DEMO_SCENARIOS.items():
            assert "anomaly_type" in scenario, f"{name} missing anomaly_type"
            assert "severity" in scenario, f"{name} missing severity"
            assert "metrics" in scenario, f"{name} missing metrics"
            assert len(scenario["metrics"]) == 8, f"{name} should have 8 metrics"

    def test_check_rules_normal(self, sample_metrics):
        from agent.trigger import _check_rules
        result = _check_rules(sample_metrics)
        assert result is None, "Normal metrics should not trigger rules"

    def test_check_rules_high_latency(self, tmp_path, monkeypatch):
        from agent.trigger import _check_rules
        # Monkeypatch to avoid file writes
        alerts_path = str(tmp_path / "alerts.json")
        monkeypatch.setattr("agent.trigger.ALERTS_PATH", alerts_path)
        data_dir = str(tmp_path)
        monkeypatch.setattr("agent.trigger.DATA_DIR", data_dir)

        metrics = {"latency_ms": 350, "packet_loss_pct": 0, "download_mbps": 50,
                   "upload_mbps": 10, "dns_response_ms": 15, "gateway_ping_ms": 5,
                   "jitter_ms": 3, "connected_devices": 4}
        result = _check_rules(metrics)
        assert result is not None
        assert result["anomaly_type"] == "high_latency"

    def test_inject_demo_alert_invalid(self):
        from agent.trigger import inject_demo_alert
        with pytest.raises(ValueError, match="Unknown scenario"):
            inject_demo_alert("nonexistent_scenario")


# ── Tools Tests ──────────────────────────────────────────────────────────

class TestTools:
    """Test agent diagnostic tools."""

    def test_tool_registry_count(self):
        from agent.tools import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 7, "Should have at least 7 tools registered"

    def test_tool_registry_format(self):
        from agent.tools import TOOL_DEFINITIONS
        for td in TOOL_DEFINITIONS:
            assert "name" in td, "Tool missing name"
            assert "func" in td, "Tool missing func"
            assert "description" in td, "Tool missing description"
            assert callable(td["func"]), f"Tool {td['name']} func is not callable"

    def test_tool_names_unique(self):
        from agent.tools import TOOL_DEFINITIONS
        names = [td["name"] for td in TOOL_DEFINITIONS]
        assert len(names) == len(set(names)), "Duplicate tool names found"

    def test_check_dns_returns_string(self):
        from agent.tools import check_dns
        result = check_dns("localhost")
        assert isinstance(result, str)
        assert "DNS" in result

    def test_speedtest_returns_string(self):
        from agent.tools import run_speedtest
        result = run_speedtest("")
        assert isinstance(result, str)
        assert "Mbps" in result or "error" in result.lower()


# ── Agent Fallback Tests ────────────────────────────────────────────────

class TestAgentFallback:
    """Test the fallback diagnosis system."""

    def test_fallback_for_known_anomaly(self):
        from agent.agent import _build_fallback_diagnosis
        result = _build_fallback_diagnosis("dns_failure", {"dns_response_ms": 9999})
        assert isinstance(result, str)
        assert "DNS" in result.upper()
        assert "9999" in result

    def test_fallback_for_unknown_anomaly(self):
        from agent.agent import _build_fallback_diagnosis
        result = _build_fallback_diagnosis("some_weird_anomaly", {"latency_ms": 500})
        assert isinstance(result, str)
        assert "ANOMALY DETECTED" in result.upper()

    def test_fallback_includes_metrics(self):
        from agent.agent import _build_fallback_diagnosis
        metrics = {"latency_ms": 200, "jitter_ms": 50}
        result = _build_fallback_diagnosis("high_packet_loss", metrics)
        assert "latency_ms" in result
        assert "200" in result
