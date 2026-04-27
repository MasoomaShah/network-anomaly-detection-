"""
inference.py — LSTM Autoencoder Real-Time Inference
====================================================
Runs on Raspberry Pi 4. Loads trained Keras model,
collects live network metrics, detects anomalies via
reconstruction error, and writes alerts to a JSON file
for the agentic layer to consume.

Directory layout expected:
    project/
    ├── inference/
    │   └── inference.py          ← this file
    ├── collector/
    │   ├── collector.py
    │   └── metrics.py
    ├── models/
    │   ├── lstm_autoencoder.keras
    │   └── threshold.npy
    └── data/
        └── alerts.json           ← agent reads this
"""

import os
import sys
import time
import json
import logging
import datetime
import collections

import numpy as np
import tensorflow as tf

# ── path setup so we can import metrics.py from collector/ ──────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLLECTOR_DIR = os.path.join(BASE_DIR, "collector")
sys.path.insert(0, COLLECTOR_DIR)

from metrics import get_all_metrics          # your existing metrics.py

# ── config ───────────────────────────────────────────────────────────────────
MODEL_PATH  = os.path.join(BASE_DIR, "models", "lstm_autoencoder.h5")
THRESHOLD_PATH = os.path.join(BASE_DIR, "models", "threshold.npy")
ALERTS_PATH = os.path.join(BASE_DIR, "data",   "alerts.json")

TIMESTEPS   = 60          # must match training (60 steps × 5 s = 5 min window)
N_FEATURES  = 8
INTERVAL_S  = 5           # seconds between metric samples
COOLDOWN_S  = 60          # minimum seconds between two anomaly alerts

FEATURES = [
    "latency_ms", "packet_loss_pct", "download_mbps", "upload_mbps",
    "connected_devices", "dns_response_ms", "gateway_ping_ms", "jitter_ms",
]

# ── logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("inference")


# ── helpers ──────────────────────────────────────────────────────────────────

def load_artifacts():
    """Load Keras model and threshold from disk. Crash early if missing."""
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"Model not found at {MODEL_PATH}\n"
            "Copy lstm_autoencoder.keras from Colab to models/ on the RPi."
        )

    log.info("Loading model  → %s", MODEL_PATH)
    model = tf.keras.models.load_model(MODEL_PATH, compile=False, custom_objects=None)


    # Load threshold
    if os.path.exists(THRESHOLD_PATH):
        threshold = float(np.load(THRESHOLD_PATH))
        log.info("Loaded anomaly threshold: %.6f", threshold)
    else:
        # Fallback: use env var or default
        threshold = float(
            os.environ.get("ANOMALY_THRESHOLD", 0.05)
        )
        log.warning(
            "threshold.npy not found — using fallback %.6f. "
            "Set env var ANOMALY_THRESHOLD or copy threshold.npy to models/.",
            threshold,
        )

    return model, threshold


def collect_one_sample():
    """
    Collect a single row of 8 metrics.
    Returns a dict and a numpy array of shape (N_FEATURES,).
    """
    raw = get_all_metrics()
    vec = np.array([raw[f] for f in FEATURES], dtype=np.float32)
    return raw, vec


def compute_reconstruction_error(model, sequence_scaled):
    """
    sequence_scaled : (TIMESTEPS, N_FEATURES) — already normalized
    Returns scalar MSE reconstruction error.
    """
    x = sequence_scaled[np.newaxis, ...]           # (1, 60, 8)
    x_hat = model.predict(x, verbose=0)            # (1, 60, 8)
    error = float(np.mean(np.square(x - x_hat)))
    return error


def classify_anomaly(raw_metrics, error, threshold):
    """
    Simple rule-based classifier to give the agent a head-start on root cause.
    Returns a dict with anomaly_type and severity.
    """
    anomaly_type = "unknown"
    severity     = "medium"

    lat  = raw_metrics.get("latency_ms",      0)
    loss = raw_metrics.get("packet_loss_pct", 0)
    dl   = raw_metrics.get("download_mbps",   0)
    ul   = raw_metrics.get("upload_mbps",     0)
    dns  = raw_metrics.get("dns_response_ms", 0)
    gw   = raw_metrics.get("gateway_ping_ms", 0)
    jit  = raw_metrics.get("jitter_ms",       0)
    dev  = raw_metrics.get("connected_devices", 0)

    # Priority order — first match wins
    if loss > 20:
        anomaly_type = "high_packet_loss"
        severity     = "high" if loss > 50 else "medium"
    elif gw > 200 or gw >= 999:
        anomaly_type = "gateway_unreachable"
        severity     = "high"
    elif dns > 2000 or dns >= 9999:
        anomaly_type = "dns_failure"
        severity     = "high"
    elif dl > 80 or ul > 40:
        anomaly_type = "bandwidth_saturation"
        severity     = "medium"
    elif lat > 300:
        anomaly_type = "high_latency"
        severity     = "medium" if lat < 600 else "high"
    elif jit > 100:
        anomaly_type = "high_jitter"
        severity     = "low"
    elif dev > 15:                                   # tune for your network
        anomaly_type = "unexpected_devices"
        severity     = "medium"

    return {"anomaly_type": anomaly_type, "severity": severity}


