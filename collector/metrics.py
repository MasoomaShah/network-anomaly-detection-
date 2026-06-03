"""
metrics.py — Network Metric Collector
======================================
Uses TCP socket probes instead of ICMP ping so it works in restricted
Docker environments (HF Spaces, containers without CAP_NET_RAW).
Falls back to subprocess ping on Windows where TCP probing may differ.
"""

import subprocess
import socket
import time
import os
import platform
import psutil
import numpy as np

GATEWAY         = os.getenv("GATEWAY",         "192.168.1.1")
NETWORK         = os.getenv("NETWORK",         "192.168.1.0/24")
PING_HOST       = os.getenv("PING_HOST",       "8.8.8.8")
DNS_TEST_DOMAIN = os.getenv("DNS_TEST_DOMAIN", "google.com")

IS_WINDOWS = platform.system() == "Windows"

# Ports to try for TCP RTT probe — first reachable one wins
_PROBE_PORTS = [53, 443, 80, 8080]

# ── Ensure nmap is discoverable on Windows ────────────────────────────────────
NMAP_DIR = r"C:\Program Files (x86)\Nmap"
if IS_WINDOWS and os.path.isdir(NMAP_DIR) and NMAP_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = NMAP_DIR + os.pathsep + os.environ.get("PATH", "")


# ── TCP RTT probe (no root required) ─────────────────────────────────────────

def _tcp_rtt(host: str, timeout: float = 2.0) -> float | None:
    """
    Measure round-trip time to *host* via TCP connect on common ports.
    Returns RTT in ms, or None if all ports are unreachable.
    Connection-refused (errno 111/10061) still counts — host is alive.
    """
    for port in _PROBE_PORTS:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            t0 = time.time()
            err = sock.connect_ex((host, port))
            rtt = (time.time() - t0) * 1000
            sock.close()
            # 0 = connected, 111 = refused (Linux), 10061 = refused (Windows)
            if err in (0, 111, 10061):
                return round(rtt, 2)
        except Exception:
            continue
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def get_latency_loss_jitter(host=PING_HOST, count=8):
    """
    Estimate latency, packet loss, and jitter via repeated TCP probes.
    Works in Docker without CAP_NET_RAW (no ICMP needed).
    """
    rtts = []
    failed = 0

    for _ in range(count):
        rtt = _tcp_rtt(host)
        if rtt is not None:
            rtts.append(rtt)
        else:
            failed += 1

    if rtts:
        latency = round(float(np.mean(rtts)), 2)
        jitter  = round(float(np.std(rtts)), 2)
    else:
        latency = 999.0
        jitter  = 999.0

    loss = round((failed / count) * 100, 1)
    return latency, loss, jitter


def get_bandwidth():
    """Measures actual bandwidth using psutil over a 1-second window."""
    try:
        net1 = psutil.net_io_counters()
        time.sleep(1)
        net2 = psutil.net_io_counters()
        download = round((net2.bytes_recv - net1.bytes_recv) / 1e6 * 8, 3)
        upload   = round((net2.bytes_sent - net1.bytes_sent) / 1e6 * 8, 3)
        return download, upload
    except Exception as e:
        print(f"[bandwidth error] {e}")
        return 0.0, 0.0


def get_dns_response(domain=DNS_TEST_DOMAIN):
    """Measures DNS resolution time in milliseconds."""
    old_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(3)
        t0 = time.time()
        socket.gethostbyname(domain)
        return round((time.time() - t0) * 1000, 2)
    except Exception as e:
        print(f"[dns error] {e}")
        return 9999.0
    finally:
        socket.setdefaulttimeout(old_timeout)


def get_gateway_ping(gateway=GATEWAY):
    """
    Probe gateway reachability via TCP.
    Returns RTT in ms, or 999.0 if unreachable.
    """
    rtt = _tcp_rtt(gateway, timeout=3.0)
    if rtt is not None:
        return rtt
    print(f"[gateway] {gateway} unreachable on all probe ports")
    return 999.0


def get_connected_devices(network=NETWORK):
    """Counts devices on the local network using nmap."""
    try:
        import nmap
        nmap_path = (
            os.path.join(NMAP_DIR, "nmap.exe")
            if IS_WINDOWS and os.path.isfile(os.path.join(NMAP_DIR, "nmap.exe"))
            else None
        )
        nm = nmap.PortScanner(nmap_search_path=(nmap_path,)) if nmap_path else nmap.PortScanner()
        nm.scan(hosts=network, arguments="-sn")
        return len(nm.all_hosts())
    except Exception as e:
        print(f"[nmap error] {e}")
        try:
            result = subprocess.run(["arp", "-a"], capture_output=True, text=True)
            lines = [l for l in result.stdout.split("\n")
                     if "dynamic" in l.lower() or "---" not in l]
            return max(1, len(lines) - 2)
        except Exception:
            return 0


def get_all_metrics():
    """Returns all 8 features needed for the LSTM Autoencoder."""
    latency, loss, jitter = get_latency_loss_jitter()
    download, upload      = get_bandwidth()
    dns                   = get_dns_response()
    gateway               = get_gateway_ping()
    devices               = get_connected_devices()

    return {
        "latency_ms":        latency,
        "packet_loss_pct":   loss,
        "download_mbps":     download,
        "upload_mbps":       upload,
        "connected_devices": devices,
        "dns_response_ms":   dns,
        "gateway_ping_ms":   gateway,
        "jitter_ms":         jitter,
    }
