"""
test_inference.py — Unit tests for the LSTM inference module
=============================================================
Tests anomaly classification, alert writing, and metric clamping.
"""

import os
import sys
import json
import numpy as np
import pytest

# Ensure project root is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from inference.inference import (
    classify_anomaly_type,
    write_alert,
    FEATURES,
    N_FEATURES,
    TIMESTEPS,
    collect_one_sample,
    save_live_metrics,
)


# ── classify_anomaly_type ────────────────────────────────────────────────

class TestClassifyAnomalyType:
    """Test the rule-based anomaly classifier."""

    def test_normal_metrics_returns_none(self, sample_metrics):
        """Normal metrics should NOT be classified as anomaly."""
        result = classify_anomaly_type(sample_metrics)
        assert result is None, f"Normal metrics should return None, got {result}"

    def test_high_packet_loss_detected(self):
        """Packet loss > 5% should be detected."""
        metrics = {"packet_loss_pct": 20.0, "latency_ms": 50, "download_mbps": 10,
                   "upload_mbps": 5, "dns_response_ms": 15, "gateway_ping_ms": 5,
                   "jitter_ms": 3, "connected_devices": 4}
        result = classify_anomaly_type(metrics)
        assert result is not None
        assert result["anomaly_type"] == "high_packet_loss"
        assert result["severity"] == "high"  # > 15%

    def test_medium_packet_loss(self):
        """Packet loss 5-15% should be medium severity."""
        metrics = {"packet_loss_pct": 8.0, "latency_ms": 50, "download_mbps": 10,
                   "upload_mbps": 5, "dns_response_ms": 15, "gateway_ping_ms": 5,
                   "jitter_ms": 3, "connected_devices": 4}
        result = classify_anomaly_type(metrics)
        assert result is not None
        assert result["anomaly_type"] == "high_packet_loss"
        assert result["severity"] == "medium"

    def test_dns_failure_detected(self):
        """DNS response >= 1000ms should be dns_failure."""
        metrics = {"packet_loss_pct": 0, "latency_ms": 50, "download_mbps": 10,
                   "upload_mbps": 5, "dns_response_ms": 2000, "gateway_ping_ms": 5,
                   "jitter_ms": 3, "connected_devices": 4}
        result = classify_anomaly_type(metrics)
        assert result is not None
        assert result["anomaly_type"] == "dns_failure"
        assert result["severity"] == "high"

    def test_gateway_unreachable(self):
        """Gateway ping > 100ms should be gateway_unreachable."""
        metrics = {"packet_loss_pct": 0, "latency_ms": 50, "download_mbps": 10,
                   "upload_mbps": 5, "dns_response_ms": 15, "gateway_ping_ms": 600,
                   "jitter_ms": 3, "connected_devices": 4}
        result = classify_anomaly_type(metrics)
        assert result is not None
        assert result["anomaly_type"] == "gateway_unreachable"
        assert result["severity"] == "high"  # > 500

    def test_high_latency_detected(self):
        """Latency > 150ms should be high_latency."""
        metrics = {"packet_loss_pct": 0, "latency_ms": 200, "download_mbps": 10,
                   "upload_mbps": 5, "dns_response_ms": 15, "gateway_ping_ms": 5,
                   "jitter_ms": 3, "connected_devices": 4}
        result = classify_anomaly_type(metrics)
        assert result is not None
        assert result["anomaly_type"] == "high_latency"

    def test_unexpected_devices(self):
        """connected_devices > 10 should be unexpected_devices."""
        metrics = {"packet_loss_pct": 0, "latency_ms": 30, "download_mbps": 10,
                   "upload_mbps": 5, "dns_response_ms": 15, "gateway_ping_ms": 5,
                   "jitter_ms": 3, "connected_devices": 15}
        result = classify_anomaly_type(metrics)
        assert result is not None
        assert result["anomaly_type"] == "unexpected_devices"

    def test_high_jitter(self):
        """Jitter > 80ms should be high_jitter."""
        metrics = {"packet_loss_pct": 0, "latency_ms": 30, "download_mbps": 10,
                   "upload_mbps": 5, "dns_response_ms": 15, "gateway_ping_ms": 5,
                   "jitter_ms": 100, "connected_devices": 4}
        result = classify_anomaly_type(metrics)
        assert result is not None
        assert result["anomaly_type"] == "high_jitter"

    def test_priority_order(self):
        """Packet loss should take priority over DNS failure when both are present."""
        metrics = {"packet_loss_pct": 20.0, "latency_ms": 50, "download_mbps": 10,
                   "upload_mbps": 5, "dns_response_ms": 5000, "gateway_ping_ms": 5,
                   "jitter_ms": 3, "connected_devices": 4}
        result = classify_anomaly_type(metrics)
        assert result["anomaly_type"] == "high_packet_loss"

    def test_empty_metrics(self):
        """Empty dict should return None (all defaults to 0)."""
        result = classify_anomaly_type({})
        assert result is None


