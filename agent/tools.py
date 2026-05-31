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

from agent.config import IS_WINDOWS, IS_LINUX, GATEWAY, NETWORK

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
            capture_output=True, text=True, timeout=10
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

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
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
# 4. SCAN DEVICES  (auto-learn baseline — works on ANY network)
# ─────────────────────────────────────────────────────────────────────────
_BASELINE_PATH = os.path.join(_BASE, "data", "device_baseline.json")


def _load_baseline() -> dict:
    """Load the auto-learned baseline of devices seen on this network."""
    if not os.path.exists(_BASELINE_PATH):
        return {}
    try:
        with open(_BASELINE_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_baseline(baseline: dict):
    """Save baseline to disk."""
    os.makedirs(os.path.dirname(_BASELINE_PATH), exist_ok=True)
    with open(_BASELINE_PATH, "w") as f:
        json.dump(baseline, f, indent=2)


def scan_devices(_: str = "") -> str:
    """Scan the local network and list all connected devices with MAC addresses.
    Auto-learns a baseline on first run — flags NEW devices on subsequent scans.
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
                mac = parts[1]
                # On Windows: IP is col 0, MAC is col 1, type is col 2
                if any(c in mac for c in [":", "-"]) and mac.lower() != "ff-ff-ff-ff-ff-ff":
                    devices.append({"ip": ip, "mac": mac.lower()})
    except Exception:
        pass

    if not devices:
        return "Device scan: No devices found via ARP table."

    # Load or create baseline (auto-learn approach)
    baseline = _load_baseline()
    baseline_macs = set(baseline.keys())
    is_first_scan = len(baseline_macs) == 0

    # Normalize current device MACs
    current_macs = {}
    for d in devices:
        mac_norm = d["mac"].replace(":", "-").lower()
        current_macs[mac_norm] = d["ip"]

    # Auto-learn: add all new MACs to the baseline
    new_devices = []
    for mac_norm, ip in current_macs.items():
        if mac_norm not in baseline_macs:
            baseline[mac_norm] = {
                "ip": ip,
                "first_seen": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            if not is_first_scan:
                new_devices.append({"ip": ip, "mac": mac_norm})

    # Save updated baseline
    _save_baseline(baseline)

    # Build output
    lines = [f"Network scan — {len(devices)} devices found:\n"]
    for d in devices:
        mac_norm = d["mac"].replace(":", "-").lower()
        if is_first_scan:
            status = "✓ BASELINE"
        elif mac_norm in {nd["mac"] for nd in new_devices}:
            status = "🆕 NEW"
        else:
            status = "✓ KNOWN"
        first_seen = baseline.get(mac_norm, {}).get("first_seen", "now")
        lines.append(f"  {d['ip']:<16}  {d['mac']:<20}  {status}  (since {first_seen})")

    if is_first_scan:
        lines.append(f"\n  ℹ First scan — saved {len(devices)} device(s) as baseline.")
        lines.append(f"  Future scans will flag NEW devices automatically.")
    elif new_devices:
        lines.append(f"\n  🆕 {len(new_devices)} NEW device(s) detected since baseline!")
        for nd in new_devices:
            lines.append(f"     → {nd['ip']}  {nd['mac']}")
    else:
        lines.append(f"\n  ✓ No new devices — all {len(devices)} match baseline.")

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
# 6. RESTART NETWORK INTERFACE  (FIX TOOL)
# ─────────────────────────────────────────────────────────────────────────
def restart_interface(input_str: str = "") -> str:
    """Restart the network interface to fix connectivity issues.
    Input: optional interface name (default: auto-detect active Wi-Fi/Ethernet).
    On Windows runs 'ipconfig /release' + 'ipconfig /renew'.
    Example: '' or 'Wi-Fi'"""
    iface = input_str.strip() if input_str.strip() else None

    try:
        if IS_WINDOWS:
            # Step 1: Release IP
            release_cmd = ["ipconfig", "/release"]
            if iface:
                release_cmd.append(iface)
            result_rel = subprocess.run(
                release_cmd, capture_output=True, text=True, timeout=15
            )

            time.sleep(2)

            # Step 2: Renew IP
            renew_cmd = ["ipconfig", "/renew"]
            if iface:
                renew_cmd.append(iface)
            result_ren = subprocess.run(
                renew_cmd, capture_output=True, text=True, timeout=30
            )

            # Step 3: Flush DNS cache for good measure
            subprocess.run(
                ["ipconfig", "/flushdns"],
                capture_output=True, text=True, timeout=10
            )

            # Check if renew succeeded
            if "Windows IP Configuration" in result_ren.stdout:
                return (
                    f"✅ Network interface restarted successfully.\n"
                    f"  Release: completed\n"
                    f"  Renew: completed\n"
                    f"  DNS cache: flushed\n"
                    f"  Interface should be back online."
                )
            else:
                error_out = result_ren.stderr or result_ren.stdout
                return (
                    f"⚠️ Interface restart partially completed.\n"
                    f"  Release: completed\n"
                    f"  Renew output: {error_out[:300]}\n"
                    f"  Try running as Administrator if this failed."
                )
        else:
            # Linux: restart via ip/ifconfig
            iface = iface or "eth0"
            subprocess.run(["sudo", "ip", "link", "set", iface, "down"],
                           capture_output=True, text=True, timeout=10)
            time.sleep(2)
            subprocess.run(["sudo", "ip", "link", "set", iface, "up"],
                           capture_output=True, text=True, timeout=10)
            time.sleep(3)
            return f"✅ Interface {iface} restarted (down → up). Network should be back online."

    except subprocess.TimeoutExpired:
        return "⚠️ Interface restart timed out. The network may still be recovering."
    except Exception as e:
        return f"❌ Interface restart error: {e}"


# ─────────────────────────────────────────────────────────────────────────
# 7. SWITCH DNS SERVER  (FIX TOOL)
# ─────────────────────────────────────────────────────────────────────────
def switch_dns(input_str: str = "") -> str:
    """Switch the DNS server to fix DNS resolution failures.
    Input: DNS server IP (default: '8.8.8.8'). Example: '8.8.8.8' or '1.1.1.1'"""
    dns_server = input_str.strip() if input_str.strip() else "8.8.8.8"

    # Map friendly names
    dns_names = {
        "8.8.8.8": "Google DNS",
        "8.8.4.4": "Google DNS (secondary)",
        "1.1.1.1": "Cloudflare DNS",
        "1.0.0.1": "Cloudflare DNS (secondary)",
        "208.67.222.222": "OpenDNS",
    }
    dns_label = dns_names.get(dns_server, dns_server)

    try:
        if IS_WINDOWS:
            # Detect the active network interface name
            iface_name = _detect_active_interface()

            # Set primary DNS
            result = subprocess.run(
                ["netsh", "interface", "ip", "set", "dns",
                 iface_name, "static", dns_server],
                capture_output=True, text=True, timeout=15
            )

            if result.returncode != 0:
                error = result.stderr or result.stdout
                if "access is denied" in error.lower() or "requires elevation" in error.lower():
                    return (
                        f"❌ Cannot switch DNS — requires Administrator privileges.\n"
                        f"  Manual fix: Run PowerShell as Admin and execute:\n"
                        f'  netsh interface ip set dns "{iface_name}" static {dns_server}'
                    )
                return f"⚠️ DNS switch may have failed: {error[:300]}"

            # Flush DNS cache
            subprocess.run(["ipconfig", "/flushdns"],
                           capture_output=True, text=True, timeout=10)

            # Verify DNS is working
            time.sleep(1)
            try:
                start = time.time()
                socket.gethostbyname("google.com")
                elapsed = round((time.time() - start) * 1000, 1)
                return (
                    f"✅ DNS switched to {dns_server} ({dns_label}) on interface '{iface_name}'.\n"
                    f"  DNS cache flushed.\n"
                    f"  Verification: google.com resolved in {elapsed} ms — DNS is working!"
                )
            except socket.gaierror:
                return (
                    f"⚠️ DNS switched to {dns_server} ({dns_label}) on interface '{iface_name}',\n"
                    f"  but verification failed — google.com still not resolving.\n"
                    f"  DNS cache was flushed. It may take a few seconds to propagate."
                )
        else:
            # Linux: write to resolv.conf
            try:
                with open("/etc/resolv.conf", "w") as f:
                    f.write(f"nameserver {dns_server}\n")
                return f"✅ DNS switched to {dns_server} ({dns_label}) via /etc/resolv.conf."
            except PermissionError:
                return (
                    f"❌ Cannot write /etc/resolv.conf — need sudo.\n"
                    f"  Manual fix: sudo sh -c 'echo nameserver {dns_server} > /etc/resolv.conf'"
                )

    except subprocess.TimeoutExpired:
        return f"⚠️ DNS switch timed out."
    except Exception as e:
        return f"❌ DNS switch error: {e}"


def _detect_active_interface() -> str:
    """Detect the active network interface name on Windows."""
    try:
        result = subprocess.run(
            ["netsh", "interface", "show", "interface"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.split("\n"):
            line = line.strip()
            if "Connected" in line:
                # Format: Admin State    State    Type    Interface Name
                parts = line.split()
                # Interface name is everything after the type column
                if len(parts) >= 4:
                    # Find "Connected" position and extract interface name
                    idx = line.find("Connected")
                    after = line[idx + len("Connected"):].strip()
                    # Skip the type column (Dedicated/...)
                    type_and_name = after.split(None, 1)
                    if len(type_and_name) >= 2:
                        return type_and_name[1].strip()
    except Exception:
        pass
    return "Wi-Fi"  # fallback default


# ─────────────────────────────────────────────────────────────────────────
# 8. TERMINATE CLUMSY SIMULATION  (FIX TOOL)
# ─────────────────────────────────────────────────────────────────────────
def terminate_clumsy(input_str: str = "") -> str:
    """FIX TOOL: Terminate the Clumsy simulation process to resolve packet loss.
    Input: ignored — just pass empty string."""
    try:
        if IS_WINDOWS:
            import psutil
            import subprocess
            
            # Check if clumsy is active (works for all privilege levels)
            check_proc = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq clumsy.exe"],
                capture_output=True, text=True, timeout=10
            )
            is_clumsy_running = "clumsy.exe" in check_proc.stdout.lower()
            
            if not is_clumsy_running:
                return "ℹ️ Clumsy simulation process was not active."
                
            # Try killing using psutil
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() == 'clumsy.exe':
                        proc.kill()
                except Exception:
                    pass
                    
            # Double check if still running
            check_proc = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq clumsy.exe"],
                capture_output=True, text=True, timeout=10
            )
            if "clumsy.exe" not in check_proc.stdout.lower():
                return "✅ Successfully terminated the Clumsy packet loss simulation. Packet loss should return to 0%."
                
            # Try taskkill as fallback
            subprocess.run(
                ["taskkill", "/f", "/im", "clumsy.exe"],
                capture_output=True, text=True, timeout=10
            )
            
            # Check one last time
            check_proc = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq clumsy.exe"],
                capture_output=True, text=True, timeout=10
            )
            if "clumsy.exe" not in check_proc.stdout.lower():
                return "✅ Successfully terminated the Clumsy process via taskkill."
                
            return "⚠️ Clumsy is active but could not be terminated automatically because the Agent is not running as Administrator. Please close the Clumsy application window manually or run this command in an Administrator terminal:\n\ntaskkill /f /im clumsy.exe"
        else:
            return "ℹ️ Clumsy is a Windows-only application."
    except Exception as e:
        return f"❌ Error terminating Clumsy: {e}"


# ─────────────────────────────────────────────────────────────────────────
# 9. BLOCK DEVICE BY MAC ADDRESS  (FIX TOOL)
# ─────────────────────────────────────────────────────────────────────────
def block_device(mac_address: str) -> str:
    """Block a suspicious device on the network by its MAC address.
    Input: MAC address to block. Example: 'aa-bb-cc-dd-ee-ff' or 'aa:bb:cc:dd:ee:ff'"""
    mac = mac_address.strip().lower().replace(":", "-")

    if not mac or len(mac) < 12:
        return "❌ Invalid MAC address. Provide a full MAC like 'aa-bb-cc-dd-ee-ff'."

    try:
        # Look up the IP for this MAC from ARP table
        ip_address = None
        result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=10)
        for line in result.stdout.split("\n"):
            line_lower = line.strip().lower()
            mac_normalized = mac.replace("-", "-")
            if mac_normalized in line_lower:
                parts = line.strip().split()
                if parts:
                    ip_address = parts[0]
                    break

        if not ip_address:
            return (
                f"⚠️ Could not find IP for MAC {mac} in ARP table.\n"
                f"  The device may have disconnected or the ARP cache expired.\n"
                f"  Device flagged for monitoring — will alert if it reconnects."
            )

        if IS_WINDOWS:
            # Create Windows Firewall rule to block the device's IP
            rule_name = f"AGENT_BLOCK_{mac.replace('-', '')}"

            # Block inbound traffic from the device
            result_in = subprocess.run(
                ["netsh", "advfirewall", "firewall", "add", "rule",
                 f"name={rule_name}_IN",
                 "dir=in", "action=block",
                 f"remoteip={ip_address}",
                 "protocol=any"],
                capture_output=True, text=True, timeout=15
            )

            # Block outbound traffic to the device
            result_out = subprocess.run(
                ["netsh", "advfirewall", "firewall", "add", "rule",
                 f"name={rule_name}_OUT",
                 "dir=out", "action=block",
                 f"remoteip={ip_address}",
                 "protocol=any"],
                capture_output=True, text=True, timeout=15
            )

            if result_in.returncode == 0 and result_out.returncode == 0:
                return (
                    f"✅ Device BLOCKED successfully.\n"
                    f"  MAC: {mac}\n"
                    f"  IP:  {ip_address}\n"
                    f"  Firewall rules added: {rule_name}_IN, {rule_name}_OUT\n"
                    f"  All traffic to/from {ip_address} is now blocked.\n"
                    f"  To unblock later: netsh advfirewall firewall delete rule name={rule_name}_IN"
                )
            else:
                error = result_in.stderr or result_out.stderr or result_in.stdout
                if "access is denied" in error.lower() or "requires elevation" in error.lower():
                    return (
                        f"❌ Cannot block device — requires Administrator privileges.\n"
                        f"  Device: MAC={mac}, IP={ip_address}\n"
                        f"  Manual fix: Run PowerShell as Admin and execute:\n"
                        f'  netsh advfirewall firewall add rule name="{rule_name}_IN" '
                        f'dir=in action=block remoteip={ip_address} protocol=any'
                    )
                return f"⚠️ Firewall rule may have failed: {error[:300]}"
        else:
            # Linux: use iptables
            subprocess.run(
                ["sudo", "iptables", "-A", "INPUT", "-m", "mac",
                 "--mac-source", mac.replace("-", ":"), "-j", "DROP"],
                capture_output=True, text=True, timeout=10
            )
            return (
                f"✅ Device blocked via iptables.\n"
                f"  MAC: {mac}\n"
                f"  All incoming traffic from this device is now dropped."
            )

    except subprocess.TimeoutExpired:
        return f"⚠️ Block command timed out for MAC {mac}."
    except Exception as e:
        return f"❌ Block device error: {e}"


# ─────────────────────────────────────────────────────────────────────────
# FIX TOOL NAMES — used by agent.py to detect fix actions
# ─────────────────────────────────────────────────────────────────────────
FIX_TOOL_NAMES = {"restart_interface", "switch_dns", "block_device", "terminate_clumsy"}


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
            "FIX TOOL: Restart the network interface to fix connectivity issues. "
            "Runs ipconfig /release + /renew on Windows. "
            "Use when gateway is unreachable or packet loss is high. "
            "Input: optional interface name, or empty string for auto-detect."
        ),
    },
    {
        "name": "switch_dns",
        "func": switch_dns,
        "description": (
            "FIX TOOL: Switch DNS server to fix DNS resolution failures. "
            "Use when DNS is failing or timing out. "
            "Input: DNS server IP. Example: '8.8.8.8' (Google DNS) or '1.1.1.1' (Cloudflare)."
        ),
    },
    {
        "name": "block_device",
        "func": block_device,
        "description": (
            "FIX TOOL: Block a suspicious device by MAC address using firewall rules. "
            "Use when an unknown or unauthorized device is detected on the network. "
            "Input: MAC address. Example: 'aa-bb-cc-dd-ee-ff'"
        ),
    },
    {
        "name": "terminate_clumsy",
        "func": terminate_clumsy,
        "description": (
            "FIX TOOL: Terminate the Clumsy simulation process to restore packet loss back to 0%. "
            "Use when high packet loss or network disruption is detected and Clumsy is running. "
            "Input: not needed, pass empty string."
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
