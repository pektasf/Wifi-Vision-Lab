from scripts.discovery.engine import (
    build_device_profiles, build_inventory_rows, classify_observation_evidence
)


def test_profiles_merge_same_mac_across_sources_and_ips():
    observations = [
        {
            "network_id": "192.168.1.0/24",
            "mac": "AA:BB:CC:DD:EE:FF",
            "ip": "192.168.1.10",
            "hostname": "device-a",
            "source": "ping",
            "status": "responding",
            "observed_at": "2026-01-01T10:00:00+00:00",
        },
        {
            "network_id": "192.168.1.0/24",
            "mac": "AA:BB:CC:DD:EE:FF",
            "ip": "192.168.1.11",
            "hostname": "device-a.local",
            "source": "arp",
            "status": "arp_seen",
            "observed_at": "2026-01-01T10:01:00+00:00",
        },
    ]

    profiles = build_device_profiles(observations)

    assert len(profiles) == 1
    profile = profiles[0]
    assert profile["identity_basis"] == "mac"
    assert profile["mac"] == "AA:BB:CC:DD:EE:FF"
    assert profile["ips"] == "192.168.1.10;192.168.1.11"
    assert profile["source_count"] == 2
    assert profile["sources"] == "arp;ping"
    assert profile["last_seen"] == "2026-01-01T10:01:00+00:00"


def test_ip_fallback_is_scoped_to_network():
    observations = [
        {"network_id": "192.168.1.0/24", "ip": "192.168.1.20"},
        {"network_id": "192.168.2.0/24", "ip": "192.168.1.20"},
    ]

    profiles = build_device_profiles(observations)

    assert len(profiles) == 2
    assert {p["identity_basis"] for p in profiles} == {"network_ip"}
    assert len({p["device_id"] for p in profiles}) == 2


def test_observation_without_mac_and_ip_is_ignored():
    assert build_device_profiles([{"network_id": "192.168.1.0/24"}]) == []


def test_inventory_contains_one_row_per_profile():
    observations = [
        {
            "network_id": "10.0.0.0/24",
            "mac": "00:11:22:33:44:55",
            "ip": "10.0.0.8",
            "hostname": "host-a",
            "status": "responding",
            "gateway": "10.0.0.1",
            "adapter": "Wi-Fi",
            "observed_at": "2026-01-01T10:00:00+00:00",
        },
        {
            "network_id": "10.0.0.0/24",
            "mac": "00:11:22:33:44:55",
            "ip": "10.0.0.9",
            "hostname": "host-a.local",
            "status": "arp_seen",
            "gateway": "10.0.0.1",
            "adapter": "Wi-Fi",
            "observed_at": "2026-01-01T10:01:00+00:00",
        },
    ]

    profiles = build_device_profiles(observations)
    rows = build_inventory_rows(observations, profiles)

    assert len(rows) == 1
    assert rows[0]["mac"] == "00:11:22:33:44:55"
    assert rows[0]["subnet"] == "10.0.0.0/24"
    assert rows[0]["gateway"] == "10.0.0.1"
    assert rows[0]["status"] == "arp_seen;responding"



def test_ip_only_observation_joins_single_matching_mac_profile():
    observations = [
        {
            "network_id": "192.168.10.0/24",
            "ip": "192.168.10.25",
            "mac": "AA:BB:CC:DD:EE:FF",
            "source": "arp",
            "status": "arp_seen",
            "observed_at": "2026-11-26T10:00:00+03:00",
        },
        {
            "network_id": "192.168.10.0/24",
            "ip": "192.168.10.25",
            "mac": "",
            "hostname": "device.local",
            "source": "ping",
            "status": "responding",
            "observed_at": "2026-11-26T10:01:00+03:00",
        },
    ]

    profiles = build_device_profiles(observations)
    inventory = build_inventory_rows(observations, profiles)

    assert len(profiles) == 1
    assert profiles[0]["identity_basis"] == "mac"
    assert profiles[0]["mac"] == "AA:BB:CC:DD:EE:FF"
    assert profiles[0]["sources"] == "arp;ping"
    assert profiles[0]["statuses"] == "arp_seen;responding"
    assert len(inventory) == 1
    assert inventory[0]["mac"] == "AA:BB:CC:DD:EE:FF"
    assert inventory[0]["hostname"] == "device.local"


def test_ip_only_observation_is_not_joined_when_ip_maps_to_multiple_macs():
    observations = [
        {
            "network_id": "192.168.10.0/24",
            "ip": "192.168.10.25",
            "mac": "AA:BB:CC:DD:EE:01",
            "source": "arp_a",
        },
        {
            "network_id": "192.168.10.0/24",
            "ip": "192.168.10.25",
            "mac": "AA:BB:CC:DD:EE:02",
            "source": "arp_b",
        },
        {
            "network_id": "192.168.10.0/24",
            "ip": "192.168.10.25",
            "mac": "",
            "source": "ping",
        },
    ]

    profiles = build_device_profiles(observations)

    assert len(profiles) == 3
    assert sum(profile["identity_basis"] == "mac" for profile in profiles) == 2
    assert sum(profile["identity_basis"] == "network_ip" for profile in profiles) == 1


def test_ip_only_observation_does_not_join_mac_from_another_network():
    observations = [
        {
            "network_id": "192.168.10.0/24",
            "ip": "192.168.10.25",
            "mac": "AA:BB:CC:DD:EE:FF",
            "source": "arp",
        },
        {
            "network_id": "192.168.20.0/24",
            "ip": "192.168.10.25",
            "mac": "",
            "source": "ping",
        },
    ]

    profiles = build_device_profiles(observations)

    assert len(profiles) == 2
    assert {profile["identity_basis"] for profile in profiles} == {
        "mac", "network_ip"
    }



