import urllib.request
import urllib.error
import time
import sys

def main():
    # Targets for downloading chunks (Cloudflare and Cachefly as fallback)
    targets = [
        {"name": "Cloudflare Edge", "url": "https://speed.cloudflare.com/__down?bytes=10000000"},
        {"name": "Cachefly CDN", "url": "https://cachefly.cachefly.net/10mb.test"}
    ]
    headers = {"User-Agent": "Mozilla/5.0"}
    
    print("=" * 70)
    print("        Bandwidth Flood Simulator (Self-Healing)")
    print("=" * 70)
    print("Saturating connection by continuously downloading 10MB chunks...")
    print("Press Ctrl+C to stop the simulation.\n")
    
    start_time = time.time()
    total_bytes = 0
    chunk_index = 1
    target_index = 0
    
    try:
        while True:
            target = targets[target_index]
            url = target["url"]
            # Add unique parameter to URL to prevent aggressive caching
            url_sep = "&" if "?" in url else "?"
            req_url = f"{url}{url_sep}chunk={chunk_index}"
            
            try:
                req = urllib.request.Request(req_url, headers=headers)
                with urllib.request.urlopen(req) as response:
                    while True:
                        chunk = response.read(1024 * 1024) # Read in 1MB chunks
                        if not chunk:
                            break
                        total_bytes += len(chunk)
                        elapsed = time.time() - start_time
                        speed_mbps = (total_bytes * 8) / (elapsed * 1e6) if elapsed > 0 else 0
                        print(f"Downloaded: {total_bytes / (1024*1024):.1f} MB | Time elapsed: {elapsed:.1f}s | Current Speed: {speed_mbps:.2f} Mbps (using {target['name']})", end="\r")
                chunk_index += 1
                time.sleep(0.1)
            except urllib.error.HTTPError as he:
                if he.code in [429, 403]:
                    # Switch to fallback target
                    next_index = (target_index + 1) % len(targets)
                    print(f"\n[HTTP {he.code}] Rate limit/block detected on {target['name']}. Switching to {targets[next_index]['name']}...")
                    target_index = next_index
                    time.sleep(0.5)
                else:
                    raise he
    except KeyboardInterrupt:
        print("\n\nStopped by user. Active bandwidth saturation stopped.")
    except Exception as e:
        print(f"\n\nError: {e}")

if __name__ == "__main__":
    main()
