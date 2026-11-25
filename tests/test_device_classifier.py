import pandas as pd

from scripts import device_classifier


def test_classifier_maps_confidence_and_preserves_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(device_classifier, "DATA", tmp_path)
    pd.DataFrame(
        [
            {
                "ip": "192.0.2.10",
                "mac": "AA:BB:CC:DD:EE:FF",
                "hostname": "ap-office",
                "vendor": "Example Networks",
                "vendor_role": "network",
                "mac_type": "global",
                "vendor_confidence": "90",
                "device_confidence": "80",
                "classification": "access_point",
                "evidence": "hostname and vendor hints",
            },
            {
                "ip": "192.0.2.11",
                "mac": "",
                "hostname": "",
                "vendor": "",
                "vendor_role": "",
                "mac_type": "",
                "vendor_confidence": "bad-value",
                "device_confidence": "55",
                "classification": "unknown",
                "evidence": "",
            },
            {
                "ip": "192.0.2.12",
                "mac": "",
                "hostname": "",
                "vendor": "",
                "vendor_role": "",
                "mac_type": "",
                "vendor_confidence": "0",
                "device_confidence": "20",
                "classification": "unknown",
                "evidence": "",
            },
        ]
    ).to_csv(tmp_path / "device_intelligence.csv", index=False)

    result = device_classifier.run()

    assert [row["confidence"] for row in result] == ["high", "medium", "low"]
    assert result[0]["identity_hint"] == "ap-office"
    assert result[0]["note"] == "hostname and vendor hints"
    assert result[1]["device_confidence"] == 55
    assert result[1]["vendor_confidence"] == 0
    assert (tmp_path / "device_classification.csv").is_file()


def test_classifier_returns_empty_when_source_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(device_classifier, "DATA", tmp_path)

    assert device_classifier.run() == []
    assert not (tmp_path / "device_classification.csv").exists()


def test_infrastructure_role_uses_hostname_evidence_not_vendor_alone():
    from scripts.device_intelligence import classify_infrastructure_role

    assert classify_infrastructure_role("office-router", "Example Inc.") == (
        "Router / Gateway", 85, "hostname_role_hint"
    )
    assert classify_infrastructure_role("device-01", "Ruijie Networks") == (
        "Network equipment candidate", 30, "vendor_only"
    )
    assert classify_infrastructure_role("device-02", "Unknown Vendor") == (
        "Unknown", 0, "insufficient_evidence"
    )


def test_known_model_family_is_still_marked_as_inference():
    from scripts.device_intelligence import classify_infrastructure_role

    assert classify_infrastructure_role("RAP2200E-office", "Ruijie") == (
        "Access Point", 85, "hostname_model_family_inference"
    )


def test_classifier_preserves_infrastructure_role_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(device_classifier, "DATA", tmp_path)
    pd.DataFrame([{
        "ip": "192.0.2.30",
        "mac": "AA:BB:CC:DD:EE:30",
        "hostname": "office-router",
        "vendor": "Example Networks",
        "vendor_role": "network",
        "mac_type": "global",
        "vendor_confidence": "90",
        "device_confidence": "80",
        "classification": "Network device",
        "device_role": "Router / Gateway",
        "role_confidence": "85",
        "role_evidence_type": "hostname_role_hint",
        "evidence": "hostname hint",
    }]).to_csv(tmp_path / "device_intelligence.csv", index=False)

    result = device_classifier.run()

    assert result[0]["device_role"] == "Router / Gateway"
    assert result[0]["role_confidence"] == 85
    assert result[0]["role_evidence_type"] == "hostname_role_hint"
    saved = pd.read_csv(tmp_path / "device_classification.csv", dtype=str)
    assert saved.loc[0, "device_role"] == "Router / Gateway"
