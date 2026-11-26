import warnings

import pandas as pd

from scripts.event_timeline import normalize_event_frames


def test_normalizes_supported_event_sources_and_sorts_newest_first():
    frames = {
        "device_events.csv": pd.DataFrame([{
            "event_time": "2026-01-01T10:00:00+03:00",
            "identity_key": "AA:BB",
            "event_type": "ip_changed",
            "old_value": "192.168.1.2",
            "new_value": "192.168.1.3",
            "details": "IP updated",
        }]),
        "live_events.csv": pd.DataFrame([{
            "timestamp": "2026-01-01T08:30:00Z",
            "ip": "192.168.1.4",
            "event": "PING_NOT_RESPONDING",
        }]),
        "behavior_findings.csv": pd.DataFrame([{
            "timestamp": "invalid",
            "subject": "AA:CC",
            "type": "MULTIPLE_IPS_SAME_MAC",
            "severity": "review",
            "detail": "Needs review",
        }]),
    }

    result = normalize_event_frames(frames)

    assert result["event_type"].tolist() == [
        "PING_NOT_RESPONDING",
        "ip_changed",
        "MULTIPLE_IPS_SAME_MAC",
    ]
    assert result.iloc[0]["source"] == "Canlı izleme"
    assert result.iloc[1]["subject"] == "AA:BB"
    assert result.iloc[1]["old_value"] == "192.168.1.2"
    assert result.iloc[2]["severity"] == "review"
    assert "_parsed_time" not in result.columns


def test_normalizer_keeps_missing_dates_last_without_parse_warnings():
    frame = pd.DataFrame([
        {"timestamp": "bad", "ip": "first", "event": "unknown"},
        {"timestamp": "2026-02-01T10:00:00Z", "ip": "newer", "event": "up"},
        {"timestamp": "2026-02-01T11:00:00+01:00", "ip": "same-instant", "event": "up"},
        {"timestamp": "bad", "ip": "second", "event": "unknown"},
    ])

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        result = normalize_event_frames({"network_events.csv": frame})

    assert result["subject"].tolist() == [
        "newer", "same-instant", "first", "second"
    ]
    assert captured == []


def test_empty_event_sources_return_expected_columns():
    result = normalize_event_frames({
        "device_events.csv": pd.DataFrame(),
        "network_events.csv": pd.DataFrame(),
    })

    assert result.empty
    assert result.columns.tolist() == [
        "event_time", "event_type", "subject", "identity_key", "ip", "severity",
        "old_value", "new_value", "details", "source",
    ]


def test_known_event_types_receive_inferred_severity_and_explicit_value_wins():
    frames = {
        "device_events.csv": pd.DataFrame([
            {"event_time": "2026-03-01T10:00:00Z", "event_type": "ip_changed"},
            {"event_time": "2026-03-01T09:00:00Z", "event_type": "new_device"},
            {"event_time": "2026-03-01T08:00:00Z", "event_type": "ping_not_responding", "severity": "critical"},
        ]),
        "network_events.csv": pd.DataFrame([
            {"timestamp": "2026-03-01T07:00:00Z", "event": "NOT_IN_LATEST_SCAN", "ip": "192.168.1.2"},
        ]),
        "behavior_findings.csv": pd.DataFrame([
            {"timestamp": "2026-03-01T06:00:00Z", "type": "MULTIPLE_IPS_SAME_MAC"},
        ]),
    }

    result = normalize_event_frames(frames)

    assert result["severity"].tolist() == [
        "warning", "info", "critical", "warning", "review"
    ]


