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
