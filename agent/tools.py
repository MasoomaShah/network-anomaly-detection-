"""
tools.py — 10 Network Diagnostic Tools for the Agent
=====================================================
Each tool takes a single string input, returns a human-readable string.
Auto-detects Windows vs Linux and adjusts commands accordingly.
Destructive actions (restart, block, switch_dns) run in dry-run mode on Windows.
"""

import os
import sys
import json
import time
import socket
import subprocess
import platform

# Ensure we can import metrics.py from collector/
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_COLLECTOR = os.path.join(_BASE, "collector")
if _COLLECTOR not in sys.path:
    sys.path.insert(0, _COLLECTOR)

from agent.config import IS_WINDOWS, IS_LINUX, GATEWAY, NETWORK, KNOWN_DEVICES_PATH

# ─────────────────────────────────────────────────────────────────────────
# 1. PING TEST
# ─────────────────────────────────────────────────────────────────────────
def run_ping_test(input_str: str) -> str:
    """Ping a host and report latency + packet loss.
    Input: 'host' or 'host,count'. Example: '8.8.8.8' or '8.8.8.8,20'"""
    try:
        parts = [p.strip() for p in input_str.split(",")]
        host = parts[0] if parts[0] else "8.8.8.8"
        count = int(parts[1]) if len(parts) > 1 else 10

        flag = "-n" if IS_WINDOWS else "-c"
        result = subprocess.run(
            ["ping", flag, str(count), host],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout

        times = []
        for line in output.split("\n"):
            if "time=" in line or "time<" in line:
                try:
                    t = line.split("time=")[-1].split("ms")[0].strip()
                    times.append(float(t))
                except ValueError:
                    pass

        loss_pct = 0.0
        for line in output.split("\n"):
            if "loss" in line.lower() or "Lost" in line:
                try:
                    loss_pct = float(line.split("(")[1].split("%")[0].strip())
                except (IndexError, ValueError):
                    pass

        received = len(times)
        lost = count - received
        avg_latency = round(sum(times) / len(times), 1) if times else 0

        return (
            f"Ping results for {host} ({count} packets):\n"
            f"  Received: {received}/{count}\n"
            f"  Lost: {lost}/{count} ({loss_pct}% loss)\n"
            f"  Avg latency: {avg_latency} ms\n"
            f"  Min: {min(times):.1f} ms | Max: {max(times):.1f} ms"
            if times else
            f"Ping to {host}: ALL {count} PACKETS LOST — host unreachable"
        )
    except subprocess.TimeoutExpired:
        return f"Ping to {input_str}: TIMED OUT after 30 seconds"
    except Exception as e:
        return f"Ping error: {e}"


# ─────────────────────────────────────────────────────────────────────────
# 2. TRACEROUTE
# ─────────────────────────────────────────────────────────────────────────
def run_traceroute(host: str) -> str:
    """Trace the packet route to a host hop by hop.
    Input: host IP or domain. Example: '8.8.8.8'"""
    host = host.strip() or "8.8.8.8"
    try:
        if IS_WINDOWS:
            cmd = ["tracert", "-d", "-h", "15", host]
        else:
            cmd = ["traceroute", "-n", "-m", "15", host]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        lines = result.stdout.strip().split("\n")
        # Limit output to keep it concise for the LLM
        if len(lines) > 20:
            lines = lines[:20] + [f"... ({len(lines)-20} more hops)"]
        return f"Traceroute to {host}:\n" + "\n".join(lines)
    except subprocess.TimeoutExpired:
        return f"Traceroute to {host}: TIMED OUT after 60 seconds"
    except Exception as e:
        return f"Traceroute error: {e}"


# ─────────────────────────────────────────────────────────────────────────
# 3. SPEED TEST (quick bandwidth measurement via psutil)
# ─────────────────────────────────────────────────────────────────────────
def run_speedtest(_: str = "") -> str:
    """Measure current network bandwidth (download/upload) over 2 seconds.
    Input: ignored — just pass empty string."""
    try:
        import psutil
        net1 = psutil.net_io_counters()
        time.sleep(2)
        net2 = psutil.net_io_counters()

        dl = round((net2.bytes_recv - net1.bytes_recv) / 1e6 * 8 / 2, 2)
        ul = round((net2.bytes_sent - net1.bytes_sent) / 1e6 * 8 / 2, 2)
        total_recv = round(net2.bytes_recv / 1e9, 2)
        total_sent = round(net2.bytes_sent / 1e9, 2)

        return (
            f"Bandwidth measurement (2-second sample):\n"
            f"  Download: {dl} Mbps\n"
            f"  Upload:   {ul} Mbps\n"
            f"  Total received this session: {total_recv} GB\n"
            f"  Total sent this session:     {total_sent} GB"
        )
    except Exception as e:
        return f"Speedtest error: {e}"


# ─────────────────────────────────────────────────────────────────────────
# 4. SCAN DEVICES
# ─────────────────────────────────────────────────────────────────────────
def scan_devices(_: str = "") -> str:
    """Scan the local network and list all connected devices with MAC addresses.
    Input: ignored — just pass empty string."""
    devices = []

    # Try ARP table (works on both Windows and Linux)
    try:
        result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=15)
        for line in result.stdout.split("\n"):
            line = line.strip()
            if not line or "Interface" in line or "Internet" in line:
                continue
            parts = line.split()
            if len(parts) >= 3:
                ip = parts[0]
                mac = parts[1] if not IS_WINDOWS else parts[1]
                # On Windows: IP is col 0, MAC is col 1, type is col 2
                if any(c in mac for c in [":", "-"]) and mac.lower() != "ff-ff-ff-ff-ff-ff":
                    devices.append({"ip": ip, "mac": mac.lower()})
    except Exception:
        pass

    # Load known devices for comparison
    known_macs = set()
    try:
        with open(KNOWN_DEVICES_PATH, "r") as f:
            known = json.load(f)
            known_macs = {d["mac"].lower().replace(":", "-") for d in known.get("trusted", [])}
    except Exception:
        pass

    if not devices:
        return "Device scan: No devices found via ARP table."

    lines = [f"Network scan — {len(devices)} devices found:\n"]
    for d in devices:
        mac_normalized = d["mac"].replace(":", "-").lower()
        status = "✓ KNOWN" if mac_normalized in known_macs else "⚠ UNKNOWN"
        lines.append(f"  {d['ip']:<16}  {d['mac']:<20}  {status}")

    unknown_count = sum(1 for d in devices
                        if d["mac"].replace(":", "-").lower() not in known_macs)
    if unknown_count:
        lines.append(f"\n  ⚠ {unknown_count} unknown device(s) detected!")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────
