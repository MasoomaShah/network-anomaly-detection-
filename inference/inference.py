"""
inference.py — LSTM Autoencoder Real-Time Inference
====================================================
Runs on Raspberry Pi 4. Loads trained Keras model,
collects live network metrics, detects anomalies via
reconstruction error AND rule-based fallback, and writes
alerts to a JSON file for the agentic layer to consume.

Directory layout expected:
    project/
    ├── inference/
    │   └── inference.py          ← this file
    ├── collector/
    │   ├── collector.py
    │   └── metrics.py
    ├── models/
    │   ├── lstm_autoencoder.h5
    │   ├── threshold.npy
    │   └── scaler.pkl            ← optional but fixes the 200x error
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
from sklearn.preprocessing import MinMaxScaler
import joblib

# ── path setup ───────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLLECTOR_DIR = os.path.join(BASE_DIR, "collector")
sys.path.insert(0, COLLECTOR_DIR)

from metrics import get_all_metrics

# ── paths ────────────────────────────────────────────────────────────────────
MODEL_PATH     = os.path.join(BASE_DIR, "models", "lstm_autoencoder.h5")
THRESHOLD_PATH = os.path.join(BASE_DIR, "models", "threshold.npy")
SCALER_PATH    = os.path.join(BASE_DIR, "models", "scaler.pkl")
ALERTS_PATH    = os.path.join(BASE_DIR, "data",   "alerts.json")

# ── config ───────────────────────────────────────────────────────────────────
TIMESTEPS  = 60
N_FEATURES = 8
INTERVAL_S = 5
COOLDOWN_S = 10

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
    """
    Load model, threshold, and scaler.
    - model    : required (crashes if missing)
    - threshold: required (crashes if missing)
    - scaler   : optional (logs warning if missing — results will be worse)
    """
    # 1. Model
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"Model not found at {MODEL_PATH}\n"
            "Copy lstm_autoencoder.h5 from Colab to models/ on the RPi."
        )
    log.info("Loading model → %s", MODEL_PATH)
    model = tf.keras.models.load_model(MODEL_PATH, compile=False)

    # 2. Threshold
    if not os.path.exists(THRESHOLD_PATH):
        raise FileNotFoundError(
            f"Threshold not found at {THRESHOLD_PATH}\n"
            "Copy threshold.npy from Colab to models/ on the RPi."
        )
    threshold = float(np.load(THRESHOLD_PATH))
    log.info("Loaded anomaly threshold: %.6f", threshold)

    # 3. Scaler (optional but strongly recommended)
    if os.path.exists(SCALER_PATH):
        scaler = joblib.load(SCALER_PATH)
        log.info("Scaler loaded → %s", SCALER_PATH)
    else:
        scaler = None
        log.warning(
            "scaler.pkl not found — inference will run on raw values. "
            "This causes inflated reconstruction errors (200x+). "
            "Save your scaler in Colab: joblib.dump(scaler, 'scaler.pkl')"
        )

    return model, threshold, scaler


def collect_one_sample():
    """Returns (raw_dict, numpy_vector shape (N_FEATURES,))"""
    raw = get_all_metrics()
    # Fix: clamp DNS 9999 fallback so it doesn't destroy scaler std
    if raw.get("dns_response_ms", 0) >= 9999:
        raw["dns_response_ms"] = 2000.0   # treat as bad-but-real value
    vec = np.array([raw[f] for f in FEATURES], dtype=np.float32)
    return raw, vec


def compute_reconstruction_error(model, window, scaler=None):
    """
    window : (TIMESTEPS, N_FEATURES) raw values
    Scales if scaler provided, then runs model inference.
    Returns scalar MSE.
    """
    if scaler is not None:
        window = scaler.transform(window.reshape(-1, N_FEATURES)).reshape(TIMESTEPS, N_FEATURES)

    x     = window[np.newaxis, ...]        # (1, 60, 8)
    x_hat = model.predict(x, verbose=0)   # (1, 60, 8)
    error = float(np.mean(np.square(x - x_hat)))
    return error


def classify_anomaly(raw_metrics, error=None, threshold=None):
    """
    Rule-based anomaly classifier.
    Works independently of LSTM — used as primary or fallback trigger.
    Returns dict with anomaly_type and severity, or None if no anomaly.
    """
    lat  = raw_metrics.get("latency_ms",        0)
    loss = raw_metrics.get("packet_loss_pct",   0)
    dl   = raw_metrics.get("download_mbps",     0)
    ul   = raw_metrics.get("upload_mbps",       0)
    dns  = raw_metrics.get("dns_response_ms",   0)
    gw   = raw_metrics.get("gateway_ping_ms",   0)
    jit  = raw_metrics.get("jitter_ms",         0)
    dev  = raw_metrics.get("connected_devices", 0)

    anomaly_type = None
    severity     = "medium"

    # Priority order — first match wins
    if loss > 20:
        anomaly_type = "high_packet_loss"
        severity     = "high" if loss > 50 else "medium"
    elif gw > 200 or gw >= 999:
        anomaly_type = "gateway_unreachable"
        severity     = "high"
    elif dns >= 2000:
        anomaly_type = "dns_failure"
        severity     = "high"
    elif dl > 80 or ul > 40:
        anomaly_type = "bandwidth_saturation"
        severity     = "medium"
    elif lat > 300:
        anomaly_type = "high_latency"
        severity     = "medium" if lat < 600 else "high"
    elif jit > 150:
        anomaly_type = "high_jitter"
        severity     = "low"
    elif dev > 15:
        anomaly_type = "unexpected_devices"
        severity     = "medium"

    if anomaly_type is None:
        return None   # no anomaly — return None instead of "unknown"

    return {"anomaly_type": anomaly_type, "severity": severity}


def write_alert(raw_metrics, error, threshold, classification):
    """Append alert to alerts.json. Agent reads and updates status field."""
    os.makedirs(os.path.dirname(ALERTS_PATH), exist_ok=True)

    if os.path.exists(ALERTS_PATH):
        with open(ALERTS_PATH, "r") as f:
            try:
                alerts = json.load(f)
            except json.JSONDecodeError:
                alerts = []
    else:
        alerts = []

    alert = {
        "id":                   len(alerts) + 1,
        "timestamp":            datetime.datetime.now().isoformat(),
        "reconstruction_error": round(error, 6) if error else None,
        "threshold":            round(threshold, 6) if threshold else None,
        "error_ratio":          round(error / threshold, 3) if (error and threshold) else None,
        "anomaly_type":         classification["anomaly_type"],
        "severity":             classification["severity"],
        "trigger_source":       classification.get("source", "rule_based"),
        "metrics":              {k: round(float(v), 3) for k, v in raw_metrics.items()
                                 if k != "timestamp"},
        "status":               "pending",
    }

    alerts.append(alert)
    with open(ALERTS_PATH, "w") as f:
        json.dump(alerts, f, indent=2)

    return alert


def print_status_line(step, error, threshold, raw, trigger):
    """Live status line printed every sample."""
    if trigger:
        flag = f"🔴 ANOMALY [{trigger}]"
    else:
        flag = "🟢 normal "

    err_str = f"err={error:.3f} thr={threshold:.3f}" if error else "rule-trigger"
    print(
        f"[{step:>5}] {flag} | {err_str} | "
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
    print("   Network Anomaly Inference — LSTM + Rule-Based Fallback")
    print("=" * 70)

    model, threshold, scaler = load_artifacts()

    buffer          = collections.deque(maxlen=TIMESTEPS)
    last_alert_time = 0
    step            = 0

    while True:
        loop_start = time.time()

        # 1. Collect sample
        try:
            raw, vec = collect_one_sample()
        except Exception as e:
            log.error("Metric collection failed: %s", e)
            time.sleep(INTERVAL_S)
            continue

        buffer.append(vec)
        step += 1

        # 2. Warm-up period
        if len(buffer) < TIMESTEPS:
            remaining = TIMESTEPS - len(buffer)
            print(f"  Warming up buffer … {len(buffer)}/{TIMESTEPS} "
                  f"({remaining * INTERVAL_S}s remaining)")
            elapsed = time.time() - loop_start
            time.sleep(max(0, INTERVAL_S - elapsed))
            continue

        # 3. LSTM inference
        window = np.array(buffer, dtype=np.float32)
        try:
            error = compute_reconstruction_error(model, window, scaler)
            lstm_anomaly = error > threshold
        except Exception as e:
            log.error("LSTM inference failed: %s", e)
            error        = None
            lstm_anomaly = False

            # 4. Rule-based check (always runs)
        rule_classification = classify_anomaly(raw, error, threshold)

        # 5. Decide trigger source
        trigger_classification = None
        if lstm_anomaly:
            if rule_classification:
                # LSTM fired AND rules agree — best case, use rule label
                rule_classification["source"] = "lstm"
                trigger_classification = rule_classification
            else:
                # LSTM fired but metrics look okay — network is recovering
                # Only alert if error is significantly above threshold
                if error > threshold * 1.2:   # 20% buffer to avoid borderline noise
                    trigger_classification = {
                        "anomaly_type": "lstm_detected",
                        "severity": "medium",
                        "source": "lstm"
                    }
        elif rule_classification:
            rule_classification["source"] = "rule_based"
            trigger_classification = rule_classification

        # 6. Print status
        trigger_label = trigger_classification["anomaly_type"] if trigger_classification else None
        print_status_line(step, error, threshold, raw, trigger_label)

        # 7. Write alert with cooldown
        if trigger_classification:
            now = time.time()
            if (now - last_alert_time) >= COOLDOWN_S:
                alert = write_alert(raw, error, threshold, trigger_classification)
                last_alert_time = now
                log.warning(
                    "ANOMALY ALERT #%d → type=%s  severity=%s  source=%s",
                    alert["id"],
                    trigger_classification["anomaly_type"],
                    trigger_classification["severity"],
                    trigger_classification["source"],
                )
            else:
                secs_left = int(COOLDOWN_S - (now - last_alert_time))
                log.info("Anomaly detected but in cooldown (%ds left)", secs_left)

        # 8. Sleep
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
