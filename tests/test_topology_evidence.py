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



def test_verified_edge_options_keep_duplicate_relationships_selectable():
    from scripts.topology_evidence import prepare_verified_edge_options

    edges = pd.DataFrame([
        {"source": "ap", "target": "client", "relation": "wifi_association",
         "observed_at": "2026-01-01T10:00:00Z"},
        {"source": "ap", "target": "client", "relation": "wifi_association",
         "observed_at": "2026-01-01T10:00:00Z"},
    ])

    options = prepare_verified_edge_options(edges, "source", "target")

    assert [item["index"] for item in options] == [0, 1]
    assert len({item["label"] for item in options}) == 2
    assert options[0]["label"].startswith("1. ")
    assert options[1]["label"].startswith("2. ")


def test_verified_edge_options_are_empty_without_usable_edge_schema():
    from scripts.topology_evidence import prepare_verified_edge_options

    assert prepare_verified_edge_options(pd.DataFrame(), "source", "target") == []
    assert prepare_verified_edge_options(
        pd.DataFrame([{"source": "a", "target": "b"}]), None, None
    ) == []



def test_extract_selected_node_id_from_plotly_selection():
    from scripts.topology_evidence import extract_selected_node_id

    selection = {"selection": {"points": [{"customdata": "192.168.1.20"}]}}

    assert extract_selected_node_id(selection) == "192.168.1.20"


def test_extract_selected_node_id_handles_attribute_objects_and_empty_selection():
    from types import SimpleNamespace
    from scripts.topology_evidence import extract_selected_node_id

    selection = SimpleNamespace(selection=SimpleNamespace(
        points=[SimpleNamespace(customdata=["BSSID:AA:BB:CC:DD:EE:99"])]
    ))

    assert extract_selected_node_id(selection) == "BSSID:AA:BB:CC:DD:EE:99"
    assert extract_selected_node_id({"selection": {"points": []}}) == ""
    assert extract_selected_node_id(None) == ""


def test_relationship_history_includes_both_directions_and_sorts_newest_first():
    from scripts.topology_evidence import prepare_relationship_history

    edges = pd.DataFrame([
        {"source": "ap", "target": "client", "relation": "wifi_association",
         "observed_at": "2026-01-01T10:00:00+03:00", "confidence": "verified"},
        {"source": "client", "target": "ap", "relation": "other_observation",
         "observed_at": "2026-01-01T08:30:00Z", "confidence": "context_only"},
        {"source": "ap", "target": "other", "relation": "unrelated",
         "observed_at": "2026-01-01T12:00:00Z"},
    ])

    result = prepare_relationship_history(edges, "ap", "client", "source", "target")

    assert len(result) == 2
    # 08:30Z is later than 10:00 at UTC+03:00 (07:00Z).
    assert result["relation"].tolist() == ["other_observation", "wifi_association"]
    assert result.iloc[0]["source"] == "client"


def test_relationship_history_preserves_file_order_without_timestamps():
    from scripts.topology_evidence import prepare_relationship_history

    edges = pd.DataFrame([
        {"source": "a", "target": "b", "relation": "first"},
        {"source": "b", "target": "a", "relation": "second"},
    ])

    result = prepare_relationship_history(edges, "a", "b", "source", "target")

    assert result["relation"].tolist() == ["second", "first"]


def test_relationship_history_is_empty_for_missing_pair_or_schema():
    from scripts.topology_evidence import prepare_relationship_history

    edges = pd.DataFrame([{"source": "a", "target": "b"}])

    assert prepare_relationship_history(edges, "", "b", "source", "target").empty
    assert prepare_relationship_history(edges, "a", "missing", "source", "target").empty
    assert prepare_relationship_history(edges, "a", "b", None, "target").empty



def test_topology_render_profile_uses_svg_for_small_maps_and_keeps_labels():
    from scripts.topology_evidence import topology_render_profile

    profile = topology_render_profile(120, 20)

    assert profile["use_webgl"] is False
    assert profile["show_labels"] is True


def test_topology_render_profile_simplifies_labels_for_dense_maps():
    from scripts.topology_evidence import topology_render_profile

    profile = topology_render_profile(121, 20)

    assert profile["use_webgl"] is False
    assert profile["show_labels"] is False


def test_topology_render_profile_switches_to_webgl_at_node_or_edge_threshold():
    from scripts.topology_evidence import topology_render_profile

    assert topology_render_profile(300, 10)["use_webgl"] is True
    assert topology_render_profile(40, 500)["use_webgl"] is True


def test_topology_render_profile_handles_missing_and_negative_counts():
    from scripts.topology_evidence import topology_render_profile

    profile = topology_render_profile(None, -5)

    assert profile == {
        "use_webgl": False,
        "show_labels": True,
        "node_count": 0,
        "edge_count": 0,
    }


