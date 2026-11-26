from datetime import datetime, timezone
from types import SimpleNamespace

from scripts.spatial_capabilities import (
    collect_capabilities,
    parse_driver_output,
    parse_interface_output,
)


def test_parse_english_driver_metadata():
    parsed = parse_driver_output(
        """
Interface name : Wi-Fi
Driver         : Intel(R) Wi-Fi 6 AX201 160MHz
Vendor         : Intel Corporation
Provider       : Intel
Date           : 2025-01-01
Version        : 23.110.0.5
Radio types supported : 802.11b 802.11g 802.11n 802.11ac 802.11ax
Hosted network supported : No
"""
    )

    assert parsed["interface_name"] == "Wi-Fi"
    assert "AX201" in parsed["driver"]
    assert "802.11ax" in parsed["radio_types"]
    assert parsed["hosted_network"] == "No"


def test_parse_turkish_interface_without_exposing_network_identity():
    parsed = parse_interface_output(
        """
    Ad                   : Wi-Fi
    Durum                : bağlı
    SSID                 : PRIVATE-NETWORK-NAME
    BSSID                : AA:BB:CC:DD:EE:FF
    Sinyal               : 87%
    Kanal                : 36
    Radyo türü           : 802.11ax
"""
    )

    assert parsed["interface_name"] == "Wi-Fi"
    assert parsed["connected"] is True
    assert parsed["signal_percent"] == 87
    assert parsed["channel"] == "36"
    assert "PRIVATE-NETWORK-NAME" not in str(parsed)
    assert "AA:BB:CC:DD:EE:FF" not in str(parsed)


def test_parse_english_interface_without_connection():
    parsed = parse_interface_output(
        """
Name : Wi-Fi
State : disconnected
Signal : 0%
Channel : 0
Radio type : 802.11ax
"""
    )

    assert parsed["connected"] is False
    assert parsed["signal_percent"] == 0


def test_collect_capabilities_is_read_only_and_does_not_scan():
    calls = []

    def fake_runner(args):
        calls.append(args)
        if args[:4] == ["netsh", "wlan", "show", "drivers"]:
            output = "Driver : Example Wireless Adapter\nRadio types supported : 802.11n"
        elif args[:4] == ["netsh", "wlan", "show", "interfaces"]:
            output = "Name : Wi-Fi\nState : connected\nSignal : 72%"
        else:
            output = (
                '[{"Name":"Wi-Fi","InterfaceDescription":"Example Adapter",'
                '"Status":"Up","LinkSpeed":"866 Mbps"}]'
            )
        return SimpleNamespace(returncode=0, stdout=output, stderr="")

    report = collect_capabilities(
        command_runner=fake_runner,
        system_name="Windows",
        now=datetime(2026, 11, 26, tzinfo=timezone.utc),
    )

    assert report["collection_mode"] == "read_only_no_network_scan"
    assert report["active_interface"]["signal_percent"] == 72
    assert report["driver"]["driver"] == "Example Wireless Adapter"
    assert report["physical_adapters"][0]["Status"] == "Up"
    assert len(calls) == 3
    assert all("networks" not in " ".join(call).casefold() for call in calls)
    assert all("scan" not in " ".join(call).casefold() for call in calls)
    assert report["capabilities"]["csi"]["status"] == "unknown"


def test_non_windows_report_does_not_execute_commands():
    def fail_if_called(_args):
        raise AssertionError("No commands should run on non-Windows systems.")

    report = collect_capabilities(
        command_runner=fail_if_called,
        system_name="Linux",
    )

    assert report["operating_system"] == "Linux"
    assert report["physical_adapters"] == []
    assert report["commands"]["netsh_drivers"]["available"] is False
    assert report["capabilities"]["rssi_dbm"]["status"] == "not_implemented"



def test_windows_capability_report_distinguishes_rssi_backend_from_netsh_percent():
    report = collect_capabilities(
        command_runner=lambda _args: SimpleNamespace(returncode=1, stdout="", stderr=""),
        system_name="Windows",
    )
    assert report["capabilities"]["rssi_dbm"]["status"] == "collector_available_driver_dependent"
    assert "not converted to dBm" in report["capabilities"]["rssi_dbm"]["detail"]
