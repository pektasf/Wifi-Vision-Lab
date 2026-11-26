import json

import pytest

from scripts.discovery.zeek_import import normalize_zeek_dhcp_export


def test_zeek_dhcp_json_import_preserves_lease_mac_and_hostname_evidence():
    payload = [{
        "ts": "2026-11-26T10:00:00.123456Z",
        "client_addr": "192.168.1.42",
        "server_addr": "192.168.1.1",
        "mac": "02:11:22:33:44:55",
        "host_name": "fixture-phone",
        "client_fqdn": "fixture-phone.local",
        "requested_addr": "192.168.1.42",
        "assigned_addr": "192.168.1.42",
        "lease_time": 86400,
        "duration": 0.42,
        "msg_types": ["DISCOVER", "OFFER", "REQUEST", "ACK"],
    }]

    rows = normalize_zeek_dhcp_export(
        json.dumps(payload),
        imported_at="2026-11-26T10:01:00+00:00",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "zeek_dhcp_import"
    assert row["client_ip"] == "192.168.1.42"
    assert row["assigned_ip"] == "192.168.1.42"
    assert row["server_ip"] == "192.168.1.1"
    assert row["mac"] == "02:11:22:33:44:55"
    assert row["hostname"] == "fixture-phone"
    assert row["client_fqdn"] == "fixture-phone.local"
    assert row["lease_time_seconds"] == "86400"
    assert row["duration_seconds"] == "0.42"
    assert row["message_types"] == "DISCOVER;OFFER;REQUEST;ACK"
    assert row["mac_address_type"] == "locally_administered"
    assert "locally_administered_mac" in row["evidence_status"]
    assert row["imported_at"] == "2026-11-26T10:01:00+00:00"


def test_zeek_dhcp_ndjson_import_accepts_client_chaddr_and_sparse_records():
    records = [
        {
            "ts": "2026-11-26T10:00:00Z",
            "client_chaddr": "00:11:22:33:44:55",
            "msg_types": ["DISCOVER"],
        },
        {
            "ts": "2026-11-26T10:01:00Z",
            "host_name": "client-without-mac",
        },
    ]
    text = "\n".join(json.dumps(item) for item in records)

    rows = normalize_zeek_dhcp_export(text)

    assert len(rows) == 2
    assert rows[0]["mac"] == "00:11:22:33:44:55"
    assert rows[0]["mac_address_type"] == "universally_administered"
    assert rows[1]["mac"] == ""
    assert rows[1]["evidence_status"] == "dhcp_client_hostname_reported"


def test_zeek_dhcp_import_ignores_unspecified_or_invalid_ip_values():
    rows = normalize_zeek_dhcp_export(json.dumps([{
        "client_addr": "0.0.0.0",
        "assigned_addr": "999.1.1.1",
        "requested_addr": "255.255.255.255",
        "mac": "00:11:22:33:44:55",
    }]))
    assert len(rows) == 1
    assert rows[0]["client_ip"] == ""
    assert rows[0]["assigned_ip"] == ""
    assert rows[0]["requested_ip"] == ""


def test_zeek_dhcp_import_skips_records_without_any_client_identity():
    assert normalize_zeek_dhcp_export(json.dumps([{
        "server_addr": "192.168.1.1",
        "msg_types": ["OFFER"],
    }])) == []


@pytest.mark.parametrize("content", [
    b"\xff",
    "{not-json}",
    '{"mac":"00:11:22:33:44:55"}\nnot-json',
])
def test_zeek_dhcp_import_rejects_invalid_utf8_or_json(content):
    with pytest.raises(ValueError):
        normalize_zeek_dhcp_export(content)


def test_zeek_dhcp_import_rejects_files_over_size_limit():
    from scripts.discovery.zeek_import import MAX_ZEEK_BYTES

    with pytest.raises(ValueError, match="20 MB"):
        normalize_zeek_dhcp_export(b" " * (MAX_ZEEK_BYTES + 1))



@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        (0.25, "1970-01-01T00:00:00.250000Z"),
        (1700000000.25, "2023-11-14T22:13:20.250000Z"),
        (1700000000250, "2023-11-14T22:13:20.250000Z"),
    ],
)
def test_zeek_dhcp_import_normalizes_epoch_seconds_and_milliseconds(timestamp, expected):
    rows = normalize_zeek_dhcp_export(json.dumps([{
        "ts": timestamp,
        "mac": "00:11:22:33:44:55",
    }]))
    assert rows[0]["observed_at"] == expected


def test_zeek_dhcp_import_preserves_iso_timestamp_strings():
    timestamp = "2026-11-26T10:00:00.123456+03:00"
    rows = normalize_zeek_dhcp_export(json.dumps([{
        "ts": timestamp,
        "mac": "00:11:22:33:44:55",
    }]))
    assert rows[0]["observed_at"] == timestamp


@pytest.mark.parametrize("timestamp", [float("nan"), float("inf"), True])
def test_zeek_dhcp_import_does_not_emit_invalid_epoch_timestamps(timestamp):
    rows = normalize_zeek_dhcp_export(json.dumps([{
        "ts": timestamp,
        "mac": "00:11:22:33:44:55",
    }]))
    assert rows[0]["observed_at"] == ""
