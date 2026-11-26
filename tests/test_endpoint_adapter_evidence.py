import pytest

from scripts.discovery.endpoint_adapter_evidence import (
    normalize_endpoint_adapter_payload,
)


def test_endpoint_payload_reports_virtual_wlan_with_local_identity_fields():
    payload = {
        "schema_version": 1,
        "collector": "wifi_vision_endpoint",
        "observed_at": "2026-11-26T10:00:00Z",
        "adapters": [{
            "name": "Local Area Connection* 12",
            "description": "Microsoft Wi-Fi Direct Virtual Adapter",
            "mac": "02-11-22-33-44-55",
            "status": "Up",
            "hardware_interface": False,
            "adapter_kind": "virtual_or_software",
            "ipv4_addresses": ["192.168.137.20", "invalid"],
        }],
    }
    rows = normalize_endpoint_adapter_payload(payload)
    assert len(rows) == 1
    assert rows[0]["endpoint_mac"] == "02:11:22:33:44:55"
    assert rows[0]["endpoint_ip"] == "192.168.137.20"
    assert rows[0]["adapter_kind"] == "virtual_wlan"
    assert rows[0]["evidence_status"] == "endpoint_reported"


def test_endpoint_payload_keeps_software_adapter_distinct_from_virtual_wlan():
    payload = {
        "schema_version": 1,
        "collector": "wifi_vision_endpoint",
        "adapters": [{
            "name": "vEthernet",
            "description": "Hyper-V Virtual Ethernet Adapter",
            "mac": "00:11:22:33:44:55",
            "hardware_interface": False,
            "ipv4_addresses": ["10.0.0.2"],
        }],
    }
    rows = normalize_endpoint_adapter_payload(payload)
    assert rows[0]["adapter_kind"] == "virtual_or_software"


def test_endpoint_payload_does_not_upgrade_untrusted_claim_to_verified():
    payload = {
        "schema_version": 1,
        "collector": "wifi_vision_endpoint",
        "adapters": [{
            "name": "Wi-Fi",
            "description": "Intel Wireless",
            "mac": "00:11:22:33:44:55",
            "hardware_interface": True,
            "ipv4_addresses": ["192.168.1.10"],
            "verification_status": "verified",
        }],
    }
    rows = normalize_endpoint_adapter_payload(payload)
    assert rows[0]["evidence_status"] == "endpoint_reported"
    assert "verification_status" not in rows[0]


@pytest.mark.parametrize("payload", [
    None,
    [],
    {"schema_version": 2, "collector": "wifi_vision_endpoint", "adapters": []},
    {"schema_version": 1, "collector": "other", "adapters": []},
    {"schema_version": 1, "collector": "wifi_vision_endpoint", "adapters": "bad"},
])
def test_endpoint_payload_rejects_invalid_envelopes(payload):
    with pytest.raises(ValueError):
        normalize_endpoint_adapter_payload(payload)


def test_endpoint_payload_ignores_rows_without_valid_mac_or_ip():
    payload = {
        "schema_version": 1,
        "collector": "wifi_vision_endpoint",
        "adapters": [{
            "name": "Unknown",
            "mac": "not-a-mac",
            "ipv4_addresses": ["invalid"],
        }],
    }
    assert normalize_endpoint_adapter_payload(payload) == []