def write_alert(raw_metrics, error, threshold, classification):
    """
    Append an alert record to data/alerts.json.
    The agentic layer watches this file and wakes up on new entries.
    """
    os.makedirs(os.path.dirname(ALERTS_PATH), exist_ok=True)

    # Load existing alerts (or start fresh)
    if os.path.exists(ALERTS_PATH):
        with open(ALERTS_PATH, "r") as f:
            try:
                alerts = json.load(f)
            except json.JSONDecodeError:
                alerts = []
    else:
        alerts = []

    alert = {
        "id":                  len(alerts) + 1,
        "timestamp":           datetime.datetime.now().isoformat(),
        "reconstruction_error": round(error, 6),
        "threshold":           round(threshold, 6),
        "error_ratio":         round(error / threshold, 3),   # >1 = anomaly
        "anomaly_type":        classification["anomaly_type"],
        "severity":            classification["severity"],
        "metrics":             {k: round(v, 3) for k, v in raw_metrics.items()
                                if k != "timestamp"},
        "status":              "pending",   # agent updates this to "resolved"
    }

    alerts.append(alert)

    with open(ALERTS_PATH, "w") as f:
        json.dump(alerts, f, indent=2)

    return alert


def print_status_line(step, error, threshold, raw):
    """One-line live status printed every sample."""
    flag = "🔴 ANOMALY" if error > threshold else "🟢 normal "
    print(
        f"[{step:>5}] {flag} | "
        f"err={error:.5f} thr={threshold:.5f} | "
        f"lat={raw['latency_ms']:>7.1f}ms "
        f"loss={raw['packet_loss_pct']:>5.1f}% "
        f"dl={raw['download_mbps']:>6.2f}Mbps "
        f"dns={raw['dns_response_ms']:>7.1f}ms "
        f"gw={raw['gateway_ping_ms']:>7.1f}ms "
        f"jitter={raw['jitter_ms']:>6.1f}ms "
        f"dev={raw['connected_devices']:>3}"
    )


# ── main loop ────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("   LSTM Autoencoder — Real-Time Network Anomaly Inference")
    print("   Building buffer of 60 samples before first prediction...")
    print("=" * 70)

    model, threshold = load_artifacts()

    # Sliding window buffer — holds the last TIMESTEPS raw (unscaled) vectors
    buffer = collections.deque(maxlen=TIMESTEPS)

    last_alert_time = 0   # unix timestamp of last fired alert
    step = 0

    while True:
        loop_start = time.time()

        # 1. Collect one sample
        try:
            raw, vec = collect_one_sample()
        except Exception as e:
            log.error("Metric collection failed: %s", e)
            time.sleep(INTERVAL_S)
            continue

        # 2. Add to buffer
        buffer.append(vec)
        step += 1

        # 3. Wait until buffer is full (first TIMESTEPS × INTERVAL_S seconds)
        if len(buffer) < TIMESTEPS:
            remaining = TIMESTEPS - len(buffer)
            print(f"  Warming up buffer … {len(buffer)}/{TIMESTEPS} "
                  f"({remaining * INTERVAL_S}s remaining)")
            elapsed = time.time() - loop_start
            time.sleep(max(0, INTERVAL_S - elapsed))
            continue

        # 4. Prepare the window (raw features, no scaler needed)
        window = np.array(buffer, dtype=np.float32)       # (60, 8)

        # 5. Run inference
        error = compute_reconstruction_error(model, window)

        # 6. Print status
        print_status_line(step, error, threshold, raw)

        # 7. Fire alert if anomaly detected (with cooldown to avoid spam)
        if error > threshold:
            now = time.time()
            if (now - last_alert_time) >= COOLDOWN_S:
                classification = classify_anomaly(raw, error, threshold)
                alert = write_alert(raw, error, threshold, classification)
                last_alert_time = now
                log.warning(
                    "ANOMALY ALERT #%d → type=%s  severity=%s  "
                    "error=%.5f (%.1fx threshold)",
                    alert["id"],
                    classification["anomaly_type"],
                    classification["severity"],
                    error,
                    error / threshold,
                )
            else:
                secs_left = int(COOLDOWN_S - (now - last_alert_time))
                log.info(
                    "Anomaly detected but in cooldown (%ds left)", secs_left
                )

        # 8. Sleep for remainder of interval
        elapsed = time.time() - loop_start
        time.sleep(max(0, INTERVAL_S - elapsed))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except FileNotFoundError as e:
        print(f"\n[SETUP ERROR] {e}")
        sys.exit(1)
