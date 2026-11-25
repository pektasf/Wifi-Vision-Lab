import pytest

from scripts.scan_policy import build_scan_targets, load_scan_settings


def test_private_subnet_targets_are_bounded_and_report_truncation():
    targets, truncated = build_scan_targets(
        "192.168.10.0/24", "192.168.10.20", "192.168.10.1", max_hosts=10
    )

    assert len(targets) == 10
    assert targets[0] == "192.168.10.1"
    assert truncated is True


def test_small_private_subnet_is_not_marked_truncated():
    targets, truncated = build_scan_targets(
        "192.168.10.0/29", "192.168.10.2", "192.168.10.1", max_hosts=10
    )

    assert len(targets) == 6
    assert truncated is False


@pytest.mark.parametrize(
    "network,local,gateway",
    [
        ("8.8.8.0/24", "8.8.8.10", "8.8.8.1"),
        ("127.0.0.0/8", "127.0.0.2", "127.0.0.1"),
        ("169.254.1.0/24", "169.254.1.2", "169.254.1.1"),
        ("192.168.10.0/24", "192.168.11.2", "192.168.10.1"),
        ("192.168.10.0/24", "192.168.10.2", "192.168.11.1"),
    ],
)
def test_rejects_nonlocal_or_unsafe_networks(network, local, gateway):
    with pytest.raises(ValueError):
        build_scan_targets(network, local, gateway)


def test_rejects_invalid_scan_limit():
    with pytest.raises(ValueError):
        build_scan_targets(
            "192.168.10.0/24", "192.168.10.2", "192.168.10.1", max_hosts=5000
        )


def test_scan_settings_have_safe_defaults(monkeypatch):
    for key in (
        "WIFI_VISION_MAX_SCAN_HOSTS",
        "WIFI_VISION_SCAN_WORKERS",
        "WIFI_VISION_PING_TIMEOUT_MS",
    ):
        monkeypatch.delenv(key, raising=False)

    assert load_scan_settings() == {
        "max_hosts": 1024,
        "workers": 32,
        "ping_timeout_ms": 600,
    }


def test_scan_settings_reject_unbounded_worker_count(monkeypatch):
    monkeypatch.setenv("WIFI_VISION_SCAN_WORKERS", "1000")
    with pytest.raises(ValueError):
        load_scan_settings()
