import pandas as pd

from scripts.behavior_analysis import (
    FINDING_FIELDS,
    analyze_inventory,
    run,
)


def test_analyze_inventory_finds_duplicate_ip_to_mac_mappings():
    inventory = pd.DataFrame([
        {"ip": "192.0.2.10", "mac": "aa:bb:cc:dd:ee:01"},
        {"ip": "192.0.2.11", "mac": "AA:BB:CC:DD:EE:01"},
        {"ip": "192.0.2.20", "mac": "AA:BB:CC:DD:EE:02"},
        {"ip": "192.0.2.20", "mac": "AA:BB:CC:DD:EE:03"},
    ])

    findings = analyze_inventory(inventory)
    types = [item["type"] for item in findings]

    assert types == ["MULTIPLE_IPS_SAME_MAC", "MULTIPLE_MACS_SAME_IP"]
    assert findings[0]["subject"] == "AA:BB:CC:DD:EE:01"
    assert "192.0.2.10, 192.0.2.11" in findings[0]["detail"]
    assert findings[1]["subject"] == "192.0.2.20"
    assert findings[0]["severity"] == "review"
    assert findings[0]["timestamp"]


def test_analyze_inventory_ignores_empty_and_single_mappings():
    inventory = pd.DataFrame([
        {"ip": "192.0.2.10", "mac": "AA:BB:CC:DD:EE:01"},
        {"ip": "192.0.2.10", "mac": "AA:BB:CC:DD:EE:01"},
        {"ip": "", "mac": ""},
        {"ip": "192.0.2.11", "mac": ""},
    ])
    assert analyze_inventory(inventory) == []


def test_analyze_inventory_returns_no_findings_for_missing_required_columns():
    assert analyze_inventory(pd.DataFrame({"hostname": ["device"]})) == []
    assert analyze_inventory(pd.DataFrame()) == []


def test_run_persists_findings_with_stable_schema(tmp_path):
    inventory_path = tmp_path / "device_inventory.csv"
    output_path = tmp_path / "behavior_findings.csv"
    pd.DataFrame([
        {"ip": "192.0.2.10", "mac": "AA:BB:CC:DD:EE:01"},
        {"ip": "192.0.2.11", "mac": "AA:BB:CC:DD:EE:01"},
    ]).to_csv(inventory_path, index=False)

    findings = run(inventory_path, output_path)
    saved = pd.read_csv(output_path, dtype=str).fillna("")

    assert len(findings) == 1
    assert list(saved.columns) == FINDING_FIELDS
    assert saved.loc[0, "type"] == "MULTIPLE_IPS_SAME_MAC"


def test_run_returns_empty_when_inventory_is_missing(tmp_path):
    assert run(tmp_path / "missing.csv", tmp_path / "findings.csv") == []



def test_prepare_temporal_context_returns_only_devices_with_ip_history():
    from scripts.behavior_analysis import prepare_temporal_context

    profiles = pd.DataFrame([
        {"identity_key": "AA:01", "hostname": "laptop", "ip_history": "192.0.2.1; 192.0.2.2",
         "ip_change_count": "1", "observation_count": "8", "first_seen": "2026-01-01",
         "last_seen": "2026-02-01"},
        {"identity_key": "AA:02", "hostname": "phone", "ip_history": "192.0.2.3",
         "ip_change_count": "0", "observation_count": "4", "first_seen": "2026-01-02",
         "last_seen": "2026-02-02"},
        {"identity_key": "AA:03", "hostname": "tablet", "ip_history": "192.0.2.4; 192.0.2.5; 192.0.2.6",
         "ip_change_count": "2", "observation_count": "9", "first_seen": "2026-01-03",
         "last_seen": "2026-02-03"},
    ])

    result = prepare_temporal_context(profiles)

    assert result["identity_key"].tolist() == ["AA:03", "AA:01"]
    assert result.iloc[0]["ip_change_count"] == "2"
    assert "_ip_change_count" not in result.columns


def test_prepare_temporal_context_handles_missing_columns_and_invalid_counts():
    from scripts.behavior_analysis import prepare_temporal_context

    result = prepare_temporal_context(pd.DataFrame([
        {"identity_key": "AA:01", "ip_change_count": "invalid"},
        {"identity_key": "AA:02", "ip_change_count": "1"},
    ]))

    assert result["identity_key"].tolist() == ["AA:02"]
    assert result.iloc[0]["hostname"] == ""
    assert prepare_temporal_context(pd.DataFrame()).empty
    assert prepare_temporal_context(pd.DataFrame({"hostname": ["unknown"]})).empty
