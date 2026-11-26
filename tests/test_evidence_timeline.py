from scripts.discovery.evidence_timeline import (\n    build_identity_evidence_timeline, build_inventory_identity_index,\n    correlate_inventory_observation,\n)


def test_timeline_prefers_exact_mac_over_conflicting_ip_match():
    inventory = [
        {
            "mac": "00:11:22:33:44:55",
            "ip": "192.168.1.10",
            "identity_assessment": "no_indicator_observed",
        },
        {
            "mac": "00:11:22:33:44:66",
            "ip": "192.168.1.20",
            "identity_assessment": "indicator",
            "identity_signals": "locally_administered_mac",
        },
    ]
    rows = build_identity_evidence_timeline(
        inventory=inventory,
        nmap_observations=[{
            "observed_at": "2026-11-26T10:00:00Z",
            "mac": "00:11:22:33:44:66",
            "ip": "192.168.1.10",
            "evidence_status": "nmap_arp_response",
        }],
    )

    assert len(rows) == 1
    assert rows[0]["correlation_method"] == "exact_mac"
    assert rows[0]["inventory_match_count"] == 1
    assert rows[0]["inventory_identity_assessment"] == "indicator"
    assert rows[0]["inventory_identity_signals"] == "locally_administered_mac"


def test_timeline_marks_ip_only_match_as_weaker_correlation_when_scope_matches():
    rows = build_identity_evidence_timeline(
        inventory=[{
            "ip": "192.168.1.10", "mac": "00:11:22:33:44:55",
            "subnet": "192.168.1.0/24",
        }],
        local_observations=[{
            "observed_at": "2026-11-26T10:00:00Z",
            "network_id": "192.168.1.0/24",
            "ip": "192.168.1.10",
            "mac": "",
            "evidence_status": "host_up",
        }],
    )
    assert rows[0]["correlation_method"] == "exact_ip"
    assert rows[0]["inventory_match_count"] == 1


def test_timeline_does_not_ip_match_when_network_scope_is_missing():
    rows = build_identity_evidence_timeline(
        inventory=[{"ip": "192.168.1.10", "mac": "00:11:22:33:44:55"}],
        nmap_observations=[{
            "observed_at": "2026-11-26T10:00:00Z",
            "ip": "192.168.1.10",
            "mac": "",
            "evidence_status": "nmap_host_up",
        }],
    )
    assert rows[0]["correlation_method"] == "ip_scope_unknown"
    assert rows[0]["inventory_match_count"] == 0


def test_timeline_does_not_ip_match_across_different_networks():
    rows = build_identity_evidence_timeline(
        inventory=[{
            "ip": "192.168.1.10", "mac": "00:11:22:33:44:55",
            "subnet": "192.168.1.0/24",
        }],
        local_observations=[{
            "network_id": "192.168.2.0/24",
            "ip": "192.168.1.10",
            "mac": "",
        }],
    )
    assert rows[0]["correlation_method"] == "network_mismatch"
    assert rows[0]["inventory_match_count"] == 0


def test_timeline_rejects_exact_mac_match_when_explicit_networks_conflict():
    rows = build_identity_evidence_timeline(
        inventory=[{
            "ip": "10.0.0.20", "mac": "00:11:22:33:44:55",
            "subnet": "10.0.0.0/24",
        }],
        local_observations=[{
            "network_id": "192.168.1.0/24",
            "ip": "192.168.1.20",
            "mac": "00:11:22:33:44:55",
        }],
    )
    assert rows[0]["correlation_method"] == "network_mismatch"
    assert rows[0]["inventory_match_count"] == 0


def test_timeline_allows_exact_mac_match_when_scope_is_unavailable():
    rows = build_identity_evidence_timeline(
        inventory=[{"mac": "00:11:22:33:44:55", "ip": "192.168.1.10"}],
        nmap_observations=[{
            "mac": "00:11:22:33:44:55",
            "ip": "192.168.1.10",
        }],
    )
    assert rows[0]["correlation_method"] == "exact_mac"


def test_timeline_flags_kismet_randomized_mac_without_merging_identity():
    rows = build_identity_evidence_timeline(
        wireless_observations=[
            {
                "observed_at": "2026-11-26T10:00:00Z",
                "mac": "02:11:22:33:44:55",
                "randomized_mac": "true",
                "evidence_status": "kismet_reported_randomized",
            },
            {
                "observed_at": "2026-11-26T10:01:00Z",
                "mac": "02:11:22:33:44:66",
                "randomized_mac": "true",
                "evidence_status": "kismet_reported_randomized",
            },
        ],
    )
    assert len(rows) == 2
    assert rows[0]["identity_indicator"] == "Kismet randomized MAC"
    assert rows[1]["identity_indicator"] == "Kismet randomized MAC"
    assert rows[0]["event_id"] != rows[1]["event_id"]
    assert all(row["correlation_method"] == "unmatched" for row in rows)


