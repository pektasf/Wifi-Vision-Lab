from scripts.discovery.engine import build_device_profiles, build_inventory_rows


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