# ── write_alert ──────────────────────────────────────────────────────────

class TestWriteAlert:
    """Test alert file writing."""

    def test_write_creates_file(self, tmp_path, monkeypatch):
        """write_alert should create alerts.json if it doesn't exist."""
        alerts_path = str(tmp_path / "alerts.json")
        monkeypatch.setattr("inference.inference.ALERTS_PATH", alerts_path)

        metrics = {"latency_ms": 200, "packet_loss_pct": 30}
        classification = {"anomaly_type": "high_packet_loss", "severity": "high"}

        alert = write_alert(metrics, 5.0, 3.0, classification)

        assert os.path.exists(alerts_path)
        assert alert["id"] == 1
        assert alert["anomaly_type"] == "high_packet_loss"
        assert alert["status"] == "pending"

    def test_write_appends_to_existing(self, tmp_path, monkeypatch, sample_alert):
        """write_alert should append to existing alerts."""
        alerts_path = str(tmp_path / "alerts.json")
        with open(alerts_path, "w") as f:
            json.dump([sample_alert], f)
        monkeypatch.setattr("inference.inference.ALERTS_PATH", alerts_path)

        classification = {"anomaly_type": "dns_failure", "severity": "high"}
        alert = write_alert({"dns_response_ms": 9999}, 4.0, 3.0, classification)

        with open(alerts_path) as f:
            alerts = json.load(f)
        assert len(alerts) == 2
        assert alerts[1]["id"] == 2

    def test_alert_has_required_fields(self, tmp_path, monkeypatch):
        """Alert dict should contain all required fields."""
        alerts_path = str(tmp_path / "alerts.json")
        monkeypatch.setattr("inference.inference.ALERTS_PATH", alerts_path)

        classification = {"anomaly_type": "test", "severity": "low", "source": "lstm"}
        alert = write_alert({"latency_ms": 100}, 2.0, 1.5, classification)

        required_keys = ["id", "timestamp", "reconstruction_error", "threshold",
                         "anomaly_type", "severity", "trigger_source", "metrics", "status"]
        for key in required_keys:
            assert key in alert, f"Missing required key: {key}"


# ── save_live_metrics ────────────────────────────────────────────────────

class TestSaveLiveMetrics:
    """Test live metrics writing for dashboard."""

    def test_saves_json(self, tmp_path, monkeypatch, sample_metrics):
        """Should write valid JSON to live_metrics.json."""
        path = str(tmp_path / "live_metrics.json")
        monkeypatch.setattr("inference.inference.LIVE_METRICS_PATH", path)

        save_live_metrics(sample_metrics)

        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert "timestamp" in data
        assert "metrics" in data
        assert data["metrics"]["latency_ms"] == 25.0


# ── Feature configuration ───────────────────────────────────────────────

class TestFeatureConfig:
    """Test feature list and constants."""

    def test_feature_count(self):
        """Should have exactly 8 features."""
        assert len(FEATURES) == 8
        assert N_FEATURES == 8

    def test_required_features_present(self):
        """All expected features should be in the list."""
        expected = ["latency_ms", "packet_loss_pct", "download_mbps", "upload_mbps",
                    "connected_devices", "dns_response_ms", "gateway_ping_ms", "jitter_ms"]
        for feat in expected:
            assert feat in FEATURES, f"Missing feature: {feat}"

    def test_timesteps(self):
        """LSTM window should be 60 timesteps."""
        assert TIMESTEPS == 60