def test_severity_mapping_matches_event_names_emitted_by_project_modules():
    frames = {
        "device_events.csv": pd.DataFrame([
            {"event_time": "2026-03-02T12:00:00Z", "event_type": "new_device"},
            {"event_time": "2026-03-02T11:00:00Z", "event_type": "seen_again"},
            {"event_time": "2026-03-02T10:00:00Z", "event_type": "baseline_snapshot"},
            {"event_time": "2026-03-02T09:00:00Z", "event_type": "ip_changed"},
        ]),
        "network_events.csv": pd.DataFrame([
            {"timestamp": "2026-03-02T08:00:00Z", "event": "FIRST_OBSERVED"},
            {"timestamp": "2026-03-02T07:00:00Z", "event": "NOT_IN_LATEST_SCAN"},
            {"timestamp": "2026-03-02T06:00:00Z", "event": "IP_CHANGED"},
        ]),
        "live_events.csv": pd.DataFrame([
            {"timestamp": "2026-03-02T05:00:00Z", "event": "PING_RESPONDING"},
            {"timestamp": "2026-03-02T04:00:00Z", "event": "PING_NOT_RESPONDING"},
        ]),
    }

    result = normalize_event_frames(frames)
    severity_by_type = dict(zip(result["event_type"], result["severity"]))

    assert severity_by_type == {
        "new_device": "info",
        "seen_again": "info",
        "baseline_snapshot": "info",
        "ip_changed": "warning",
        "FIRST_OBSERVED": "info",
        "NOT_IN_LATEST_SCAN": "warning",
        "IP_CHANGED": "warning",
        "PING_RESPONDING": "info",
        "PING_NOT_RESPONDING": "warning",
    }



def test_summarize_event_severity_counts_known_and_custom_levels():
    from scripts.event_timeline import summarize_event_severity

    frame = pd.DataFrame({
        "severity": ["warning", "warning", "critical", "review", "info", "custom", None, ""]
    })

    assert summarize_event_severity(frame) == {
        "warning": 2,
        "critical": 1,
        "review": 1,
        "info": 1,
        "custom": 1,
    }


def test_summarize_event_severity_handles_empty_or_missing_column():
    from scripts.event_timeline import summarize_event_severity

    assert summarize_event_severity(pd.DataFrame()) == {}
    assert summarize_event_severity(pd.DataFrame({"event_type": ["up"]})) == {}



def test_network_timeline_uses_stable_identity_and_ip_transition_values():
    result = normalize_event_frames({
        "network_events.csv": pd.DataFrame([{
            "timestamp": "2026-11-26T09:00:00+03:00",
            "event": "IP_CHANGED",
            "ip": "192.168.1.35",
            "identity_key": "AA:BB:CC:DD:EE:FF",
            "old_value": "192.168.1.20",
            "new_value": "192.168.1.35",
        }])
    })

    assert result.iloc[0]["subject"] == "AA:BB:CC:DD:EE:FF"
    assert result.iloc[0]["old_value"] == "192.168.1.20"
    assert result.iloc[0]["new_value"] == "192.168.1.35"



def test_live_ping_timeline_keeps_mac_identity_and_ip_separately():
    result = normalize_event_frames({
        "live_events.csv": pd.DataFrame([{
            "timestamp": "2026-11-26T09:00:00+03:00",
            "ip": "192.0.2.8",
            "event": "PING_NOT_RESPONDING",
            "identity_key": "AA:BB:CC:DD:EE:FF",
            "old_value": "responding",
            "new_value": "not_responding",
        }])
    })

    assert result.iloc[0]["subject"] == "AA:BB:CC:DD:EE:FF"
    assert result.iloc[0]["identity_key"] == "AA:BB:CC:DD:EE:FF"
    assert result.iloc[0]["ip"] == "192.0.2.8"
    assert result.iloc[0]["old_value"] == "responding"
    assert result.iloc[0]["new_value"] == "not_responding"



def test_filter_event_timeline_combines_exact_filters_and_literal_search():
    from scripts.event_timeline import filter_event_timeline

    frame = pd.DataFrame([
        {"event_type": "IP_CHANGED", "source": "Ağ olayları", "severity": "warning",
         "subject": "AA:BB:CC:DD:EE:01", "details": "Address changed"},
        {"event_type": "PING_NOT_RESPONDING", "source": "Canlı izleme", "severity": "warning",
         "subject": "AA:BB:CC:DD:EE:02", "details": "Ping timeout"},
        {"event_type": "IP_CHANGED", "source": "Ağ olayları", "severity": "review",
         "subject": "AA:BB:CC:DD:EE:03", "details": "Needs review"},
    ])

    result = filter_event_timeline(
        frame, search="AA:BB", source="Ağ olayları", severity="warning",
        event_type="IP_CHANGED",
    )

    assert len(result) == 1
    assert result.iloc[0]["subject"] == "AA:BB:CC:DD:EE:01"
    assert result.index.tolist() == [0]


