"""
trigger.py — Dual-Mode Anomaly Trigger System
==============================================
Mode 1: Rule-based  — polls metrics, fires on threshold breach
Mode 2: LSTM-watch  — watches alerts.json for new entries from inference.py
Mode 3: Manual demo — pre-built fake anomalies for demo day
"""

import os
import sys
import json
import time
import datetime
import threading
import logging

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_COLLECTOR = os.path.join(_BASE, "collector")
if _COLLECTOR not in sys.path:
    sys.path.insert(0, _COLLECTOR)

from agent.config import ALERTS_PATH, LIVE_METRICS_PATH, DATA_DIR
from agent.agent import run_agent
from agent import memory

log = logging.getLogger("trigger")
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")


# ── Rule-based thresholds ────────────────────────────────────────────────

RULES = {
    "latency_ms":        {"warn": 150,  "crit": 300,  "direction": "above"},
    "packet_loss_pct":   {"warn": 5,    "crit": 15,   "direction": "above"},
    "download_mbps":     {"warn": 1.0,  "crit": 0.3,  "direction": "below"},
    "dns_response_ms":   {"warn": 1000, "crit": 3000, "direction": "above"},
    "gateway_ping_ms":   {"warn": 100,  "crit": 500,  "direction": "above"},
    "jitter_ms":         {"warn": 80,   "crit": 150,  "direction": "above"},
}

ANOMALY_MAP = {
    "latency_ms":      "high_latency",
    "packet_loss_pct": "high_packet_loss",
    "download_mbps":   "bandwidth_saturation",
    "dns_response_ms": "dns_failure",
    "gateway_ping_ms": "gateway_unreachable",
    "jitter_ms":       "high_jitter",
}


def _check_rules(metrics: dict) -> dict | None:
    """Check metrics against rules. Returns alert dict or None."""
    for feature, rule in RULES.items():
        val = metrics.get(feature, 0)
        direction = rule["direction"]

        is_crit = (val > rule["crit"]) if direction == "above" else (val < rule["crit"])
        is_warn = (val > rule["warn"]) if direction == "above" else (val < rule["warn"])

        if is_crit:
            return _build_alert(metrics, ANOMALY_MAP.get(feature, "unknown"), "high")
        elif is_warn:
            return _build_alert(metrics, ANOMALY_MAP.get(feature, "unknown"), "medium")

    return None


def _build_alert(metrics: dict, anomaly_type: str, severity: str) -> dict:
    """Build an alert dict in the same format as inference.py."""
    os.makedirs(DATA_DIR, exist_ok=True)

    # Load existing alerts to get next ID
    alerts = []
    if os.path.exists(ALERTS_PATH):
        try:
            with open(ALERTS_PATH, "r") as f:
                alerts = json.load(f)
        except (json.JSONDecodeError, IOError):
            alerts = []

    alert = {
        "id": len(alerts) + 1,
        "timestamp": datetime.datetime.now().isoformat(),
        "reconstruction_error": 0,
        "threshold": 0,
        "error_ratio": 0,
        "anomaly_type": anomaly_type,
        "severity": severity,
        "metrics": {k: round(v, 3) if isinstance(v, float) else v
                    for k, v in metrics.items() if k != "timestamp"},
        "status": "pending",
        "source": "rule_based",
    }

    alerts.append(alert)
    with open(ALERTS_PATH, "w") as f:
        json.dump(alerts, f, indent=2)

    return alert


def _save_live_metrics(metrics: dict):
    """Write latest metrics to live_metrics.json for dashboard."""
    os.makedirs(DATA_DIR, exist_ok=True)
    data = {
        "timestamp": datetime.datetime.now().isoformat(),
        "metrics": metrics,
    }
    with open(LIVE_METRICS_PATH, "w") as f:
        json.dump(data, f, indent=2)


# ── Mode 1: Rule-based trigger loop ─────────────────────────────────────

def run_rule_based(interval: int = 10, cooldown: int = 60):
    """
    Continuously collect metrics, check rules, trigger agent on breach.
    interval: seconds between checks
    cooldown: minimum seconds between agent triggers
    """
    from metrics import get_all_metrics

    log.info("Starting RULE-BASED trigger (interval=%ds, cooldown=%ds)", interval, cooldown)
    memory.write_state("idle")
    last_trigger = 0

    while True:
        try:
            metrics = get_all_metrics()
            _save_live_metrics(metrics)

            alert = _check_rules(metrics)
            now = time.time()

            if alert and (now - last_trigger) >= cooldown:
                log.warning("ANOMALY: %s (%s)", alert["anomaly_type"], alert["severity"])
                last_trigger = now

                # Run agent in separate thread so monitoring continues
                thread = threading.Thread(target=run_agent, args=(alert,), daemon=True)
                thread.start()
            elif alert:
                log.info("Anomaly detected but in cooldown (%ds left)",
                         int(cooldown - (now - last_trigger)))

            time.sleep(interval)

        except KeyboardInterrupt:
            log.info("Stopped by user.")
            break
        except Exception as e:
            log.error("Trigger loop error: %s", e)
            time.sleep(interval)


