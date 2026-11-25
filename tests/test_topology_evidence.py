import pandas as pd

from scripts.network_topology import build_topology


def test_shared_subnet_creates_context_edges_not_physical_links():
    inventory = pd.DataFrame([
        {
            "timestamp": "2026-01-01T10:00:00+03:00",
            "ip": "192.168.1.1", "mac": "AA:BB:CC:DD:EE:01",
            "hostname": "router", "status": "responding",
            "gateway": "192.168.1.1", "subnet": "192.168.1.0/24",
        },
        {
            "timestamp": "2026-01-01T10:00:00+03:00",
            "ip": "192.168.1.20", "mac": "AA:BB:CC:DD:EE:20",
            "hostname": "laptop", "status": "responding",
            "gateway": "192.168.1.1", "subnet": "192.168.1.0/24",
        },
    ])

    nodes, edges = build_topology(inventory)
    relations = {edge["relation"] for edge in edges}

    assert "observed_in_scope" in relations
    assert "configured_default_gateway" in relations
    assert all(edge["confidence"] == "context_only" for edge in edges)
    assert not any(edge["relation"] in {"connected_to", "physical_link"} for edge in edges)
    assert any(node["node_type"] == "gateway_address" for node in nodes)


def test_remote_scan_scope_does_not_mislabel_local_gateway_as_target_gateway():
    inventory = pd.DataFrame([{
        "timestamp": "2026-01-01",
        "ip": "10.20.30.15", "mac": "AA:BB:CC:DD:EE:15",
        "hostname": "host", "status": "responding",
        "gateway": "192.168.1.1", "subnet": "10.20.30.0/24",
    }])

    nodes, edges = build_topology(inventory)

    assert not any(node["node_type"] == "gateway_address" for node in nodes)
    assert all(edge["relation"] != "configured_default_gateway" for edge in edges)


def test_only_verified_direct_wlan_association_creates_ap_client_edge():
    inventory = pd.DataFrame([{
        "timestamp": "2026-01-01",
        "ip": "192.168.1.20", "mac": "AA:BB:CC:DD:EE:20",
        "hostname": "laptop", "status": "responding",
        "gateway": "192.168.1.1", "subnet": "192.168.1.0/24",
    }])
    ap_records = pd.DataFrame([
        {
            "observed_at": "2026-01-01T10:00:00+03:00",
            "client_mac": "AA:BB:CC:DD:EE:20",
            "client_ip": "192.168.1.20",
            "client_hostname": "laptop",
            "ap_bssid": "AA:BB:CC:DD:EE:99",
            "ssid": "Test WiFi",
            "source": "windows_wlan",
            "evidence_type": "direct_association",
            "verification_status": "verified",
        },
        {
            "observed_at": "2026-01-01T10:00:00+03:00",
            "client_mac": "AA:BB:CC:DD:EE:20",
            "ap_bssid": "AA:BB:CC:DD:EE:98",
            "source": "untrusted_guess",
            "evidence_type": "inferred",
            "verification_status": "unverified",
        },
    ])

    nodes, edges = build_topology(inventory, ap_relationships=ap_records)
    associations = [edge for edge in edges if edge["relation"] == "wifi_association"]

    assert len(associations) == 1
    assert associations[0]["confidence"] == "verified"
    assert associations[0]["evidence_type"] == "direct_association"
    assert associations[0]["source"] == "BSSID:AA:BB:CC:DD:EE:99"
    assert associations[0]["target"] == "192.168.1.20"
    assert any(node["node_type"] == "access_point_radio" for node in nodes)


def test_invalid_mac_values_do_not_create_wifi_relationships():
    inventory = pd.DataFrame([{
        "timestamp": "2026-01-01",
        "ip": "192.168.1.20", "mac": "AA:BB:CC:DD:EE:20",
        "hostname": "laptop", "status": "responding",
        "subnet": "192.168.1.0/24",
    }])
    ap_records = pd.DataFrame([{
        "client_mac": "not-a-mac", "ap_bssid": "also-invalid",
        "evidence_type": "direct_association",
        "verification_status": "verified",
    }])

    nodes, edges = build_topology(inventory, ap_relationships=ap_records)
    assert not any(edge["relation"] == "wifi_association" for edge in edges)


def test_hostname_based_network_role_remains_an_inference():
    inventory = pd.DataFrame([{
        "timestamp": "2026-01-01",
        "ip": "192.168.1.2", "mac": "AA:BB:CC:DD:EE:02",
        "hostname": "access point 01", "status": "responding",
        "subnet": "192.168.1.0/24",
    }])

    nodes, _ = build_topology(inventory)
    candidate = next(node for node in nodes if node["ip"] == "192.168.1.2")

    assert candidate["node_type"] == "network_device_candidate"
    assert candidate["confidence"] == "inferred"