def test_dhcp_server_configuration_adds_context_edge_not_physical_link():
    inventory = pd.DataFrame([{
        "timestamp": "2026-11-26T10:00:00+03:00",
        "ip": "192.168.137.20", "mac": "AA:BB:CC:DD:EE:20",
        "hostname": "phone", "status": "responding",
        "subnet": "192.168.137.0/24",
    }])
    network_context = pd.DataFrame([{
        "captured_at": "2026-11-26T10:00:00+03:00",
        "network_cidr": "192.168.137.0/24",
        "dhcp_enabled": "enabled",
        "dhcp_server": "192.168.137.1",
    }])

    nodes, edges = build_topology(inventory, network_context=network_context)
    dhcp_edges = [edge for edge in edges if edge["relation"] == "configured_dhcp_server"]
    server = next(node for node in nodes if node["id"] == "192.168.137.1")

    assert len(dhcp_edges) == 1
    assert dhcp_edges[0]["confidence"] == "context_only"
    assert dhcp_edges[0]["evidence_type"] == "dhcp_configuration"
    assert dhcp_edges[0]["source"] == "NETWORK:192.168.137.0/24"
    assert server["node_type"] == "dhcp_server_address"
    assert not any(edge["relation"] in {"connected_to", "physical_link"} for edge in edges)


def test_dhcp_server_is_not_added_when_dhcp_is_disabled_or_address_invalid():
    inventory = pd.DataFrame([{
        "ip": "192.168.137.20", "mac": "AA:BB:CC:DD:EE:20",
        "subnet": "192.168.137.0/24",
    }])
    disabled = pd.DataFrame([{
        "network_cidr": "192.168.137.0/24", "dhcp_enabled": "disabled",
        "dhcp_server": "192.168.137.1",
    }])
    invalid = pd.DataFrame([{
        "network_cidr": "192.168.137.0/24", "dhcp_enabled": "enabled",
        "dhcp_server": "not-an-ip",
    }])

    for context in (disabled, invalid):
        nodes, edges = build_topology(inventory, network_context=context)
        assert not any(node["node_type"] == "dhcp_server_address" for node in nodes)
        assert not any(edge["relation"] == "configured_dhcp_server" for edge in edges)


def test_distinct_bssids_with_same_ssid_are_not_merged_into_one_physical_ap():
    inventory = pd.DataFrame([{"ip": "192.168.1.20", "mac": "AA:BB:CC:DD:EE:20", "subnet": "192.168.1.0/24"}])
    relationships = pd.DataFrame([
        {"client_mac": "AA:BB:CC:DD:EE:20", "ap_bssid": "AA:BB:CC:DD:EE:01", "ssid": "Office", "source": "windows_wlan", "evidence_type": "direct_association", "verification_status": "verified", "observed_at": "2026-11-26T10:00:00Z"},
        {"client_mac": "AA:BB:CC:DD:EE:21", "ap_bssid": "AA:BB:CC:DD:EE:02", "ssid": "Office", "source": "windows_wlan", "evidence_type": "direct_association", "verification_status": "verified", "observed_at": "2026-11-26T10:01:00Z"},
    ])

    nodes, edges = build_topology(inventory, ap_relationships=relationships)
    radios = [node for node in nodes if node["node_type"] == "access_point_radio"]
    physical = [node for node in nodes if node["node_type"] == "access_point_device"]

    assert len(radios) == 2
    assert len(physical) == 0
    assert not any(edge["relation"] == "radio_of" for edge in edges)


def test_bssid_is_grouped_only_with_explicit_verified_ap_device_identity():
    inventory = pd.DataFrame([{"ip": "192.168.1.20", "mac": "AA:BB:CC:DD:EE:20", "subnet": "192.168.1.0/24"}])
    relationships = pd.DataFrame([{
        "client_mac": "AA:BB:CC:DD:EE:20",
        "ap_bssid": "AA:BB:CC:DD:EE:01",
        "ap_device_mac": "AA:BB:CC:DD:EF:00",
        "device_identity_verification": "verified",
        "device_identity_evidence": "direct_ap_device_identity",
        "device_identity_source": "trusted_local_controller",
        "ssid": "Office", "source": "windows_wlan",
        "evidence_type": "direct_association", "verification_status": "verified",
        "observed_at": "2026-11-26T10:00:00Z",
    }])

    nodes, edges = build_topology(inventory, ap_relationships=relationships)
    physical = next(node for node in nodes if node["node_type"] == "access_point_device")
    radio_edge = next(edge for edge in edges if edge["relation"] == "radio_of")

    assert physical["id"] == "AP_DEVICE:AA:BB:CC:DD:EF:00"
    assert physical["confidence"] == "verified"
    assert radio_edge["source"] == physical["id"]
    assert radio_edge["target"] == "BSSID:AA:BB:CC:DD:EE:01"
    assert radio_edge["confidence"] == "verified"


