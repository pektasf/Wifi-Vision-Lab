import pandas as pd

from scripts.infrastructure_ui import assign_identity_keys


def test_assign_identity_keys_handles_mixed_and_missing_ip_mac():
    source = pd.DataFrame(
        [
            {"ip": "192.168.1.10", "mac": "aa:bb:cc:dd:ee:10"},
            {"ip": "", "mac": "aa:bb:cc:dd:ee:20"},
            {"ip": "", "mac": ""},
            {"ip": "", "mac": ""},
        ],
        index=[0, 1, 2, 3],
    )

    result = assign_identity_keys(source, "ip", "mac")

    assert result["_identity"].tolist() == [
        "192.168.1.10",
        "AA:BB:CC:DD:EE:20",
        "kayit-2",
        "kayit-3",
    ]
    assert result["_identity"].is_unique



def test_split_ap_client_records_requires_all_direct_verification_fields():
    from scripts.infrastructure_ui import split_ap_client_records

    frame = pd.DataFrame([
        {"client_mac": "AA:01", "verification_status": "verified",
         "confidence": "verified", "evidence_type": "direct_association"},
        {"client_mac": "AA:02", "verification_status": "verified",
         "confidence": "inferred", "evidence_type": "direct_association"},
        {"client_mac": "AA:03", "verification_status": "unverified",
         "confidence": "verified", "evidence_type": "direct_association"},
        {"client_mac": "AA:04", "verification_status": "verified",
         "confidence": "verified", "evidence_type": "shared_ssid"},
    ])

    result = split_ap_client_records(frame)

    assert result["verified"]["client_mac"].tolist() == ["AA:01"]
    assert result["unverified"]["client_mac"].tolist() == ["AA:02", "AA:03", "AA:04"]


def test_split_ap_client_records_never_promotes_missing_evidence():
    from scripts.infrastructure_ui import split_ap_client_records

    frame = pd.DataFrame([{"client_mac": "AA:01"}])
    result = split_ap_client_records(frame)

    assert result["verified"].empty
    assert len(result["unverified"]) == 1
    empty = split_ap_client_records(pd.DataFrame())
    assert empty["verified"].empty
    assert empty["unverified"].empty



def test_build_network_context_summary_formats_latest_local_adapter_snapshot():
    from scripts.infrastructure_ui import build_network_context_summary

    frame = pd.DataFrame([
        {
            "captured_at": "2026-11-26T10:00:00+03:00",
            "adapter": "Wi-Fi",
            "interface_index": "7",
            "local_ipv4": "192.0.2.10",
            "network_cidr": "192.0.2.0/24",
            "gateway": "192.0.2.1",
            "dhcp_enabled": "enabled",
            "dhcp_server": "192.0.2.1",
            "dhcp_lease_obtained": "2026-11-26T06:00:00Z",
            "dhcp_lease_expires": "2026-11-27T06:00:00Z",
        },
        {
            "captured_at": "2026-11-26T11:00:00+03:00",
            "adapter": "Local Area Connection* 12",
            "interface_index": "19",
            "local_ipv4": "192.168.137.1",
            "network_cidr": "192.168.137.0/24",
            "gateway": "",
            "dhcp_enabled": "disabled",
            "dhcp_server": "",
            "dhcp_lease_obtained": "",
            "dhcp_lease_expires": "",
        },
    ])

    summary = build_network_context_summary(frame)

    assert summary["adapter"] == "Local Area Connection* 12"
    assert summary["local_ipv4"] == "192.168.137.1"
    assert summary["network_cidr"] == "192.168.137.0/24"
    assert summary["gateway"] == "Yok"
    assert summary["dhcp_status"] == "Devre dışı"
    assert summary["dhcp_server"] == "Bilinmiyor"
    assert summary["interface_index"] == "19"


def test_build_network_context_summary_handles_missing_and_unknown_state():
    from scripts.infrastructure_ui import build_network_context_summary

    assert build_network_context_summary(pd.DataFrame()) is None
    summary = build_network_context_summary(pd.DataFrame([{
        "dhcp_enabled": "unknown",
    }]))

    assert summary["dhcp_status"] == "Bilinmiyor"
    assert summary["adapter"] == "Bilinmiyor"
    assert summary["gateway"] == "Yok"