def test_filter_event_timeline_search_treats_regex_characters_literally():
    from scripts.event_timeline import filter_event_timeline

    frame = pd.DataFrame([
        {"event_type": "IP_CHANGED", "details": "Address [192.0.2.1] changed"},
        {"event_type": "IP_CHANGED", "details": "Address 192x0x2x1 changed"},
    ])

    result = filter_event_timeline(frame, search="[192.0.2.1]")

    assert len(result) == 1
    assert result.iloc[0]["details"] == "Address [192.0.2.1] changed"


def test_filter_event_timeline_handles_missing_columns_and_empty_input():
    from scripts.event_timeline import filter_event_timeline

    frame = pd.DataFrame([{"event_type": "IP_CHANGED"}])

    assert filter_event_timeline(frame, source="Ağ olayları").empty
    assert filter_event_timeline(pd.DataFrame()).empty
    assert filter_event_timeline(None).empty


def test_related_event_context_correlates_same_stable_identity_across_ip_changes():
    from scripts.event_timeline import related_event_context

    frame = pd.DataFrame([
        {"event_time": "2026-11-26T09:00:00Z", "identity_key": "AA:01",
         "event_type": "ip_changed", "ip": "192.0.2.2"},
        {"event_time": "2026-11-26T08:52:00Z", "identity_key": "AA:01",
         "event_type": "ping_not_responding", "ip": "192.0.2.1"},
        {"event_time": "2026-11-26T08:40:00Z", "identity_key": "AA:01",
         "event_type": "seen_again", "ip": "192.0.2.2"},
        {"event_time": "2026-11-26T08:58:00Z", "identity_key": "AA:02",
         "event_type": "new_device", "ip": "192.0.2.8"},
    ])
    result = related_event_context(frame, frame.iloc[0], window_minutes=10)
    assert result["event_type"].tolist() == ["ip_changed", "ping_not_responding"]
    assert result["identity_key"].unique().tolist() == ["AA:01"]


def test_related_event_context_handles_invalid_times_and_missing_identity():
    from scripts.event_timeline import related_event_context

    frame = pd.DataFrame([
        {"event_time": "bad", "identity_key": "AA:01", "event_type": "bad_time"},
        {"event_time": "2026-11-26T09:00:00Z", "identity_key": "", "event_type": "legacy"},
    ])
    assert related_event_context(frame, frame.iloc[0]).empty
    assert related_event_context(frame, pd.Series({
        "event_time": "2026-11-26T09:00:00Z", "identity_key": ""
    })).empty


def test_related_event_context_returns_empty_when_required_fields_are_missing():
    from scripts.event_timeline import related_event_context

    frame = pd.DataFrame([{"event_time": "2026-11-26T09:00:00Z"}])
    selected = pd.Series({"event_time": "2026-11-26T09:00:00Z", "identity_key": "AA:01"})
    assert related_event_context(frame, selected).empty


def test_related_event_context_rejects_negative_or_invalid_window():
    import pytest
    from scripts.event_timeline import related_event_context

    frame = pd.DataFrame([{
        "event_time": "2026-11-26T09:00:00Z", "identity_key": "AA:01"
    }])
    with pytest.raises(ValueError):
        related_event_context(frame, frame.iloc[0], window_minutes=-1)
    with pytest.raises(ValueError):
        related_event_context(frame, frame.iloc[0], window_minutes="invalid")


def test_event_review_key_is_deterministic_and_uses_event_source_context():
    from scripts.event_timeline import event_review_key

    event = pd.Series({
        "source": "Canlı izleme", "event_time": "2026-11-26T09:00:00Z",
        "event_type": "PING_NOT_RESPONDING", "identity_key": "AA:01",
        "ip": "192.0.2.1", "details": "Ping timeout",
    })
    assert event_review_key(event) == event_review_key(event.to_dict())
    changed = event.copy()
    changed["source"] = "Ağ olayları"
    assert event_review_key(event) != event_review_key(changed)


