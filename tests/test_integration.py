"""
test_integration.py — End-to-end integration tests
"""
import os, sys, json, datetime, pytest
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "collector"))


class TestAlertPipeline:
    """Test the full alert flow: classify → write → read."""

    def test_classification_to_alert(self, tmp_path, monkeypatch):
        from inference.inference import classify_anomaly_type, write_alert
        alerts_path = str(tmp_path / "alerts.json")
        monkeypatch.setattr("inference.inference.ALERTS_PATH", alerts_path)

        metrics = {"latency_ms": 50, "packet_loss_pct": 30, "download_mbps": 10,
                   "upload_mbps": 5, "dns_response_ms": 15, "gateway_ping_ms": 5,
                   "jitter_ms": 3, "connected_devices": 4}

        classification = classify_anomaly_type(metrics)
        assert classification is not None
        alert = write_alert(metrics, 5.0, 3.0, classification)

        with open(alerts_path) as f:
            alerts = json.load(f)
        assert len(alerts) == 1
        assert alerts[0]["anomaly_type"] == "high_packet_loss"
        assert alerts[0]["status"] == "pending"

    def test_memory_state_cycle(self, tmp_path, monkeypatch):
        from agent import memory
        sp = str(tmp_path / "state.json")
        lp = str(tmp_path / "log.json")
        ap = str(tmp_path / "alerts.json")
        monkeypatch.setattr("agent.config.AGENT_STATE_PATH", sp)
        monkeypatch.setattr("agent.config.AGENT_LOG_PATH", lp)
        monkeypatch.setattr("agent.config.ALERTS_PATH", ap)
        monkeypatch.setattr("agent.config.DATA_DIR", str(tmp_path))

        memory.write_state("idle")
        assert memory.read_state()["status"] == "idle"

        memory.write_state("investigating", alert_id=1)
        memory.add_step("thought", "Starting investigation")
        memory.add_step("action", "Running ping", tool="ping_test", tool_input="8.8.8.8")
        memory.add_step("observation", "Ping OK")

        state = memory.read_state()
        assert state["status"] == "investigating"
        assert len(state["steps"]) == 3

    def test_demo_scenario_injects_alert(self, tmp_path, monkeypatch):
        from agent.trigger import inject_demo_alert, DEMO_SCENARIOS
        ap = str(tmp_path / "alerts.json")
        dp = str(tmp_path)
        lmp = str(tmp_path / "live_metrics.json")
        monkeypatch.setattr("agent.trigger.ALERTS_PATH", ap)
        monkeypatch.setattr("agent.trigger.DATA_DIR", dp)
        monkeypatch.setattr("agent.trigger.LIVE_METRICS_PATH", lmp)

        alert = inject_demo_alert("dns_failure")
        assert alert["anomaly_type"] == "dns_failure"
        assert alert["source"] == "demo"

        with open(ap) as f:
            alerts = json.load(f)
        assert len(alerts) == 1


class TestRuleBasedTrigger:
    """Test rule-based anomaly detection matches inference classification."""

    def test_rules_match_inference_classification(self, anomalous_metrics, tmp_path, monkeypatch):
        from inference.inference import classify_anomaly_type
        from agent.trigger import _check_rules
        ap = str(tmp_path / "alerts.json")
        dp = str(tmp_path)
        monkeypatch.setattr("agent.trigger.ALERTS_PATH", ap)
        monkeypatch.setattr("agent.trigger.DATA_DIR", dp)

        for name, metrics in anomalous_metrics.items():
            inf_result = classify_anomaly_type(metrics)
            rule_result = _check_rules(metrics)
            assert inf_result is not None, f"Inference missed {name}"
            assert rule_result is not None, f"Rules missed {name}"


class TestDashboardDataFlow:
    """Test that dashboard can read data written by other modules."""

    def test_live_metrics_readable(self, tmp_path, monkeypatch):
        from inference.inference import save_live_metrics
        path = str(tmp_path / "live_metrics.json")
        monkeypatch.setattr("inference.inference.LIVE_METRICS_PATH", path)

        save_live_metrics({"latency_ms": 25.0, "packet_loss_pct": 0.0,
                           "download_mbps": 50.0, "upload_mbps": 10.0,
                           "connected_devices": 4, "dns_response_ms": 15.0,
                           "gateway_ping_ms": 5.0, "jitter_ms": 3.0})

        with open(path) as f:
            data = json.load(f)
        assert "timestamp" in data
        assert data["metrics"]["latency_ms"] == 25.0

    def test_alerts_json_format(self, tmp_path, monkeypatch):
        from inference.inference import write_alert
        ap = str(tmp_path / "alerts.json")
        monkeypatch.setattr("inference.inference.ALERTS_PATH", ap)

        for i in range(3):
            write_alert({"latency_ms": 200+i}, 5.0, 3.0,
                        {"anomaly_type": "test", "severity": "low"})

        with open(ap) as f:
            alerts = json.load(f)
        assert len(alerts) == 3
        assert alerts[0]["id"] == 1
        assert alerts[2]["id"] == 3
