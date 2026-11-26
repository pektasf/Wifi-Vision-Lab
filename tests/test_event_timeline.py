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