# ── Mode 2: LSTM watcher ────────────────────────────────────────────────

def run_lstm_watcher(poll_interval: int = 3):
    """
    Watch alerts.json for new 'pending' alerts written by inference.py.
    When found, trigger the agent.
    """
    log.info("Starting LSTM WATCHER (polling alerts.json every %ds)", poll_interval)
    memory.write_state("idle")
    processed_ids = set()

    # Load already-processed IDs
    if os.path.exists(ALERTS_PATH):
        try:
            with open(ALERTS_PATH, "r") as f:
                for a in json.load(f):
                    processed_ids.add(a.get("id"))
        except Exception:
            pass

    while True:
        try:
            if os.path.exists(ALERTS_PATH):
                with open(ALERTS_PATH, "r") as f:
                    alerts = json.load(f)

                for alert in alerts:
                    aid = alert.get("id")
                    if aid not in processed_ids and alert.get("status") == "pending":
                        processed_ids.add(aid)
                        log.warning("New LSTM alert #%d: %s", aid, alert.get("anomaly_type"))
                        thread = threading.Thread(target=run_agent, args=(alert,), daemon=True)
                        thread.start()

            time.sleep(poll_interval)

        except KeyboardInterrupt:
            break
        except Exception as e:
            log.error("Watcher error: %s", e)
            time.sleep(poll_interval)


# ── Mode 3: Manual demo triggers ────────────────────────────────────────

DEMO_SCENARIOS = {
    "bandwidth_flood": {
        "anomaly_type": "bandwidth_saturation",
        "severity": "high",
        "metrics": {
            "latency_ms": 180.0,
            "packet_loss_pct": 5.0,
            "download_mbps": 0.8,
            "upload_mbps": 45.0,
            "connected_devices": 6,
            "dns_response_ms": 120.0,
            "gateway_ping_ms": 45.0,
            "jitter_ms": 65.0,
        },
    },
    "unknown_device": {
        "anomaly_type": "unexpected_devices",
        "severity": "medium",
        "metrics": {
            "latency_ms": 55.0,
            "packet_loss_pct": 0.0,
            "download_mbps": 12.0,
            "upload_mbps": 5.0,
            "connected_devices": 12,
            "dns_response_ms": 15.0,
            "gateway_ping_ms": 8.0,
            "jitter_ms": 10.0,
        },
    },
    "dns_failure": {
        "anomaly_type": "dns_failure",
        "severity": "high",
        "metrics": {
            "latency_ms": 60.0,
            "packet_loss_pct": 0.0,
            "download_mbps": 15.0,
            "upload_mbps": 8.0,
            "connected_devices": 4,
            "dns_response_ms": 9999.0,
            "gateway_ping_ms": 10.0,
            "jitter_ms": 12.0,
        },
    },
    "packet_loss": {
        "anomaly_type": "high_packet_loss",
        "severity": "high",
        "metrics": {
            "latency_ms": 350.0,
            "packet_loss_pct": 40.0,
            "download_mbps": 2.0,
            "upload_mbps": 0.5,
            "connected_devices": 4,
            "dns_response_ms": 800.0,
            "gateway_ping_ms": 250.0,
            "jitter_ms": 120.0,
        },
    },
}


def trigger_demo(scenario_name: str) -> dict:
    """
    Fire a fake anomaly for demo purposes.
    scenario_name: bandwidth_flood | unknown_device | dns_failure | packet_loss
    Returns the alert dict.
    """
    if scenario_name not in DEMO_SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario_name}. "
                         f"Options: {list(DEMO_SCENARIOS.keys())}")

    scenario = DEMO_SCENARIOS[scenario_name]
    alert = _build_alert(
        scenario["metrics"],
        scenario["anomaly_type"],
        scenario["severity"],
    )
    alert["source"] = "demo"
    log.info("Demo trigger: %s (alert #%d)", scenario_name, alert["id"])

    # Save live metrics so dashboard shows the anomalous values
    _save_live_metrics(scenario["metrics"])

    # Run agent
    result = run_agent(alert)
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Network Anomaly Trigger")
    parser.add_argument("--mode", choices=["rules", "lstm", "demo"], default="rules")
    parser.add_argument("--scenario", choices=list(DEMO_SCENARIOS.keys()), default="dns_failure")
    parser.add_argument("--interval", type=int, default=10)
    args = parser.parse_args()

    if args.mode == "rules":
        run_rule_based(interval=args.interval)
    elif args.mode == "lstm":
        run_lstm_watcher()
    elif args.mode == "demo":
        trigger_demo(args.scenario)