def test_timeline_keeps_all_source_observations_separate():
    rows = build_identity_evidence_timeline(
        local_observations=[{
            "observed_at": "2026-11-26T10:00:00Z",
            "mac": "00:11:22:33:44:55",
            "ip": "192.168.1.10",
            "source": "windows_local",
            "evidence": "icmp_echo_reply",
        }],
        endpoint_observations=[{
            "observed_at": "2026-11-26T10:01:00Z",
            "endpoint_mac": "00:11:22:33:44:55",
            "endpoint_ip": "192.168.1.10",
            "adapter_kind": "virtual_wlan",
            "evidence_status": "endpoint_reported",
        }],
        wireless_observations=[{
            "observed_at": "2026-11-26T10:02:00Z",
            "mac": "00:11:22:33:44:55",
            "evidence_status": "kismet_imported",
        }],
        nmap_observations=[{
            "observed_at": "2026-11-26T10:03:00Z",
            "mac": "00:11:22:33:44:55",
            "ip": "192.168.1.10",
            "evidence_status": "nmap_arp_response",
        }],
        zeek_observations=[{
            "observed_at": "2026-11-26T10:04:00Z",
            "mac": "00:11:22:33:44:55",
            "assigned_ip": "192.168.1.10",
            "evidence_status": "dhcp_assigned_address",
        }],
    )

    assert len(rows) == 5
    assert {row["source"] for row in rows} == {
        "Windows keşif", "Yetkili endpoint", "Kismet Wi-Fi",
        "Nmap host keşfi", "Zeek DHCP",
    }
    assert rows[0]["source"] == "Zeek DHCP"
    assert all(row["correlation_method"] == "unmatched" for row in rows)


def test_timeline_returns_newest_events_first_and_respects_limit():
    rows = build_identity_evidence_timeline(
        nmap_observations=[
            {"observed_at": "2026-11-26T10:00:00Z", "ip": "192.168.1.10"},
            {"observed_at": "2026-11-26T10:01:00Z", "ip": "192.168.1.11"},
            {"observed_at": "2026-11-26T10:02:00Z", "ip": "192.168.1.12"},
        ],
        limit=2,
    )
    assert len(rows) == 2
    assert rows[0]["observed_at"] == "2026-11-26T10:02:00Z"
    assert rows[1]["observed_at"] == "2026-11-26T10:01:00Z"


def test_timeline_ignores_observations_without_ip_or_mac():
    rows = build_identity_evidence_timeline(
        zeek_observations=[{"hostname": "only-hostname"}],
    )
    assert rows == []


def test_timeline_sorts_timestamps_by_instant_not_timezone_string():
    rows = build_identity_evidence_timeline(
        nmap_observations=[
            {
                "observed_at": "2026-11-26T09:30:00+03:00",
                "ip": "192.168.1.10",
            },
            {
                "observed_at": "2026-11-26T07:00:00Z",
                "ip": "192.168.1.11",
            },
        ],
    )
    assert rows[0]["ip"] == "192.168.1.11"
    assert rows[1]["ip"] == "192.168.1.10"



def test_shared_inventory_matcher_rejects_ip_only_match_without_scope():
    index = build_inventory_identity_index([{
        "ip": "192.168.1.10", "mac": "00:11:22:33:44:55",
        "subnet": "192.168.1.0/24",
    }])
    method, matches = correlate_inventory_observation(
        {"assigned_ip": "192.168.1.10"}, index,
        mac_value="", ip_value="192.168.1.10",
    )
    assert method == "ip_scope_unknown"
    assert matches == []


def test_shared_inventory_matcher_allows_exact_mac_without_network_scope():
    index = build_inventory_identity_index([{
        "ip": "192.168.1.10", "mac": "00:11:22:33:44:55",
        "subnet": "192.168.1.0/24",
    }])
    method, matches = correlate_inventory_observation(
        {"endpoint_ip": "192.168.1.10"}, index,
        mac_value="00:11:22:33:44:55", ip_value="192.168.1.10",
    )
    assert method == "exact_mac"
    assert len(matches) == 1


def test_shared_inventory_matcher_uses_ip_only_with_equal_explicit_scope():
    index = build_inventory_identity_index([{
        "ip": "192.168.1.10", "mac": "00:11:22:33:44:55",
        "subnet": "192.168.1.0/24",
    }])
    method, matches = correlate_inventory_observation(
        {"network_id": "192.168.1.0/24"}, index,
        mac_value="", ip_value="192.168.1.10",
    )
    assert method == "exact_ip"
    assert len(matches) == 1