def test_merge_event_review_states_preserves_notes_and_defaults_unknown_events():
    from scripts.event_timeline import merge_event_review_states, event_review_key

    events = pd.DataFrame([
        {"source": "Canlı izleme", "event_time": "2026-11-26T09:00:00Z",
         "event_type": "PING_NOT_RESPONDING", "identity_key": "AA:01"},
        {"source": "Ağ olayları", "event_time": "2026-11-26T08:00:00Z",
         "event_type": "IP_CHANGED", "identity_key": "AA:01"},
    ])
    states = pd.DataFrame([{
        "event_key": event_review_key(events.iloc[0]),
        "status": "action_required", "note": "Router tarafını kontrol et",
        "updated_at": "2026-11-26T09:10:00+03:00",
    }])
    result = merge_event_review_states(events, states)
    assert result["review_status"].tolist() == ["action_required", "new"]
    assert result.iloc[0]["review_note"] == "Router tarafını kontrol et"
    assert result.iloc[1]["review_note"] == ""


def test_upsert_event_review_state_updates_existing_record_without_duplicates():
    from scripts.event_timeline import upsert_event_review_state, event_review_key

    event = pd.Series({
        "source": "Canlı izleme", "event_time": "2026-11-26T09:00:00Z",
        "event_type": "PING_NOT_RESPONDING", "identity_key": "AA:01",
    })
    states = pd.DataFrame([{
        "event_key": event_review_key(event), "status": "reviewed",
        "note": "Old note", "updated_at": "old",
    }])
    result = upsert_event_review_state(
        states, event, "resolved", "Kontrol edildi", "2026-11-26T10:00:00Z"
    )
    assert len(result) == 1
    assert result.iloc[0]["status"] == "resolved"
    assert result.iloc[0]["note"] == "Kontrol edildi"


def test_upsert_event_review_state_rejects_unknown_status():
    import pytest
    from scripts.event_timeline import upsert_event_review_state

    with pytest.raises(ValueError):
        upsert_event_review_state(pd.DataFrame(), {"event_type": "test"}, "closed")


def test_merge_event_review_states_handles_empty_and_invalid_legacy_state():
    from scripts.event_timeline import merge_event_review_states

    events = pd.DataFrame([{
        "source": "Ağ olayları", "event_time": "2026-11-26T09:00:00Z",
        "event_type": "IP_CHANGED",
    }])
    assert merge_event_review_states(pd.DataFrame(), pd.DataFrame()).empty
    result = merge_event_review_states(events, pd.DataFrame([{
        "event_key": "wrong", "status": "unsupported", "note": "legacy",
    }]))
    assert result.iloc[0]["review_status"] == "new"


def test_filter_event_review_status_filters_only_selected_state():
    from scripts.event_timeline import filter_event_review_status

    frame = pd.DataFrame([
        {"event_type": "IP_CHANGED", "review_status": "new"},
        {"event_type": "PING_NOT_RESPONDING", "review_status": "action_required"},
        {"event_type": "seen_again", "review_status": "resolved"},
    ])
    result = filter_event_review_status(frame, "action_required")
    assert result["event_type"].tolist() == ["PING_NOT_RESPONDING"]


def test_filter_event_review_status_supports_all_and_safe_missing_data():
    from scripts.event_timeline import filter_event_review_status

    frame = pd.DataFrame([
        {"event_type": "IP_CHANGED", "review_status": "new"},
        {"event_type": "seen_again", "review_status": "resolved"},
    ])
    assert len(filter_event_review_status(frame, "all")) == 2
    assert len(filter_event_review_status(frame)) == 2
    assert filter_event_review_status(frame, "unknown").empty
    assert filter_event_review_status(pd.DataFrame([{"event_type": "legacy"}]), "new").empty
    assert filter_event_review_status(None, "new").empty


def test_filter_event_review_status_treats_missing_status_as_new():
    from scripts.event_timeline import filter_event_review_status

    frame = pd.DataFrame([
        {"event_type": "IP_CHANGED", "review_status": None},
        {"event_type": "seen_again", "review_status": "resolved"},
    ])
    result = filter_event_review_status(frame, "new")
    assert result["event_type"].tolist() == ["IP_CHANGED"]



