import ctypes
from datetime import datetime, timezone

from scripts.windows_wlan import (
    _WLAN_BSS_ENTRY,
    _WLAN_INTERFACE_INFO,
    _load_local_alias_key,
    _alias_for_bssid,
    collector_availability,
    collect_windows_rssi_measurements,
    normalise_bss_entries,
    describe_wlan_error,
)


def test_windows_wlan_struct_layout_matches_windows_sdk():
    # SDK WLAN_BSS_ENTRY is 360 bytes and WLAN_INTERFACE_INFO is 532 bytes.
    assert ctypes.sizeof(_WLAN_BSS_ENTRY) == 360
    assert ctypes.sizeof(_WLAN_INTERFACE_INFO) == 532


def test_bssid_is_pseudonymised_and_alias_is_stable(tmp_path):
    key_path = tmp_path / "local.key"
    key = _load_local_alias_key(key_path)
    bssid = bytes.fromhex("AABBCCDDEEFF")

    assert len(key) == 32
    assert _load_local_alias_key(key_path) == key
    alias = _alias_for_bssid(bssid, key)
    assert alias.startswith("AP-")
    assert "AABBCCDDEEFF" not in alias
    assert alias == _alias_for_bssid(bssid, key)


def test_normalise_bss_entries_filters_invalid_rssi_and_deduplicates(tmp_path):
    key = _load_local_alias_key(tmp_path / "local.key")
    bssid_a = bytes.fromhex("001122334455")
    bssid_b = bytes.fromhex("AABBCCDDEEFF")

    measurements = normalise_bss_entries(
        [
            (bssid_a, -71),
            (bssid_a, -60),
            (bssid_b, -82),
            (bssid_b, -121),
            (b"bad", -55),
            (bytes.fromhex("102030405060"), 0),
        ],
        key,
    )

    assert len(measurements) == 2
    assert measurements[_alias_for_bssid(bssid_a, key)] == -60
    assert measurements[_alias_for_bssid(bssid_b, key)] == -82
    assert all(-120 <= value <= -1 for value in measurements.values())
    assert all(":" not in alias for alias in measurements)


def test_collector_report_privacy_and_measurements(tmp_path):
    class FakeFunction:
        def __call__(self, *args):
            raise AssertionError("Native calls are not expected in this test.")

    class FakeApi:
        WlanOpenHandle = FakeFunction()
        WlanEnumInterfaces = FakeFunction()
        WlanGetNetworkBssList = FakeFunction()
        WlanFreeMemory = FakeFunction()
        WlanCloseHandle = FakeFunction()

    # The native boundary is tested separately by the CI platform; this checks
    # output contract and alias handling through a narrow injected seam.
    from scripts import windows_wlan

    original_query = windows_wlan._query_bss_entries
    try:
        windows_wlan._query_bss_entries = lambda _api: {
            "entries": [(bytes.fromhex("AABBCCDDEEFF"), -63)],
            "interfaces_seen": 1,
            "interfaces_queried": 1,
            "interfaces_with_entries": 1,
            "interface_error_codes": [],
        }
        report = collect_windows_rssi_measurements(
            key_path=tmp_path / "local.key",
            now=datetime(2026, 11, 26, tzinfo=timezone.utc),
            api=FakeApi(),
        )
    finally:
        windows_wlan._query_bss_entries = original_query

    assert report["status"] == "available"
    assert report["measurement_count"] == 1
    assert report["collection_mode"] == "read_only_bss_list_no_wlan_scan_call"
    assert report["privacy"]["raw_bssid_returned"] is False
    assert "AABBCCDDEEFF" not in str(report)
    assert next(iter(report["measurements"].values())) == -63


def test_platform_availability_is_explicit():
    assert collector_availability("Windows")["status"] == "implemented"
    assert collector_availability("Linux")["status"] == "not_implemented"
    assert collector_availability("macOS")["status"] == "not_implemented"



def test_collector_distinguishes_missing_interface_and_empty_scan_list(tmp_path, monkeypatch):
    from scripts import windows_wlan

    monkeypatch.setattr(
        windows_wlan,
        "_query_bss_entries",
        lambda _api: {
            "entries": [],
            "interfaces_seen": 0,
            "interfaces_queried": 0,
            "interfaces_with_entries": 0,
            "interface_error_codes": [],
        },
    )
    no_adapter = collect_windows_rssi_measurements(
        key_path=tmp_path / "no-adapter.key", api=object()
    )
    assert no_adapter["status"] == "no_wifi_interface"

    monkeypatch.setattr(
        windows_wlan,
        "_query_bss_entries",
        lambda _api: {
            "entries": [],
            "interfaces_seen": 1,
            "interfaces_queried": 1,
            "interfaces_with_entries": 0,
            "interface_error_codes": [],
        },
    )
    empty = collect_windows_rssi_measurements(
        key_path=tmp_path / "empty.key", api=object()
    )
    assert empty["status"] == "no_measurements"


def test_collector_reports_partial_interface_errors(tmp_path, monkeypatch):
    from scripts import windows_wlan

    monkeypatch.setattr(
        windows_wlan,
        "_query_bss_entries",
        lambda _api: {
            "entries": [(bytes.fromhex("AABBCCDDEEFF"), -63)],
            "interfaces_seen": 2,
            "interfaces_queried": 1,
            "interfaces_with_entries": 1,
            "interface_error_codes": [1062],
        },
    )
    report = collect_windows_rssi_measurements(
        key_path=tmp_path / "partial.key", api=object()
    )

    assert report["status"] == "available_with_warnings"
    assert report["interfaces_seen"] == 2
    assert report["interfaces_queried"] == 1
    assert report["errors"][0]["code"] == 1062
    assert "WLAN AutoConfig" in report["errors"][0]["message"]


def test_wlan_error_messages_are_actionable_and_safe():
    assert "privacy" in describe_wlan_error(5).casefold()
    assert "WLAN AutoConfig" in describe_wlan_error(1062)
    assert "0xDEADBEEF" in describe_wlan_error(0xDEADBEEF)