# 5. CHECK DNS
# ─────────────────────────────────────────────────────────────────────────
def check_dns(domain: str) -> str:
    """Test DNS resolution for a domain and measure response time.
    Input: domain name. Example: 'google.com'"""
    domain = domain.strip() or "google.com"
    results = []

    for test_domain in [domain, "cloudflare.com", "github.com"]:
        try:
            start = time.time()
            ip = socket.gethostbyname(test_domain)
            elapsed = round((time.time() - start) * 1000, 1)
            results.append(f"  {test_domain:<20} → {ip:<16}  ({elapsed} ms)")
        except socket.gaierror:
            results.append(f"  {test_domain:<20} → FAILED (DNS resolution error)")
        except Exception as e:
            results.append(f"  {test_domain:<20} → ERROR: {e}")

    return "DNS resolution test:\n" + "\n".join(results)


# ─────────────────────────────────────────────────────────────────────────
# 6. RESTART NETWORK INTERFACE
# ─────────────────────────────────────────────────────────────────────────
def restart_interface(_: str = "") -> str:
    """Restart the primary network interface to fix connectivity issues.
    Input: ignored. Requires admin privileges on Linux. DRY-RUN on Windows."""
    if IS_WINDOWS:
        return (
            "[DRY RUN — Windows] Would restart network interface.\n"
            "  On Raspberry Pi, this runs:\n"
            "    sudo ip link set wlan0 down && sleep 2 && sudo ip link set wlan0 up\n"
            "  Simulating: interface restart successful."
        )

    # Linux / RPi
    try:
        iface = "wlan0"  # default RPi wireless interface
        subprocess.run(["sudo", "ip", "link", "set", iface, "down"],
                       check=True, timeout=10)
        time.sleep(2)
        subprocess.run(["sudo", "ip", "link", "set", iface, "up"],
                       check=True, timeout=10)
        time.sleep(3)  # wait for reconnect
        return f"Network interface '{iface}' restarted successfully. Waiting for reconnect..."
    except subprocess.CalledProcessError as e:
        return f"Failed to restart interface: {e} (need sudo privileges?)"
    except Exception as e:
        return f"Interface restart error: {e}"