def test_topology_uses_latest_verified_ap_association_per_client():
    inventory = pd.DataFrame([{
        "timestamp": "2026-01-01",
        "ip": "192.168.1.20", "mac": "AA:BB:CC:DD:EE:20",
        "hostname": "laptop", "status": "responding",
        "subnet": "192.168.1.0/24",
    }])
    ap_records = pd.DataFrame([
        {
            "observed_at": "2026-01-01T10:00:00+03:00",
            "client_mac": "AA:BB:CC:DD:EE:20",
            "ap_bssid": "AA:BB:CC:DD:EE:98",
            "ssid": "Old AP",
            "source": "windows_wlan",
            "evidence_type": "direct_association",
            "verification_status": "verified",
        },
        {
            "observed_at": "2026-01-01T06:30:00Z",
            "client_mac": "AA:BB:CC:DD:EE:20",
            "ap_bssid": "AA:BB:CC:DD:EE:99",
            "ssid": "Current AP",
            "source": "windows_wlan",
            "evidence_type": "direct_association",
            "verification_status": "verified",
        },
    ])

    nodes, edges = build_topology(inventory, ap_relationships=ap_records)
    associations = [edge for edge in edges if edge["relation"] == "wifi_association"]

    assert len(associations) == 1
    assert associations[0]["source"] == "BSSID:AA:BB:CC:DD:EE:98"
    assert associations[0]["target"] == "192.168.1.20"
    assert associations[0]["observed_at"] == "2026-01-01T10:00:00+03:00"
    assert not any(node["id"] == "BSSID:AA:BB:CC:DD:EE:99" for node in nodes)


def test_topology_uses_last_row_when_association_timestamps_are_missing():
    inventory = pd.DataFrame([{
        "timestamp": "2026-01-01",
        "ip": "192.168.1.20", "mac": "AA:BB:CC:DD:EE:20",
        "hostname": "laptop", "status": "responding",
    }])
    ap_records = pd.DataFrame([
        {
            "client_mac": "AA:BB:CC:DD:EE:20",
            "ap_bssid": "AA:BB:CC:DD:EE:98",
            "evidence_type": "direct_association",
            "verification_status": "verified",
        },
        {
            "client_mac": "AA:BB:CC:DD:EE:20",
            "ap_bssid": "AA:BB:CC:DD:EE:99",
            "evidence_type": "direct_association",
            "verification_status": "verified",
        },
    ])

    _, edges = build_topology(inventory, ap_relationships=ap_records)
    associations = [edge for edge in edges if edge["relation"] == "wifi_association"]

    assert len(associations) == 1
    assert associations[0]["source"] == "BSSID:AA:BB:CC:DD:EE:99"



def test_topology_ui_separates_verified_inferred_context_and_unknown_edges():
    from scripts.topology_evidence import split_topology_edges

    edges = pd.DataFrame([
        {"source": "ap", "target": "client", "relation": "wifi_association",
         "confidence": "verified", "evidence_type": "direct_association"},
        {"source": "candidate", "target": "host", "relation": "possible_role",
         "confidence": "inferred", "evidence_type": "hostname_hint"},
        {"source": "scope", "target": "host", "relation": "observed_in_scope",
         "confidence": "context_only", "evidence_type": "shared_scan_scope"},
        {"source": "x", "target": "y", "relation": "unknown",
         "confidence": "", "evidence_type": ""},
        {"source": "", "target": "orphan", "relation": "wifi_association",
         "confidence": "verified", "evidence_type": "direct_association"},
    ])

    groups = split_topology_edges(edges, "source", "target")

    assert len(groups["verified"]) == 1
    assert groups["verified"].iloc[0]["source"] == "ap"
    assert len(groups["inferred"]) == 1
    assert len(groups["context"]) == 1
    assert len(groups["unverified"]) == 1


def test_missing_confidence_is_never_promoted_to_verified():
    from scripts.topology_evidence import split_topology_edges

    edges = pd.DataFrame([{
        "source": "a", "target": "b", "relation": "connected_to"
    }])

    groups = split_topology_edges(edges, "source", "target")

    assert groups["verified"].empty
    assert len(groups["unverified"]) == 1



def test_association_history_is_sorted_newest_first_across_timezones():
    from scripts.topology_evidence import prepare_association_history

    history = pd.DataFrame([
        {"observed_at": "2026-01-01T10:00:00+03:00", "ap_bssid": "older"},
        {"observed_at": "2026-01-01T08:30:00Z", "ap_bssid": "newer"},
        {"observed_at": "invalid-date", "ap_bssid": "unknown"},
    ])

    result = prepare_association_history(history)

    assert result["ap_bssid"].tolist() == ["newer", "older", "unknown"]
    assert "_observed_at_utc" not in result.columns


def test_association_history_without_timestamp_preserves_reverse_file_order():
    from scripts.topology_evidence import prepare_association_history

    history = pd.DataFrame([{"ap_bssid": "first"}, {"ap_bssid": "second"}])

    result = prepare_association_history(history)

    assert result["ap_bssid"].tolist() == ["second", "first"]