def test_discovery_evidence_labels_distinguish_ping_and_arp_sources():
    assert classify_observation_evidence("windows_local", "responding") == (
        "icmp_echo_reply"
    )
    assert classify_observation_evidence(
        "windows_local", "responding", "AA:BB:CC:DD:EE:FF"
    ) == "arp_cache_entry;icmp_echo_reply"
    assert classify_observation_evidence("windows_local", "arp_seen") == (
        "arp_cache_entry"
    )
    assert classify_observation_evidence("windows_arp_cache", "arp_cache") == (
        "arp_cache_entry"
    )
    assert classify_observation_evidence("future_adapter", "unknown") == (
        "adapter_reported_observation"
    )


def test_device_profile_aggregates_distinct_evidence_types():
    observations = [
        {
            "network_id": "192.168.30.0/24",
            "ip": "192.168.30.10",
            "mac": "00:11:22:33:44:55",
            "source": "windows_local",
            "status": "responding",
        },
        {
            "network_id": "192.168.30.0/24",
            "ip": "192.168.30.10",
            "mac": "00:11:22:33:44:55",
            "source": "windows_arp_cache",
            "status": "arp_cache",
        },
    ]

    profiles = build_device_profiles(observations)

    assert len(profiles) == 1
    assert profiles[0]["evidence_types"] == (
        "arp_cache_entry;icmp_echo_reply"
    )



def test_locally_administered_mac_is_reported_as_indicator_not_confirmed_spoofing():
    from scripts.discovery.identity_signals import (
        analyze_identity_variation, is_locally_administered_mac,
    )
    assert is_locally_administered_mac("02:11:22:33:44:55")
    assert not is_locally_administered_mac("00:11:22:33:44:55")
    result = analyze_identity_variation([{
        "network_id": "192.168.1.0/24",
        "ip": "192.168.1.22",
        "mac": "02:11:22:33:44:55",
    }])
    item = result["192.168.1.0/24|mac|02:11:22:33:44:55"]
    assert item["identity_assessment"] == "indicator"
    assert item["identity_signals"] == "locally_administered_mac"


def test_mac_rotation_for_same_ip_is_flagged_for_review():
    from scripts.discovery.identity_signals import analyze_identity_variation
    history = [{
        "network_id": "192.168.1.0/24", "ip": "192.168.1.30",
        "mac": "00:11:22:33:44:55", "hostname": "phone-a",
    }]
    current = [{
        "network_id": "192.168.1.0/24", "ip": "192.168.1.30",
        "mac": "02:AA:BB:CC:DD:EE", "hostname": "phone-a",
    }]
    result = analyze_identity_variation(current, history)
    item = result["192.168.1.0/24|mac|02:AA:BB:CC:DD:EE"]
    assert item["identity_assessment"] == "review"
    assert "ip_mac_changed_over_time" in item["identity_signals"]
    assert "hostname_seen_with_multiple_macs" in item["identity_signals"]


def test_multiple_macs_claiming_same_ip_in_one_scan_are_flagged():
    from scripts.discovery.identity_signals import analyze_identity_variation
    rows = [
        {"network_id": "192.168.1.0/24", "ip": "192.168.1.40", "mac": "00:11:22:33:44:55"},
        {"network_id": "192.168.1.0/24", "ip": "192.168.1.40", "mac": "00:11:22:33:44:66"},
    ]
    result = analyze_identity_variation(rows)
    assert all(value["identity_assessment"] == "review" for value in result.values())
    assert all("same_ip_multiple_macs" in value["identity_signals"] for value in result.values())


def test_missing_mac_is_reported_without_inventing_identity():
    from scripts.discovery.identity_signals import analyze_identity_variation
    result = analyze_identity_variation([{
        "network_id": "192.168.1.0/24", "ip": "192.168.1.50", "mac": "",
    }])
    item = result["192.168.1.0/24|ip|192.168.1.50"]
    assert item["identity_assessment"] == "indicator"
    assert item["identity_signals"] == "mac_not_observed"


def test_profile_and_inventory_include_identity_signals():
    observations = [{
        "network_id": "192.168.1.0/24", "ip": "192.168.1.60",
        "mac": "02:11:22:33:44:55", "source": "arp",
        "observed_at": "2026-11-26T10:00:00+03:00",
    }]
    profiles = build_device_profiles(observations)
    inventory = build_inventory_rows(observations, profiles)
    assert profiles[0]["identity_assessment"] == "indicator"
    assert "locally_administered_mac" in profiles[0]["identity_signals"]
    assert inventory[0]["identity_assessment"] == "indicator"



def test_identity_history_is_bounded_and_deduplicated(tmp_path):
    from scripts.discovery.identity_signals import (
        load_identity_history, save_identity_history,
    )
    path = tmp_path / "identity_history.csv"
    rows = [{
        "observed_at": "2026-11-26T10:00:00+03:00",
        "network_id": "192.168.1.0/24",
        "ip": "192.168.1.20",
        "mac": "02:11:22:33:44:55",
        "hostname": "phone",
        "source": "windows_arp_cache",
    }]
    saved = save_identity_history(rows, history=[], path=path)
    saved = save_identity_history(rows, history=saved, path=path)
    assert len(saved) == 1
    assert load_identity_history(path) == saved