def test_review_state_priority_and_assignee_round_trip_with_legacy_defaults():
    from scripts.event_timeline import (
        event_review_key, merge_event_review_states, upsert_event_review_state,
    )

    event = pd.Series({
        "source": "Ağ olayları", "event_time": "2026-11-26T09:00:00Z",
        "event_type": "IP_CHANGED", "identity_key": "AA:01",
    })
    key = event_review_key(event)
    legacy = pd.DataFrame([{
        "event_key": key, "status": "reviewed", "note": "Kontrol edildi",
        "updated_at": "2026-11-26T09:10:00Z",
    }])
    merged_legacy = merge_event_review_states(pd.DataFrame([event]), legacy)
    assert merged_legacy.iloc[0]["review_priority"] == "normal"
    assert merged_legacy.iloc[0]["review_assignee"] == ""

    updated = upsert_event_review_state(
        legacy, event, "action_required", "AP kontrolü", "2026-11-26T10:00:00Z",
        priority="high", assignee="Ağ ekibi",
    )
    assert len(updated) == 1
    merged = merge_event_review_states(pd.DataFrame([event]), updated)
    assert merged.iloc[0]["review_status"] == "action_required"
    assert merged.iloc[0]["review_priority"] == "high"
    assert merged.iloc[0]["review_assignee"] == "Ağ ekibi"


def test_review_state_rejects_unknown_priority():
    import pytest
    from scripts.event_timeline import upsert_event_review_state

    with pytest.raises(ValueError):
        upsert_event_review_state(pd.DataFrame(), {"event_type": "test"}, "new", priority="urgent")


def test_review_history_appends_only_changes_and_deduplicates_retries():
    from scripts.event_timeline import append_event_review_history, filter_event_review_history

    event = {
        "source": "Canlı izleme", "event_time": "2026-11-26T09:00:00Z",
        "event_type": "PING_NOT_RESPONDING", "identity_key": "AA:01",
    }
    previous = {"status": "new", "priority": "normal", "assignee": "", "note": ""}
    kwargs = {
        "status": "action_required", "priority": "high", "assignee": "Operatör",
        "note": "AP bağlantısını kontrol et", "updated_at": "2026-11-26T10:00:00Z",
    }
    history = append_event_review_history(pd.DataFrame(), event, previous, **kwargs)
    assert len(history) == 1
    assert '"priority"' in history.iloc[0]["changes"]

    retried = append_event_review_history(history, event, previous, **kwargs)
    assert len(retried) == 1

    unchanged = append_event_review_history(
        history, event,
        {"status": "action_required", "priority": "high", "assignee": "Operatör",
         "note": "AP bağlantısını kontrol et"},
        **kwargs,
    )
    assert len(unchanged) == 1
    assert len(filter_event_review_history(history, history.iloc[0]["event_key"])) == 1
    assert filter_event_review_history(history, "missing").empty


def test_review_history_is_append_only_and_sorted_newest_first():
    from scripts.event_timeline import append_event_review_history, filter_event_review_history

    event = {"source": "Ağ olayları", "event_time": "2026-11-26T09:00:00Z", "event_type": "IP_CHANGED"}
    history = pd.DataFrame()
    history = append_event_review_history(
        history, event, {"status": "new"}, status="reviewed", priority="normal",
        assignee="", note="İlk inceleme", updated_at="2026-11-26T09:10:00Z",
    )
    history = append_event_review_history(
        history, event, {"status": "reviewed", "note": "İlk inceleme"},
        status="resolved", priority="normal", assignee="", note="Tamamlandı",
        updated_at="2026-11-26T09:20:00Z",
    )
    assert len(history) == 2
    result = filter_event_review_history(history, history.iloc[0]["event_key"])
    assert result["status"].tolist() == ["resolved", "reviewed"]
    assert len(history) == 2



def test_filter_event_review_assignment_filters_priority_and_assignee_together():
    from scripts.event_timeline import filter_event_review_assignment

    frame = pd.DataFrame([
        {"event_type": "IP_CHANGED", "review_priority": "high", "review_assignee": "Network Team"},
        {"event_type": "PING_NOT_RESPONDING", "review_priority": "critical", "review_assignee": "Network Team"},
        {"event_type": "NEW_DEVICE", "review_priority": "high", "review_assignee": "Security"},
    ])
    result = filter_event_review_assignment(
        frame, priority="high", assignee="network"
    )
    assert result["event_type"].tolist() == ["IP_CHANGED"]


