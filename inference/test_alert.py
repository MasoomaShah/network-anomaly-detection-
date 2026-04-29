# test_alert.py — inject a fake anomaly to test the agent
import json, datetime, os

ALERTS_PATH = os.path.join("data", "alerts.json")
os.makedirs("data", exist_ok=True)

# Load existing
if os.path.exists(ALERTS_PATH):
    with open(ALERTS_PATH) as f:
        alerts = json.load(f)
else:
    alerts = []

# Pick whichever scenario you want to test
TEST_SCENARIOS = {
    "1": {"anomaly_type": "high_packet_loss",    "severity": "high",   "metrics": {"latency_ms": 180, "packet_loss_pct": 65, "download_mbps": 1.2, "upload_mbps": 0.5, "connected_devices": 3, "dns_response_ms": 45, "gateway_ping_ms": 55, "jitter_ms": 30}},
    "2": {"anomaly_type": "dns_failure",          "severity": "high",   "metrics": {"latency_ms": 75,  "packet_loss_pct": 0,  "download_mbps": 8.0, "upload_mbps": 2.1, "connected_devices": 3, "dns_response_ms": 8500, "gateway_ping_ms": 12, "jitter_ms": 8}},
    "3": {"anomaly_type": "gateway_unreachable",  "severity": "high",   "metrics": {"latency_ms": 999, "packet_loss_pct": 80, "download_mbps": 0.0, "upload_mbps": 0.0, "connected_devices": 2, "dns_response_ms": 9999, "gateway_ping_ms": 999, "jitter_ms": 999}},
    "4": {"anomaly_type": "unexpected_devices",   "severity": "medium", "metrics": {"latency_ms": 85,  "packet_loss_pct": 0,  "download_mbps": 2.1, "upload_mbps": 0.8, "connected_devices": 22, "dns_response_ms": 30, "gateway_ping_ms": 15, "jitter_ms": 12}},
}

print("\nChoose test scenario:")
print("  1 — High packet loss (65%)")
print("  2 — DNS failure")
print("  3 — Gateway unreachable")
print("  4 — Unexpected devices (22 on network)")
choice = input("\nEnter 1-4: ").strip()

s = TEST_SCENARIOS.get(choice)
if not s:
    print("Invalid choice."); exit()

alert = {
    "id":                   len(alerts) + 1,
    "timestamp":            datetime.datetime.now().isoformat(),
    "reconstruction_error": None,
    "threshold":            None,
    "error_ratio":          None,
    "anomaly_type":         s["anomaly_type"],
    "severity":             s["severity"],
    "trigger_source":       "manual_test",
    "metrics":              s["metrics"],
    "status":               "pending",
}

alerts.append(alert)
with open(ALERTS_PATH, "w") as f:
    json.dump(alerts, f, indent=2)

print(f"\n✅ Injected alert #{alert['id']} → {s['anomaly_type']} ({s['severity']})")
print(f"   Written to {ALERTS_PATH}")
print(f"   Agent should pick this up now.\n")