# ─────────────────────────────────────────────────────────────────────────
# 7. BLOCK DEVICE BY MAC
# ─────────────────────────────────────────────────────────────────────────
def block_mac(mac: str) -> str:
    """Block a device on the network by its MAC address using iptables.
    Input: MAC address. Example: 'aa:bb:cc:dd:ee:ff'. DRY-RUN on Windows."""
    mac = mac.strip()
    if not mac:
        return "Error: no MAC address provided. Usage: block_device('aa:bb:cc:dd:ee:ff')"

    if IS_WINDOWS:
        return (
            f"[DRY RUN — Windows] Would block MAC: {mac}\n"
            f"  On Raspberry Pi, this runs:\n"
            f"    sudo iptables -A INPUT -m mac --mac-source {mac} -j DROP\n"
            f"  Simulating: device {mac} blocked successfully."
        )

    try:
        subprocess.run(
            ["sudo", "iptables", "-A", "INPUT", "-m", "mac",
             "--mac-source", mac, "-j", "DROP"],
            check=True, timeout=10
        )
        return f"Device {mac} has been BLOCKED via iptables. It can no longer communicate on this network."
    except Exception as e:
        return f"Failed to block {mac}: {e}"


# ─────────────────────────────────────────────────────────────────────────
# 8. SWITCH DNS SERVER
# ─────────────────────────────────────────────────────────────────────────
def switch_dns(dns_server: str) -> str:
    """Switch the system DNS server to a specified address.
    Input: DNS server IP. Example: '8.8.8.8'. DRY-RUN on Windows."""
    dns_server = dns_server.strip() or "8.8.8.8"

    if IS_WINDOWS:
        return (
            f"[DRY RUN — Windows] Would switch DNS to: {dns_server}\n"
            f"  On Raspberry Pi, this runs:\n"
            f"    echo 'nameserver {dns_server}' | sudo tee /etc/resolv.conf\n"
            f"  Simulating: DNS switched to {dns_server} successfully."
        )

    try:
        subprocess.run(
            ["sudo", "bash", "-c",
             f"echo 'nameserver {dns_server}' > /etc/resolv.conf"],
            check=True, timeout=10
        )
        # Verify
        check = check_dns("google.com")
        return f"DNS switched to {dns_server}.\nVerification:\n{check}"
    except Exception as e:
        return f"Failed to switch DNS: {e}"


# ─────────────────────────────────────────────────────────────────────────
# 9. READ NETWORK LOGS
# ─────────────────────────────────────────────────────────────────────────
def read_network_logs(_: str = "") -> str:
    """Read recent network-related system logs for context.
    Input: ignored — just pass empty string."""
    try:
        if IS_WINDOWS:
            # Read recent network events from Windows Event Log
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-EventLog -LogName System -Newest 20 "
                 "-Source 'Microsoft-Windows-*' "
                 "| Select-Object TimeGenerated,Source,Message "
                 "| Format-Table -Wrap -AutoSize"],
                capture_output=True, text=True, timeout=15
            )
            logs = result.stdout.strip()
            if not logs:
                logs = "No recent network events found in Windows Event Log."
        else:
            # Linux: read syslog
            result = subprocess.run(
                ["tail", "-n", "30", "/var/log/syslog"],
                capture_output=True, text=True, timeout=10
            )
            logs = result.stdout.strip()
            if not logs:
                logs = "No recent entries in /var/log/syslog."

        # Truncate if too long for LLM context
        if len(logs) > 2000:
            logs = logs[:2000] + "\n... (truncated)"

        return f"System network logs (recent):\n{logs}"
    except Exception as e:
        return f"Log reading error: {e}"


