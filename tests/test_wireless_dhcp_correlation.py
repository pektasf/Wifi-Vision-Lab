import pytest

from scripts.discovery.wireless_dhcp_correlation import (
    correlate_wireless_dhcp_observations,
)


MAC = "00:11:22:33:44:55"


def _wireless(**overrides):
    return {
        "observed_at": "2026-11-26T10:00:00Z",
        "mac": MAC,
        "last_bssid": "00:AA:BB:CC:DD:EE",
        "signal_dbm": "-62",
        "randomized_mac": "false",
        **overrides,
    }


def _dhcp(**overrides):
    return {
        "observed_at": "2026-11-26T10:02:00Z",
        "mac": MAC,
        "assigned_ip": "192.168.1.25",
        "server_ip": "192.168.1.1",
        **overrides,
    }


def test_exact_mac_and_time_near_with_equal_explicit_scope():
    rows = correlate_wireless_dhcp_observations(
        [_wireless(network_id="192.168.1.0/24")],
        [_dhcp(network_id="192.168.1.0/24")],
    )
    assert len(rows) == 1
    assert rows[0]["correlation_status"] == "exact_mac_time_near_scope_match"
    assert rows[0]["time_delta_seconds"] == 120
    assert rows[0]["wireless_bssid_context"] == "00:AA:BB:CC:DD:EE"


def test_different_explicit_network_scopes_are_not_correlated():
    rows = correlate_wireless_dhcp_observations(
        [_wireless(network_id="192.168.1.0/24")],
        [_dhcp(network_id="192.168.2.0/24")],
    )
    assert rows == []


def test_missing_scope_is_explicitly_uncertain():
    rows = correlate_wireless_dhcp_observations(
        [_wireless()],
        [_dhcp()],
    )
    assert len(rows) == 1
    assert rows[0]["correlation_status"] == "exact_mac_time_near_scope_unknown"


def test_randomized_mac_is_not_promoted_to_device_identity():
    rows = correlate_wireless_dhcp_observations(
        [_wireless(randomized_mac="true")],
        [_dhcp()],
    )
    assert len(rows) == 1
    assert rows[0]["correlation_status"] == "exact_mac_time_near_randomized_mac"
    assert "fiziksel cihaz kimliği doğrulanmaz" in rows[0]["interpretation"]


def test_bssid_is_context_only_and_never_used_as_client_mac():
    rows = correlate_wireless_dhcp_observations(
        [_wireless(mac="00:AA:BB:CC:DD:EE")],
        [_dhcp()],
    )
    assert rows == []


def test_different_client_macs_are_not_correlated_even_with_same_bssid():
    rows = correlate_wireless_dhcp_observations(
        [_wireless(mac="00:11:22:33:44:66")],
        [_dhcp()],
    )
    assert rows == []


def test_outside_time_window_is_not_correlated():
    rows = correlate_wireless_dhcp_observations(
        [_wireless(observed_at="2026-11-26T09:00:00Z")],
        [_dhcp()],
    )
    assert rows == []


def test_missing_or_invalid_timestamps_are_not_correlated():
    rows = correlate_wireless_dhcp_observations(
        [_wireless(observed_at="not-a-time")],
        [_dhcp(observed_at="")],
    )
    assert rows == []


def test_timezone_offsets_are_compared_as_instants():
    rows = correlate_wireless_dhcp_observations(
        [_wireless(observed_at="2026-11-26T13:00:00+03:00")],
        [_dhcp(observed_at="2026-11-26T10:01:00Z")],
    )
    assert len(rows) == 1
    assert rows[0]["time_delta_seconds"] == 60


def test_multiple_pairs_are_deterministic_and_limited():
    wireless = [
        _wireless(observed_at="2026-11-26T10:00:00Z"),
        _wireless(observed_at="2026-11-26T10:01:00Z"),
    ]
    dhcp = [_dhcp(observed_at="2026-11-26T10:02:00Z")]
    rows = correlate_wireless_dhcp_observations(wireless, dhcp, limit=1)
    assert len(rows) == 1
    assert rows[0]["time_delta_seconds"] == 60


@pytest.mark.parametrize("window", [0, -1, 3601, "bad"])
def test_invalid_time_window_is_rejected(window):
    with pytest.raises(ValueError):
        correlate_wireless_dhcp_observations([], [], window_seconds=window)


def test_duplicate_same_mac_observations_remain_separate_pairs():
    rows = correlate_wireless_dhcp_observations(
        [
            _wireless(device_key="kismet-a"),
            _wireless(device_key="kismet-b", observed_at="2026-11-26T10:01:00Z"),
        ],
        [_dhcp()],
    )
    assert len(rows) == 2
    assert {row["wireless_source_index"] for row in rows} == {0, 1}
