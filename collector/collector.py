import time
import csv
import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metrics import get_all_metrics

CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'network_metrics.csv')
INTERVAL = 5  # seconds

HEADERS = ['timestamp', 'latency_ms', 'packet_loss_pct',
           'download_mbps', 'upload_mbps', 'connected_devices',
           'dns_response_ms', 'gateway_ping_ms', 'jitter_ms']

def main():
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    file_exists = os.path.isfile(CSV_PATH)

    print("=" * 50)
    print("   Network Metric Collector — 8 Features")
    print("=" * 50)
    print(f"Saving to: {os.path.abspath(CSV_PATH)}")
    print("Press Ctrl+C to stop.\n")

    row_count = 0

    with open(CSV_PATH, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        if not file_exists:
            writer.writeheader()

        while True:
            try:
                start = time.time()
                metrics = get_all_metrics()
                metrics['timestamp'] = datetime.datetime.now().isoformat()

                writer.writerow(metrics)
                f.flush()
                row_count += 1

                print(f"Row {row_count:>5} | "
                      f"Lat: {metrics['latency_ms']:>7.1f}ms | "
                      f"Loss: {metrics['packet_loss_pct']:>5.1f}% | "
                      f"DL: {metrics['download_mbps']:>6.2f} Mbps | "
                      f"UL: {metrics['upload_mbps']:>6.2f} Mbps | "
                      f"DNS: {metrics['dns_response_ms']:>7.1f}ms | "
                      f"GW: {metrics['gateway_ping_ms']:>7.1f}ms | "
                      f"Jitter: {metrics['jitter_ms']:>6.1f}ms | "
                      f"Devices: {metrics['connected_devices']:>3}")

                # Keep interval accurate even if collection took time
                elapsed = time.time() - start
                sleep_time = max(0, INTERVAL - elapsed)
                time.sleep(sleep_time)

            except KeyboardInterrupt:
                print(f"\nStopped. Total rows collected: {row_count}")
                break
            except Exception as e:
                print(f"[ERROR] {e}")
                time.sleep(INTERVAL)

if __name__ == "__main__":
    main()