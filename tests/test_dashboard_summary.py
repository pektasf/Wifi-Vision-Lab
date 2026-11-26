import pandas as pd

from scripts.dashboard_summary import (
    inventory_status_summary,
    latest_observation_timestamp,
    select_attention_events,
)


def test_inventory_summary_keeps_unknown_separate():
    inventory = pd.DataFrame({
        "status": ["online", "offline", "", "unknown", "responding"]
    })
    result = inventory_status_summary(inventory)
    assert result["total"] == 5
    assert result["responding"] == 2
    assert result["unresponsive"] == 1
    assert result["unknown"] == 2
    assert result["status_counts"]["Bilinmiyor"] == 1


def test_inventory_without_status_is_unknown_not_healthy():
    result = inventory_status_summary(pd.DataFrame({"ip": ["10.0.0.1", "10.0.0.2"]}))
    assert result["total"] == 2
    assert result["responding"] == 0
    assert result["unknown"] == 2


def test_latest_observation_uses_latest_valid_timestamp():
    inventory = pd.DataFrame({"last_seen": ["2026-01-01T10:00:00Z"]})
    events = pd.DataFrame({"event_time": ["2026-01-02T11:30:00Z", "invalid"]})
    result = latest_observation_timestamp(inventory, events)
    assert result == pd.Timestamp("2026-01-02T11:30:00Z")


def test_latest_observation_returns_none_without_valid_time():
    assert latest_observation_timestamp(pd.DataFrame({"timestamp": ["bad"]})) is None


def test_attention_events_include_only_explicit_attention_levels():
    timeline = pd.DataFrame({
        "event_type": ["warning", "info", "critical", "review"],
        "severity": ["warning", "info", "critical", "review"],
    })
    result = select_attention_events(timeline, limit=2)
    assert result["event_type"].tolist() == ["warning", "critical"]
    assert len(select_attention_events(timeline, limit=0)) == 0


def test_attention_events_empty_input_preserves_columns():
    empty = pd.DataFrame(columns=["event_time", "severity"])
    result = select_attention_events(empty)
    assert result.empty
    assert list(result.columns) == ["event_time", "severity"]



def test_localized_unknown_status_is_counted_as_unknown():
    result = inventory_status_summary(pd.DataFrame({
        "status": ["Bilinmiyor", "responding"]
    }))
    assert result["unknown"] == 1
    assert result["responding"] == 1



def test_observation_posture_counts_only_recorded_attention_levels():
    from scripts.dashboard_summary import summarize_observation_posture

    inventory = pd.DataFrame({"status": ["online", "unknown", "offline"]})
    timeline = pd.DataFrame({
        "severity": ["critical", "warning", "review", "info", "", None],
    })
    result = summarize_observation_posture(inventory, timeline)
    assert result == {
        "devices": 3,
        "responding": 1,
        "unresponsive": 1,
        "unknown": 1,
        "events": 6,
        "critical": 1,
        "warning": 1,
        "review": 1,
        "attention": 3,
    }


def test_observation_posture_empty_data_does_not_claim_safe_network():
    from scripts.dashboard_summary import summarize_observation_posture

    result = summarize_observation_posture(pd.DataFrame(), pd.DataFrame())
    assert result["devices"] == 0
    assert result["events"] == 0
    assert result["attention"] == 0
