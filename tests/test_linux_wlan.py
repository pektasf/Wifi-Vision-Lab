from datetime import datetime, timezone
from types import SimpleNamespace

from scripts.linux_wlan import (
    collect_linux_rssi_measurements,
    collector_availability,
    parse_iw_interfaces,
    parse_iw_scan_dump,
)


SAMPLE_SCAN = """BSS 00:11:22:33:44:55(on wlan0)
        last seen: 10.000s [boottime]
        TSF: 123 usec (0 days, 00:00:00)
        freq: 2412
        signal: -62.50 dBm
        SSID: private-network-name
BSS AA:BB:CC:DD:EE:FF(on wlan0)
        freq: 5180
        signal: -71.00 dBm
        SSID: another-private-network
"""


def test_parse_iw_interfaces_returns_unique_interface_names():
    output = """phy#0
    Interface wlan0
        ifindex 3
        type managed
phy#1
    Interface wlp2s0
        ifindex 4
        type managed
"""
    assert parse_iw_interfaces(output) == ["wlan0", "wlp2s0"]


def test_parse_iw_scan_dump_extracts_only_valid_rssi_and_bssid():
    entries = parse_iw_scan_dump(SAMPLE_SCAN)
    assert entries == [
        (bytes.fromhex("001122334455"), -62, 10.0),
        (bytes.fromhex("AABBCCDDEEFF"), -71, None),
    ]


def test_linux_collector_reads_cached_results_and_pseudonymises(tmp_path):
    calls = []

    def runner(args):
        calls.append(args)
        if args == ["iw", "dev"]:
            return SimpleNamespace(returncode=0, stdout="phy#0\n    Interface wlan0\n")
        if args == ["iw", "dev", "wlan0", "scan", "dump"]:
            return SimpleNamespace(returncode=0, stdout=SAMPLE_SCAN)
        raise AssertionError(f"Unexpected command: {args}")

    report = collect_linux_rssi_measurements(
        key_path=tmp_path / "linux-alias.key",
        now=datetime(2026, 11, 26, tzinfo=timezone.utc),
        command_runner=runner,
    )

    assert report["status"] == "available"
    assert report["measurement_count"] == 2
    assert next(iter(report["measurement_ages_seconds"].values())) == 10.0
    assert report["interfaces"][0]["name"] == "wlan0"
    assert report["collection_mode"] == "read_only_cached_bss_list_no_scan"
    assert report["privacy"]["raw_bssid_returned"] is False
    assert "001122334455" not in str(report)
    assert "private-network-name" not in str(report)
    assert calls == [
        ["iw", "dev"],
        ["iw", "dev", "wlan0", "scan", "dump"],
    ]


def test_linux_collector_reports_missing_iw_tool():
    def runner(_args):
        raise FileNotFoundError("iw")

    report = collect_linux_rssi_measurements(command_runner=runner)
    assert report["status"] == "unsupported_tool"
    assert report["errors"][0]["code"] == 127


def test_linux_collector_reports_missing_wifi_interface():
    report = collect_linux_rssi_measurements(
        command_runner=lambda _args: SimpleNamespace(returncode=0, stdout=""),
    )
    assert report["status"] == "no_wifi_interface"
    assert report["measurement_count"] == 0


def test_linux_collector_reports_permission_error_per_interface():
    def runner(args):
        if args == ["iw", "dev"]:
            return SimpleNamespace(returncode=0, stdout="phy#0\n    Interface wlan0\n")
        return SimpleNamespace(returncode=1, stdout="", stderr="Operation not permitted")

    report = collect_linux_rssi_measurements(command_runner=runner)
    assert report["status"] == "unavailable"
    assert report["interfaces"][0]["status"] == "error"
    assert "permissions" in report["errors"][0]["message"]


def test_linux_collector_reports_empty_cached_bss_list():
    def runner(args):
        if args == ["iw", "dev"]:
            return SimpleNamespace(returncode=0, stdout="phy#0\n    Interface wlan0\n")
        return SimpleNamespace(returncode=0, stdout="")

    report = collect_linux_rssi_measurements(command_runner=runner)
    assert report["status"] == "no_measurements"
    assert report["interfaces"][0]["status"] == "empty_bss_list"


def test_linux_backend_availability_is_explicit():
    assert collector_availability("Linux")["status"] == "implemented"
    assert collector_availability("Windows")["status"] == "not_implemented"