def test_unverified_or_invalid_ap_device_identity_does_not_group_radios():
    inventory = pd.DataFrame([{"ip": "192.168.1.20", "mac": "AA:BB:CC:DD:EE:20", "subnet": "192.168.1.0/24"}])
    for identity in [
        {"ap_device_mac": "AA:BB:CC:DD:EF:00", "device_identity_verification": "inferred", "device_identity_evidence": "direct_ap_device_identity"},
        {"ap_device_mac": "not-a-mac", "device_identity_verification": "verified", "device_identity_evidence": "direct_ap_device_identity"},
    ]:
        relationships = pd.DataFrame([{
            "client_mac": "AA:BB:CC:DD:EE:20", "ap_bssid": "AA:BB:CC:DD:EE:01",
            "ssid": "Office", "source": "windows_wlan",
            "evidence_type": "direct_association", "verification_status": "verified",
            "observed_at": "2026-11-26T10:00:00Z", **identity,
        }])
        nodes, edges = build_topology(inventory, ap_relationships=relationships)
        assert not any(node["node_type"] == "access_point_device" for node in nodes)
        assert not any(edge["relation"] == "radio_of" for edge in edges)


def test_verified_lldp_neighbor_creates_verified_topology_edge():
    from scripts.topology_evidence import prepare_verified_neighbor_edges
    records = pd.DataFrame([{
        "protocol": "lldp", "local_mac": "AA:BB:CC:DD:EE:01",
        "neighbor_mac": "AA:BB:CC:DD:EE:02",
        "verification_status": "verified",
        "evidence_type": "lldp_neighbor_advertisement",
        "evidence_source": "local_lldp_export", "local_port": "Gi1/0/1",
        "neighbor_port": "eth0",
    }])
    assert prepare_verified_neighbor_edges(records)[0]["relation"] == "lldp_neighbor"
    inventory = pd.DataFrame([{"ip": "192.168.1.2", "mac": "AA:BB:CC:DD:EE:01", "subnet": "192.168.1.0/24"}])
    nodes, edges = build_topology(inventory, neighbor_relationships=records)
    edge = next(edge for edge in edges if edge["relation"] == "lldp_neighbor")
    assert edge["confidence"] == "verified"
    assert edge["source"] == "192.168.1.2"
    assert edge["target"] == "MAC:AA:BB:CC:DD:EE:02"


def test_cdp_and_trusted_mesh_controller_evidence_are_supported():
    from scripts.topology_evidence import prepare_verified_neighbor_edges
    records = pd.DataFrame([
        {"protocol": "cdp", "local_mac": "AA:BB:CC:DD:EE:01", "neighbor_mac": "AA:BB:CC:DD:EE:02", "verification_status": "verified", "evidence_type": "cdp_neighbor_advertisement"},
        {"protocol": "mesh_controller", "local_mac": "AA:BB:CC:DD:EE:02", "neighbor_mac": "AA:BB:CC:DD:EE:03", "verification_status": "verified", "evidence_type": "controller_verified_mesh_relationship", "source_trust": "trusted"},
    ])
    assert [row["relation"] for row in prepare_verified_neighbor_edges(records)] == ["cdp_neighbor", "mesh_peer"]


def test_unverified_untrusted_or_invalid_neighbor_records_are_rejected():
    from scripts.topology_evidence import prepare_verified_neighbor_edges
    records = pd.DataFrame([
        {"protocol": "lldp", "local_mac": "AA:BB:CC:DD:EE:01", "neighbor_mac": "AA:BB:CC:DD:EE:02", "verification_status": "inferred", "evidence_type": "lldp_neighbor_advertisement"},
        {"protocol": "mesh_controller", "local_mac": "AA:BB:CC:DD:EE:01", "neighbor_mac": "AA:BB:CC:DD:EE:02", "verification_status": "verified", "evidence_type": "controller_verified_mesh_relationship", "source_trust": "unknown"},
        {"protocol": "guess", "local_mac": "AA:BB:CC:DD:EE:01", "neighbor_mac": "AA:BB:CC:DD:EE:02", "verification_status": "verified", "evidence_type": "lldp_neighbor_advertisement"},
        {"protocol": "lldp", "local_mac": "bad", "neighbor_mac": "AA:BB:CC:DD:EE:02", "verification_status": "verified", "evidence_type": "lldp_neighbor_advertisement"},
    ])
    assert prepare_verified_neighbor_edges(records) == []


def test_topology_ui_assigns_physical_ap_and_neighbor_lanes():
    from scripts.topology_evidence import topology_node_lane
    assert topology_node_lane("access_point_device")[0] == "Fiziksel erişim noktası"
    assert topology_node_lane("access_point_radio")[0] == "AP radyosu"
    assert topology_node_lane("network_neighbor")[0] == "Switch / Mesh komşusu"
    assert topology_node_lane("endpoint")[0] == "Uç cihaz"
    assert topology_node_lane("unrecognized")[0] == "Diğer / sınıflandırılmamış"