def test_filter_event_review_assignment_supports_all_empty_missing_and_invalid_values():
    from scripts.event_timeline import filter_event_review_assignment

    frame = pd.DataFrame([
        {"event_type": "IP_CHANGED", "review_priority": "normal", "review_assignee": ""},
        {"event_type": "PING_NOT_RESPONDING", "review_priority": "critical", "review_assignee": "Ops"},
    ])
    assert len(filter_event_review_assignment(frame, priority="all")) == 2
    assert len(filter_event_review_assignment(frame, assignee="")) == 2
    assert filter_event_review_assignment(frame, priority="urgent").empty
    assert filter_event_review_assignment(frame, assignee="Ops").iloc[0]["event_type"] == "PING_NOT_RESPONDING"
    assert filter_event_review_assignment(
        pd.DataFrame([{"event_type": "legacy"}]), priority="high"
    ).empty
    assert filter_event_review_assignment(None).empty


def test_format_event_review_changes_localizes_known_fields_and_values():
    import json
    from scripts.event_timeline import format_event_review_changes

    changes = {
        "status": {"from": "new", "to": "action_required"},
        "priority": {"from": "normal", "to": "high"},
        "assignee": {"from": "", "to": "Ağ ekibi"},
    }
    result = format_event_review_changes(json.dumps(changes, ensure_ascii=False))
    assert result == (
        "Durum: Yeni → İşlem gerekli · "
        "Öncelik: Normal → Yüksek · Sorumlu: — → Ağ ekibi"
    )


def test_format_event_review_changes_handles_empty_malformed_and_unknown_fields():
    import json
    from scripts.event_timeline import format_event_review_changes

    assert format_event_review_changes("") == ""
    assert format_event_review_changes(None) == ""
    assert format_event_review_changes("{not-json") == "{not-json"
    unknown = {"custom_field": {"from": "before", "to": "after"}}
    assert format_event_review_changes(json.dumps(unknown)) == "Custom Field: before → after"
    malformed_shape = {"status": "not-a-transition"}
    assert format_event_review_changes(json.dumps(malformed_shape)) == json.dumps(malformed_shape)


def test_filter_event_review_history_for_events_limits_keys_and_sorts_newest_first():
    from scripts.event_timeline import filter_event_review_history_for_events

    history = pd.DataFrame([
        {"event_key": "event-a", "updated_at": "2026-01-01T10:00:00Z", "status": "new"},
        {"event_key": "event-b", "updated_at": "2026-01-03T10:00:00Z", "status": "reviewed"},
        {"event_key": "event-a", "updated_at": "2026-01-02T10:00:00Z", "status": "resolved"},
    ])
    result = filter_event_review_history_for_events(history, ["event-a"])
    assert result["event_key"].tolist() == ["event-a", "event-a"]
    assert result["status"].tolist() == ["resolved", "new"]


def test_filter_event_review_history_for_events_handles_empty_and_missing_data():
    from scripts.event_timeline import filter_event_review_history_for_events

    history = pd.DataFrame([{"event_key": "event-a", "status": "new"}])
    assert filter_event_review_history_for_events(history, []).empty
    assert filter_event_review_history_for_events(None, ["event-a"]).empty
    assert filter_event_review_history_for_events(
        pd.DataFrame([{"status": "new"}]), ["event-a"]
    ).empty



def test_bulk_event_review_updates_unique_events_and_appends_individual_audit_rows():
    from scripts.event_timeline import bulk_update_event_review, merge_event_review_states

    events = pd.DataFrame([
        {"source": "Ağ olayları", "event_time": "2026-11-26T09:00:00Z",
         "event_type": "IP_CHANGED", "identity_key": "AA:01"},
        {"source": "Canlı izleme", "event_time": "2026-11-26T09:05:00Z",
         "event_type": "PING_NOT_RESPONDING", "identity_key": "AA:02"},
    ])
    states, history, changed = bulk_update_event_review(
        pd.DataFrame(), pd.DataFrame(), events,
        updated_at="2026-11-26T10:00:00Z", status="action_required",
        priority="high", assignee="Ağ ekibi",
    )
    assert changed == 2
    assert len(states) == 2
    assert len(history) == 2
    merged = merge_event_review_states(events, states)
    assert merged["review_status"].tolist() == ["action_required", "action_required"]
    assert merged["review_priority"].tolist() == ["high", "high"]
    assert merged["review_assignee"].tolist() == ["Ağ ekibi", "Ağ ekibi"]
    assert history["event_key"].nunique() == 2