# ─────────────────────────────────────────────────────────────────────────
# 10. GET CURRENT METRICS
# ─────────────────────────────────────────────────────────────────────────
def get_current_metrics(_: str = "") -> str:
    """Get a fresh snapshot of all 8 network metrics right now.
    Input: ignored — just pass empty string."""
    try:
        from metrics import get_all_metrics
        m = get_all_metrics()
        return (
            f"Current network metrics (live):\n"
            f"  Latency:           {m['latency_ms']:.1f} ms\n"
            f"  Packet Loss:       {m['packet_loss_pct']:.1f}%\n"
            f"  Download:          {m['download_mbps']:.2f} Mbps\n"
            f"  Upload:            {m['upload_mbps']:.2f} Mbps\n"
            f"  Connected Devices: {m['connected_devices']}\n"
            f"  DNS Response:      {m['dns_response_ms']:.1f} ms\n"
            f"  Gateway Ping:      {m['gateway_ping_ms']:.1f} ms\n"
            f"  Jitter:            {m['jitter_ms']:.1f} ms"
        )
    except Exception as e:
        return f"Metric collection error: {e}"


# ─────────────────────────────────────────────────────────────────────────
# TOOL REGISTRY — used by agent.py
# ─────────────────────────────────────────────────────────────────────────
TOOL_DEFINITIONS = [
    {
        "name": "ping_test",
        "func": run_ping_test,
        "description": (
            "Ping a host to measure latency and packet loss. "
            "Input: 'host' or 'host,count'. Example: '8.8.8.8' or '8.8.8.8,20'"
        ),
    },
    {
        "name": "traceroute",
        "func": run_traceroute,
        "description": (
            "Trace the packet route to a host hop by hop. "
            "Input: host IP or domain. Example: '8.8.8.8'"
        ),
    },
    {
        "name": "speedtest",
        "func": run_speedtest,
        "description": (
            "Measure current download/upload bandwidth. "
            "Input: not needed, pass empty string."
        ),
    },
    {
        "name": "scan_devices",
        "func": scan_devices,
        "description": (
            "List all devices connected to the local network with MAC addresses. "
            "Flags unknown devices not in the trusted list. "
            "Input: not needed, pass empty string."
        ),
    },
    {
        "name": "check_dns",
        "func": check_dns,
        "description": (
            "Test DNS resolution for a domain. "
            "Input: domain name. Example: 'google.com'"
        ),
    },
    {
        "name": "restart_interface",
        "func": restart_interface,
        "description": (
            "Restart the network interface to fix connectivity issues. "
            "Use as last resort when gateway is unreachable. "
            "Input: not needed, pass empty string."
        ),
    },
    {
        "name": "block_device",
        "func": block_mac,
        "description": (
            "Block a suspicious device by its MAC address. "
            "Input: MAC address. Example: 'aa:bb:cc:dd:ee:ff'"
        ),
    },
    {
        "name": "switch_dns",
        "func": switch_dns,
        "description": (
            "Switch DNS server when DNS resolution is failing. "
            "Input: DNS server IP. Example: '8.8.8.8'"
        ),
    },
    {
        "name": "read_logs",
        "func": read_network_logs,
        "description": (
            "Read recent system network logs for additional context. "
            "Input: not needed, pass empty string."
        ),
    },
    {
        "name": "get_metrics",
        "func": get_current_metrics,
        "description": (
            "Get a fresh snapshot of all 8 network metrics right now. "
            "Useful to verify if a fix worked. "
            "Input: not needed, pass empty string."
        ),
    },
]
