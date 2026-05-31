"""
test_collector.py — Unit tests for the metrics collector
"""
import os, sys, pytest
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "collector"))

class TestMetrics:
    def test_get_all_metrics_returns_dict(self):
        from metrics import get_all_metrics
        result = get_all_metrics()
        assert isinstance(result, dict)
        assert len(result) == 8

    def test_all_keys_present(self):
        from metrics import get_all_metrics
        result = get_all_metrics()
        for k in ["latency_ms","packet_loss_pct","download_mbps","upload_mbps",
                   "connected_devices","dns_response_ms","gateway_ping_ms","jitter_ms"]:
            assert k in result

    def test_values_numeric(self):
        from metrics import get_all_metrics
        for v in get_all_metrics().values():
            assert isinstance(v, (int, float))

    def test_bandwidth_tuple(self):
        from metrics import get_bandwidth
        dl, ul = get_bandwidth()
        assert isinstance(dl, float) and isinstance(ul, float)

    def test_dns_response(self):
        from metrics import get_dns_response
        assert get_dns_response() >= 0
