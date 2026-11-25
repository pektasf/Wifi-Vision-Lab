from scripts.device_fingerprints import resolve_device_fingerprint


def test_missing_model_and_firmware_remain_unknown():
    result = resolve_device_fingerprint({})

    assert result["model"] == ""
    assert result["model_status"] == "unknown"
    assert result["model_confidence"] == 0
    assert result["firmware_version"] == ""
    assert result["firmware_status"] == "unknown"
    assert result["firmware_confidence"] == 0
    assert result["fingerprint_evidence"] == "no_model_or_firmware_evidence"


def test_management_api_values_are_verified_with_provenance():
    result = resolve_device_fingerprint({
        "model": "RG-AP820-L",
        "model_source": "management_api",
        "firmware_version": "RGOS 11.9",
        "firmware_source": "management_api",
    })

    assert result["model"] == "RG-AP820-L"
    assert result["model_confidence"] == 95
    assert result["model_status"] == "verified"
    assert result["model_source"] == "management_api"
    assert result["firmware_version"] == "RGOS 11.9"
    assert result["firmware_status"] == "verified"
    assert result["fingerprint_evidence"] == (
        "model:management_api; firmware:management_api"
    )


def test_snmp_and_lldp_are_observations_not_verified_identity():
    result = resolve_device_fingerprint({
        "model": "Catalyst family",
        "model_source": "snmp_sysdescr",
        "firmware_version": "IOS-XE 17.x",
        "firmware_source": "lldp_system_description",
    })

    assert result["model_status"] == "observed_unverified"
    assert result["model_confidence"] == 85
    assert result["firmware_status"] == "observed_unverified"
    assert result["firmware_confidence"] == 75


def test_unknown_source_is_not_promoted_to_verified():
    result = resolve_device_fingerprint({
        "model": "Possible model",
        "model_source": "hostname_guess",
        "firmware": "Possible firmware",
    })

    assert result["model_status"] == "unverified"
    assert result["model_source"] == "unverified_input"
    assert result["model_confidence"] == 20
    assert result["firmware_status"] == "unverified"
    assert result["firmware_source"] == "unverified_input"


def test_placeholder_values_are_treated_as_missing():
    result = resolve_device_fingerprint({
        "model": "unknown",
        "model_source": "management_api",
        "firmware_version": "N/A",
        "firmware_source": "management_api",
    })

    assert result["model"] == ""
    assert result["model_status"] == "unknown"
    assert result["firmware_version"] == ""
    assert result["firmware_status"] == "unknown"



def test_classifier_preserves_model_and_firmware_provenance(tmp_path, monkeypatch):
    import pandas as pd
    from scripts import device_classifier

    monkeypatch.setattr(device_classifier, "DATA", tmp_path)
    pd.DataFrame([{
        "ip": "192.0.2.44",
        "hostname": "edge-device",
        "vendor": "Example Networks",
        "device_role": "Network equipment candidate",
        "role_confidence": "30",
        "role_evidence_type": "vendor_only",
        "model": "RG-AP820-L",
        "model_confidence": "95",
        "model_status": "verified",
        "model_source": "management_api",
        "firmware_version": "RGOS 11.9",
        "firmware_confidence": "95",
        "firmware_status": "verified",
        "firmware_source": "management_api",
        "fingerprint_evidence": "model:management_api; firmware:management_api",
        "vendor_confidence": "95",
        "device_confidence": "80",
        "classification": "Network device",
        "evidence": "fixture",
    }]).to_csv(tmp_path / "device_intelligence.csv", index=False)

    result = device_classifier.run()

    assert result[0]["model"] == "RG-AP820-L"
    assert result[0]["model_status"] == "verified"
    assert result[0]["firmware_version"] == "RGOS 11.9"
    assert result[0]["firmware_source"] == "management_api"
    saved = pd.read_csv(tmp_path / "device_classification.csv", dtype=str)
    assert saved.loc[0, "model"] == "RG-AP820-L"
    assert saved.loc[0, "firmware_version"] == "RGOS 11.9"
