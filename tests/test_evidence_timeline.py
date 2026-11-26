from scripts.discovery.evidence_timeline import build_identity_evidence_timeline


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


def test_timeline_marks_ip_only_match_as_weaker_correlation():
    rows = build_identity_evidence_timeline(
        inventory=[{"ip": "192.168.1.10", "mac": "00:11:22:33:44:55"}],
        nmap_observations=[{
            "observed_at": "2026-11-26T10:00:00Z",
            "ip": "192.168.1.10",
            "mac": "",
            "evidence_status": "nmap_host_up",
        }],
    )
    assert rows[0]["correlation_method"] == "exact_ip"


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
