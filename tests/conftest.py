"""
conftest.py — Shared fixtures for all tests
=============================================
"""

import os
import sys
import json
import shutil
import tempfile

import pytest

# Ensure project root is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "collector"))


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory for tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return str(data_dir)


@pytest.fixture
def sample_alert():
    """Return a sample alert dict matching the production format."""
    return {
        "id": 1,
        "timestamp": "2026-05-11T12:00:00",
        "reconstruction_error": 5.234,
        "threshold": 3.100,
        "error_ratio": 1.689,
        "anomaly_type": "high_packet_loss",
        "severity": "high",
        "trigger_source": "lstm",
        "metrics": {
            "latency_ms": 180.0,
            "packet_loss_pct": 40.0,
            "download_mbps": 2.0,
            "upload_mbps": 0.5,
            "connected_devices": 4,
            "dns_response_ms": 800.0,
            "gateway_ping_ms": 250.0,
            "jitter_ms": 120.0,
        },
        "status": "pending",
    }


@pytest.fixture
def sample_metrics():
    """Return a sample metrics dict with normal values."""
    return {
        "latency_ms": 25.0,
        "packet_loss_pct": 0.0,
        "download_mbps": 50.0,
        "upload_mbps": 10.0,
        "connected_devices": 4,
        "dns_response_ms": 15.0,
        "gateway_ping_ms": 5.0,
        "jitter_ms": 3.0,
    }


@pytest.fixture
def anomalous_metrics():
    """Return a dict of named anomalous metric sets."""
    return {
        "dns_failure": {
            "latency_ms": 60.0,
            "packet_loss_pct": 0.0,
            "download_mbps": 15.0,
            "upload_mbps": 8.0,
            "connected_devices": 4,
            "dns_response_ms": 9999.0,
            "gateway_ping_ms": 10.0,
            "jitter_ms": 12.0,
        },
        "high_packet_loss": {
            "latency_ms": 350.0,
            "packet_loss_pct": 40.0,
            "download_mbps": 2.0,
            "upload_mbps": 0.5,
            "connected_devices": 4,
            "dns_response_ms": 800.0,
            "gateway_ping_ms": 250.0,
            "jitter_ms": 120.0,
        },
        "gateway_unreachable": {
            "latency_ms": 999.0,
            "packet_loss_pct": 80.0,
            "download_mbps": 0.0,
            "upload_mbps": 0.0,
            "connected_devices": 2,
            "dns_response_ms": 9999.0,
            "gateway_ping_ms": 999.0,
            "jitter_ms": 999.0,
        },
        "bandwidth_saturation": {
            "latency_ms": 180.0,
            "packet_loss_pct": 5.0,
            "download_mbps": 0.8,
            "upload_mbps": 45.0,
            "connected_devices": 6,
            "dns_response_ms": 120.0,
            "gateway_ping_ms": 45.0,
            "jitter_ms": 65.0,
        },
    }


@pytest.fixture
def alerts_file(tmp_path, sample_alert):
    """Create a temporary alerts.json with one sample alert."""
    path = tmp_path / "alerts.json"
    path.write_text(json.dumps([sample_alert], indent=2))
    return str(path)
