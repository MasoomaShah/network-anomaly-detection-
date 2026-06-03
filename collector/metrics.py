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

# ── Ensure nmap is discoverable on Windows ───────────────────────────────────
NMAP_DIR = r"C:\Program Files (x86)\Nmap"
if IS_WINDOWS and os.path.isdir(NMAP_DIR) and NMAP_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = NMAP_DIR + os.pathsep + os.environ.get("PATH", "")


def _ping_cmd(host: str, count: int = 4) -> list:
    """Return the correct ping command for the current OS."""
    if IS_WINDOWS:
        # -n count  -w timeout_ms
        return ["ping", "-n", str(count), "-w", "1000", host]
    else:
        # -c count  -W timeout_s  -i interval_s
        return ["ping", "-c", str(count), "-W", "2", "-i", "0.5", host]


def _parse_ping_output(output: str):
    """Parse ping stdout from both Windows and Linux into (times, loss_pct)."""
    times = []
    loss = 0.0

    for line in output.split("\n"):
        # Both platforms emit "time=X" (Windows: "time=Xms", Linux: "time=X ms")
        if "time=" in line or "time<" in line:
            try:
                raw = line.split("time=")[-1].split("ms")[0].strip()
                # Linux may have a trailing space before "ms"
                times.append(float(raw.strip()))
            except Exception:
                pass

        # Windows: "Lost = N (X% loss)"
        # Linux:   "X% packet loss"
        if "loss" in line.lower() or "Lost" in line:
            try:
                if "(" in line and "%" in line:
                    # Windows format
                    loss = float(line.split("(")[1].split("%")[0].strip())
                elif "%" in line:
                    # Linux format: "1 packets transmitted, 1 received, 0% packet loss"
                    for part in line.split(","):
                        if "%" in part:
                            loss = float(part.strip().split("%")[0].strip())
                            break
            except Exception:
                pass

    return times, loss


def get_latency_loss_jitter(host=PING_HOST, count=4):
    """Single ping batch — returns (latency_ms, packet_loss_pct, jitter_ms)."""
    try:
        result = subprocess.run(
            _ping_cmd(host, count),
            capture_output=True, text=True, timeout=15
        )
        times, loss = _parse_ping_output(result.stdout)

        if times:
            latency = round(sum(times) / len(times), 2)
            jitter  = round(float(np.std(times)), 2)
        else:
            latency = 0.0
            jitter  = 0.0

        return latency, loss, jitter

    except Exception as e:
        print(f"[ping error] {e}")
        return 999.0, 100.0, 999.0


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
        start = time.time()
        socket.gethostbyname(domain)
        return round((time.time() - start) * 1000, 2)
    except Exception as e:
        print(f"[dns error] {e}")
        return 9999.0
    finally:
        socket.setdefaulttimeout(old_timeout)


def get_gateway_ping(gateway=GATEWAY):
    """Pings the gateway/router and returns average RTT in ms."""
    try:
        result = subprocess.run(
            _ping_cmd(gateway, 4),
            capture_output=True, text=True, timeout=20
        )
        times, _ = _parse_ping_output(result.stdout)
        if times:
            return round(sum(times) / len(times), 2)
        return 999.0
    except Exception as e:
        print(f"[gateway error] {e}")
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
