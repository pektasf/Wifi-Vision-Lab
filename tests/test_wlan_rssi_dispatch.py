from datetime import datetime, timezone
from types import SimpleNamespace

from scripts.wlan_rssi import collector_availability, collect_rssi_measurements


def test_dispatcher_reports_native_backend_by_platform():
    assert collector_availability("Windows")["status"] == "implemented"
    assert collector_availability("Linux")["status"] == "implemented"
    assert collector_availability("Darwin")["status"] == "not_implemented"
    assert collector_availability("FreeBSD")["status"] == "unsupported_platform"


def test_dispatcher_routes_linux_measurement_to_iw_backend(tmp_path):
    def runner(args):
        if args == ["iw", "dev"]:
            return SimpleNamespace(returncode=0, stdout="phy#0\n    Interface wlan0\n")
        return SimpleNamespace(
            returncode=0,
            stdout="BSS 00:11:22:33:44:55(on wlan0)\n    signal: -65.0 dBm\n",
        )

    report = collect_rssi_measurements(
        system_name="Linux",
        key_path=tmp_path / "dispatch.key",
        now=datetime(2026, 11, 26, tzinfo=timezone.utc),
        command_runner=runner,
    )
    assert report["status"] == "available"
    assert report["measurement_count"] == 1


def test_dispatcher_does_not_claim_macos_support():
    report = collect_rssi_measurements(system_name="Darwin")
    assert report["status"] == "not_implemented"
    assert report["measurement_count"] == 0
