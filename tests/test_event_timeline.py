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


def test_normalizer_keeps_missing_dates_last_and_preserves_stable_order():
    frame = pd.DataFrame([
        {"timestamp": "bad", "ip": "first", "event": "unknown"},
        {"timestamp": "2026-02-01T10:00:00Z", "ip": "newer", "event": "up"},
        {"timestamp": "bad", "ip": "second", "event": "unknown"},
    ])

    result = normalize_event_frames({"network_events.csv": frame})

    assert result["subject"].tolist() == ["newer", "first", "second"]


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
