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
