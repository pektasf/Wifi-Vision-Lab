from scripts.discovery.dhcp_lease_analysis import analyze_dhcp_lease_windows


def lease(mac, start, seconds=3600, server="192.168.1.1", scope="192.168.1.0/24",
          ip="192.168.1.50", duration="1", messages="DISCOVER;OFFER;REQUEST;ACK"):
    return {
        "observed_at": start,
        "server_ip": server,
        "assigned_ip": ip,
        "mac": mac,
        "network_id": scope,
        "lease_time_seconds": str(seconds),
        "duration_seconds": duration,
        "message_types": messages,
    }


def test_lease_window_uses_transaction_end_as_estimated_start_and_expiry():
    rows = analyze_dhcp_lease_windows([
        lease("00:11:22:33:44:55", "2026-11-26T10:00:00Z", seconds=3600, duration="2.5")
    ])
    row = rows[0]
    assert row["lease_start_estimate"] == "2026-11-26T10:00:02.500000Z"
    assert row["lease_expiry_estimate"] == "2026-11-26T11:00:02.500000Z"
    assert row["lease_window_seconds"] == "3600"
    assert row["lease_timing_quality"] == "transaction_end_estimate"
    assert row["lease_analysis"] == "Kira penceresi hesaplandı"


def test_different_macs_with_overlapping_leases_same_scope_are_review_candidates():
    rows = analyze_dhcp_lease_windows([
        lease("00:11:22:33:44:55", "2026-11-26T10:00:00Z"),
        lease("00:11:22:33:44:66", "2026-11-26T10:30:00Z"),
    ])
    assert rows[1]["lease_analysis"] == "Çakışan kira adayı · ağ kapsamı doğrulandı"
    assert rows[1]["lease_related_observation"] == "00:11:22:33:44:55"


def test_different_macs_with_sequential_non_overlapping_leases_are_normal_reuse():
    rows = analyze_dhcp_lease_windows([
        lease("00:11:22:33:44:55", "2026-11-26T10:00:00Z", seconds=3600),
        lease("00:11:22:33:44:66", "2026-11-26T11:00:01Z", seconds=3600),
    ])
    assert rows[1]["lease_analysis"] == (
        "Önceki farklı MAC kirası sona ermiş · sıralı yeniden kullanım"
    )


def test_different_explicit_network_scopes_are_never_compared():
    rows = analyze_dhcp_lease_windows([
        lease("00:11:22:33:44:55", "2026-11-26T10:00:00Z", scope="192.168.1.0/24"),
        lease("00:11:22:33:44:66", "2026-11-26T10:30:00Z", scope="192.168.2.0/24"),
    ])
    assert rows[1]["lease_analysis"] == "Kira penceresi hesaplandı"


def test_overlapping_leases_without_scope_are_downgraded_to_possible_candidate():
    rows = analyze_dhcp_lease_windows([
        lease("00:11:22:33:44:55", "2026-11-26T10:00:00Z", scope=""),
        lease("00:11:22:33:44:66", "2026-11-26T10:30:00Z", scope=""),
    ])
    assert rows[1]["lease_analysis"] == "Olası çakışma · ağ kapsamı bilinmiyor"


def test_unknown_scope_does_not_turn_different_server_leases_into_conflicts():
    rows = analyze_dhcp_lease_windows([
        lease("00:11:22:33:44:55", "2026-11-26T10:00:00Z", scope="", server="192.168.1.1"),
        lease("00:11:22:33:44:66", "2026-11-26T10:30:00Z", scope="", server="192.168.2.1"),
    ])
    assert rows[1]["lease_analysis"] == "Kira penceresi hesaplandı"


def test_same_mac_renewal_is_not_reported_as_identity_conflict():
    rows = analyze_dhcp_lease_windows([
        lease("00:11:22:33:44:55", "2026-11-26T10:00:00Z", seconds=3600),
        lease("00:11:22:33:44:55", "2026-11-26T10:30:00Z", seconds=3600),
    ])
    assert rows[1]["lease_analysis"] == "Kira penceresi hesaplandı"