def test_bulk_event_review_preserves_unselected_fields_and_skips_noop_audit():
    from scripts.event_timeline import bulk_update_event_review, event_review_key

    event = pd.Series({
        "source": "Ağ olayları", "event_time": "2026-11-26T09:00:00Z",
        "event_type": "IP_CHANGED", "identity_key": "AA:01",
    })
    states = pd.DataFrame([{
        "event_key": event_review_key(event), "status": "reviewed",
        "note": "Mevcut not", "updated_at": "old", "priority": "high",
        "assignee": "Nöbetçi ekip",
    }])
    history = pd.DataFrame()
    updated, audit, changed = bulk_update_event_review(
        states, history, pd.DataFrame([event]),
        updated_at="2026-11-26T10:00:00Z", status="reviewed",
    )
    assert changed == 0
    assert len(audit) == 0
    assert updated.iloc[0]["note"] == "Mevcut not"
    assert updated.iloc[0]["priority"] == "high"
    assert updated.iloc[0]["assignee"] == "Nöbetçi ekip"
    assert updated.iloc[0]["updated_at"] == "old"


def test_bulk_event_review_deduplicates_event_keys_and_can_clear_assignee():
    from scripts.event_timeline import bulk_update_event_review, event_review_key

    event = pd.Series({
        "source": "Ağ olayları", "event_time": "2026-11-26T09:00:00Z",
        "event_type": "IP_CHANGED", "identity_key": "AA:01",
    })
    states = pd.DataFrame([{
        "event_key": event_review_key(event), "status": "new", "note": "Not",
        "priority": "normal", "assignee": "Eski ekip",
    }])
    duplicated = pd.DataFrame([event, event])
    updated, history, changed = bulk_update_event_review(
        states, pd.DataFrame(), duplicated,
        updated_at="2026-11-26T10:00:00Z", assignee="",
    )
    assert changed == 1
    assert len(updated) == 1
    assert updated.iloc[0]["assignee"] == ""
    assert updated.iloc[0]["note"] == "Not"
    assert len(history) == 1


def test_bulk_event_review_handles_empty_selection_and_rejects_invalid_updates():
    import pytest
    from scripts.event_timeline import bulk_update_event_review

    states, history, changed = bulk_update_event_review(
        pd.DataFrame(), pd.DataFrame(), pd.DataFrame(),
        updated_at="2026-11-26T10:00:00Z", status="reviewed",
    )
    assert states.empty and history.empty and changed == 0
    with pytest.raises(ValueError):
        bulk_update_event_review(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), updated_at="now")
    with pytest.raises(ValueError):
        bulk_update_event_review(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), updated_at="now", status="closed")
    with pytest.raises(ValueError):
        bulk_update_event_review(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), updated_at="now", priority="urgent")



def test_summarize_event_review_workload_groups_assignees_and_open_priorities():
    from scripts.event_timeline import summarize_event_review_workload

    frame = pd.DataFrame([
        {"review_assignee": "Ağ ekibi", "review_status": "action_required", "review_priority": "critical"},
        {"review_assignee": "Ağ ekibi", "review_status": "reviewed", "review_priority": "normal"},
        {"review_assignee": "", "review_status": "new", "review_priority": "high"},
        {"review_assignee": "Ağ ekibi", "review_status": "resolved", "review_priority": "critical"},
    ])
    result = summarize_event_review_workload(frame).set_index("assignee")
    assert result.loc["Ağ ekibi", "total_events"] == 3
    assert result.loc["Ağ ekibi", "open_events"] == 2
    assert result.loc["Ağ ekibi", "action_required_events"] == 1
    assert result.loc["Ağ ekibi", "high_priority_open"] == 1
    assert result.loc["Atanmamış", "new_events"] == 1
    assert result.loc["Atanmamış", "high_priority_open"] == 1


