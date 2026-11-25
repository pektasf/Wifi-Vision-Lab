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
    assert result[1]["vendor_confidence"] == 0
    assert (tmp_path / "device_classification.csv").is_file()


def test_classifier_returns_empty_when_source_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(device_classifier, "DATA", tmp_path)

    assert device_classifier.run() == []
    assert not (tmp_path / "device_classification.csv").exists()
