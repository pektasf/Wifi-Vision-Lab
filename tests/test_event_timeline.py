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
    assert result.iloc[0]["source"] == "Canli izleme"
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
        "event_time", "event_type", "subject", "severity",
        "old_value", "new_value", "details", "source",
    ]