def test_ack_and_lease_fields_are_required_before_estimating_window():
    no_ack = lease("00:11:22:33:44:55", "2026-11-26T10:00:00Z", messages="DISCOVER;OFFER")
    no_ack_row = analyze_dhcp_lease_windows([no_ack])[0]
    assert no_ack_row["lease_analysis"] == "ACK yok · kira başlangıcı doğrulanamadı"
    assert no_ack_row["lease_expiry_estimate"] == ""

    no_lease = lease("00:11:22:33:44:55", "2026-11-26T10:00:00Z", seconds="")
    no_lease_row = analyze_dhcp_lease_windows([no_lease])[0]
    assert no_lease_row["lease_analysis"] == "Geçerli kira süresi yok"


def test_missing_mac_or_server_keeps_window_but_skips_comparison():
    row = lease("", "2026-11-26T10:00:00Z")
    row["server_ip"] = ""
    result = analyze_dhcp_lease_windows([row])[0]
    assert result["lease_expiry_estimate"] == "2026-11-26T11:00:01.000000Z"
    assert result["lease_analysis"] == "Kira hesaplandı · sunucu veya MAC eksik"


def test_invalid_timestamp_and_non_finite_lease_values_are_not_estimated():
    bad_time = lease("00:11:22:33:44:55", "not-a-time")
    bad_lease = lease("00:11:22:33:44:66", "2026-11-26T10:00:00Z", seconds="nan")
    rows = analyze_dhcp_lease_windows([bad_time, bad_lease])
    assert rows[0]["lease_analysis"] == "Geçerli zaman damgası yok"
    assert rows[1]["lease_analysis"] == "Geçerli kira süresi yok"



def test_reuse_after_unknown_scope_is_not_labeled_as_confirmed_same_scope():
    rows = analyze_dhcp_lease_windows([
        lease("00:11:22:33:44:55", "2026-11-26T10:00:00Z", seconds=3600, scope=""),
        lease("00:11:22:33:44:66", "2026-11-26T11:00:01Z", seconds=3600,
              scope="192.168.1.0/24"),
    ])
    assert rows[1]["lease_analysis"] == (
        "Farklı MAC sonrası yeniden kullanım · ağ kapsamı bilinmiyor"
    )


def test_missing_transaction_duration_uses_lower_precision_start_estimate():
    row = lease("00:11:22:33:44:55", "2026-11-26T10:00:00+03:00", duration="")
    result = analyze_dhcp_lease_windows([row])[0]
    assert result["lease_start_estimate"] == "2026-11-26T07:00:00.000000Z"
    assert result["lease_timing_quality"] == "first_message_estimate"


def test_extreme_lease_duration_is_rejected_without_datetime_overflow():
    row = lease("00:11:22:33:44:55", "2026-11-26T10:00:00Z", seconds="999999999999")
    result = analyze_dhcp_lease_windows([row])[0]
    assert result["lease_analysis"] == "Geçerli kira süresi yok"
    assert result["lease_expiry_estimate"] == ""



def test_explicit_zeek_import_scope_enables_same_network_lease_comparison():
    import json
    from scripts.discovery.zeek_import import normalize_zeek_dhcp_export

    records = [
        {
            "ts": "2026-11-26T10:00:00Z",
            "duration": 1,
            "server_addr": "192.168.1.1",
            "assigned_addr": "192.168.1.50",
            "mac": "00:11:22:33:44:55",
            "lease_time": 3600,
            "msg_types": ["DISCOVER", "OFFER", "REQUEST", "ACK"],
        },
        {
            "ts": "2026-11-26T10:30:00Z",
            "duration": 1,
            "server_addr": "192.168.1.1",
            "assigned_addr": "192.168.1.50",
            "mac": "00:11:22:33:44:66",
            "lease_time": 3600,
            "msg_types": ["DISCOVER", "OFFER", "REQUEST", "ACK"],
        },
    ]
    imported = normalize_zeek_dhcp_export(
        json.dumps(records), network_id="192.168.1.0/24"
    )
    results = analyze_dhcp_lease_windows(imported)
    assert all(row["network_id"] == "192.168.1.0/24" for row in results)
    assert results[1]["lease_analysis"] == (
        "Çakışan kira adayı · ağ kapsamı doğrulandı"
    )