def test_summarize_event_review_workload_defaults_missing_fields_and_handles_empty_data():
    from scripts.event_timeline import summarize_event_review_workload

    assert summarize_event_review_workload(None).empty
    assert summarize_event_review_workload(pd.DataFrame()).empty
    result = summarize_event_review_workload(pd.DataFrame([{"event_type": "legacy"}]))
    assert len(result) == 1
    assert result.iloc[0]["assignee"] == "Atanmamış"
    assert result.iloc[0]["total_events"] == 1
    assert result.iloc[0]["open_events"] == 1
    assert result.iloc[0]["new_events"] == 1
    assert result.iloc[0]["high_priority_open"] == 0



def test_sort_event_review_queue_prioritizes_unassigned_and_high_priority_stably():
    from scripts.event_timeline import sort_event_review_queue
    frame = pd.DataFrame([
        {"event_key": "assigned-low", "event_time": "2026-11-26T10:00:00Z", "review_status": "new", "review_priority": "low", "review_assignee": "Ops"},
        {"event_key": "assigned-critical", "event_time": "2026-11-26T09:00:00Z", "review_status": "new", "review_priority": "critical", "review_assignee": "Ops"},
        {"event_key": "unassigned-high", "event_time": "2026-11-26T08:00:00Z", "review_status": "action_required", "review_priority": "high", "review_assignee": ""},
        {"event_key": "resolved-critical", "event_time": "2026-11-26T11:00:00Z", "review_status": "resolved", "review_priority": "critical", "review_assignee": ""},
    ])
    result = sort_event_review_queue(frame, "priority", unassigned_first=True)
    assert result["event_key"].tolist() == ["unassigned-high", "assigned-critical", "assigned-low", "resolved-critical"]
    assert not any(c.startswith("_queue_") for c in result.columns)
    assert frame["event_key"].iloc[0] == "assigned-low"


def test_sort_event_review_queue_handles_newest_open_and_invalid_modes():
    import pytest
    from scripts.event_timeline import sort_event_review_queue
    frame = pd.DataFrame([
        {"event_key": "old-open", "event_time": "2026-11-25T10:00:00Z", "review_status": "new"},
        {"event_key": "new-open", "event_time": "2026-11-26T10:00:00Z", "review_status": "reviewed"},
        {"event_key": "new-resolved", "event_time": "2026-11-27T10:00:00Z", "review_status": "resolved"},
    ])
    assert sort_event_review_queue(frame, "newest")["event_key"].tolist() == ["new-open", "old-open", "new-resolved"]
    assert sort_event_review_queue(frame, "open")["event_key"].tolist() == ["new-open", "old-open", "new-resolved"]
    with pytest.raises(ValueError): sort_event_review_queue(frame, "random")
    assert sort_event_review_queue(None).empty


def test_add_event_review_history_summary_counts_and_finds_latest_timestamp():
    from scripts.event_timeline import add_event_review_history_summary
    events = pd.DataFrame([{"event_key": "a"}, {"event_key": "b"}])
    history = pd.DataFrame([
        {"event_key": "a", "updated_at": "2026-11-25T10:00:00Z"},
        {"event_key": "a", "updated_at": "2026-11-26T10:00:00Z"},
        {"event_key": "b", "updated_at": "2026-11-24T10:00:00Z"},
    ])
    result = add_event_review_history_summary(events, history).set_index("event_key")
    assert result.loc["a", "review_history_count"] == 2
    assert result.loc["a", "review_last_updated"] == "2026-11-26T10:00:00Z"
    assert result.loc["b", "review_history_count"] == 1
    assert result.loc["b", "review_last_updated"] == "2026-11-24T10:00:00Z"


def test_add_event_review_history_summary_handles_missing_or_empty_history():
    from scripts.event_timeline import add_event_review_history_summary
    events = pd.DataFrame([{"event_key": "a"}])
    assert add_event_review_history_summary(events, None).iloc[0]["review_history_count"] == 0
    assert add_event_review_history_summary(events, pd.DataFrame()).iloc[0]["review_last_updated"] == ""
    assert add_event_review_history_summary(None, None).empty
