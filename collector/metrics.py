import subprocess
import socket
import time
import os
import psutil
import numpy as np
import requests
from agent.config import GATEWAY, NETWORK, PING_HOST, PI_HOST, PI_PORT, IS_WINDOWS


DNS_TEST_DOMAIN = "google.com"


# ── Ensure nmap is discoverable ──────────────────────────────────────────────
NMAP_DIR = r"C:\Program Files (x86)\Nmap"
if os.path.isdir(NMAP_DIR) and NMAP_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = NMAP_DIR + os.pathsep + os.environ.get("PATH", "")

def get_latency_loss_jitter(host=PING_HOST, count=4):
    """Single ping batch — returns latency, packet loss, jitter"""
    try:
        flag = "-n" if IS_WINDOWS else "-c"
        wait = "1000" if IS_WINDOWS else "1"
        result = subprocess.run(
            ["ping", flag, str(count), "-w", wait, host],   # fast timeout per ping
            capture_output=True, text=True, timeout=15
        )

        output = result.stdout
        loss = 0.0
        latency = 0.0
        jitter = 0.0

        times = []
        for line in output.split("\n"):
            if "time=" in line or "time<" in line:
                try:
                    t = line.split("time=")[-1].split("ms")[0].strip()
                    times.append(float(t))
                except:
                    pass
            if "Lost" in line or "loss" in line.lower():
                try:
                    loss = float(line.split("(")[1].split("%")[0].strip())
                except:
                    pass

        if times:
            latency = round(sum(times) / len(times), 2)
            jitter = round(np.std(times), 2)

        return latency, loss, jitter

    except Exception as e:
        print(f"[ping error] {e}")
        return 999.0, 100.0, 999.0


def get_bandwidth():
    """Measures actual bandwidth using psutil over 1 second window"""
    try:
        net1 = psutil.net_io_counters()
        time.sleep(1)
        net2 = psutil.net_io_counters()
        download = round((net2.bytes_recv - net1.bytes_recv) / 1e6 * 8, 3)
        upload = round((net2.bytes_sent - net1.bytes_sent) / 1e6 * 8, 3)
        return download, upload
    except Exception as e:
        print(f"[bandwidth error] {e}")
        return 0.0, 0.0


def get_dns_response(domain=DNS_TEST_DOMAIN):
    """Measures DNS resolution time in milliseconds"""
    try:
        start = time.time()
        socket.gethostbyname(domain)
        return round((time.time() - start) * 1000, 2)
    except Exception as e:
        print(f"[dns error] {e}")
        return 9999.0


def get_gateway_ping(gateway=GATEWAY):
    """Pings the router/gateway directly"""
    try:
        flag = "-n" if IS_WINDOWS else "-c"
        result = subprocess.run(
            ["ping", flag, "4", gateway],
            capture_output=True, text=True, timeout=15
        )

        times = []
        for line in result.stdout.split("\n"):
            if "time=" in line:
                try:
                    t = line.split("time=")[-1].split("ms")[0].strip()
                    times.append(float(t))
                except:
                    pass
        if times:
            return round(sum(times) / len(times), 2)
        return 999.0
    except Exception as e:
        print(f"[gateway error] {e}")
        return 999.0


def get_connected_devices(network=NETWORK):
    """Fast device count using ARP table (nmap is too slow for real-time)"""
    try:
        result = subprocess.run(
            ["arp", "-a"], capture_output=True, text=True, timeout=5
        )
        # Filter for actual dynamic entries
        lines = [l for l in result.stdout.split("\n")
                 if "dynamic" in l.lower() or ("-" in l and ":" in l)]
        return max(1, len(lines))
    except Exception as e:
        print(f"[device scan error] {e}")
        return 0



def get_all_metrics():
    """Returns all 8 features. Fetches from Pi if PI_HOST is set."""
    if PI_HOST:
        url = f"http://{PI_HOST}:{PI_PORT}/metrics"
        try:
            resp = requests.get(url, timeout=30)  # Increased timeout to 30s
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[Pi metrics error] {e} — falling back to local collection")


    latency, loss, jitter = get_latency_loss_jitter()
    download, upload = get_bandwidth()
    dns = get_dns_response()
    gateway = get_gateway_ping()
    devices = get_connected_devices()

    return {
        "latency_ms":        latency,
        "packet_loss_pct":   loss,
        "download_mbps":     download,
        "upload_mbps":       upload,
        "connected_devices": devices,
        "dns_response_ms":   dns,
        "gateway_ping_ms":   gateway,
        "jitter_ms":         jitter
    }