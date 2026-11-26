import pandas as pd
import pytest

from scripts.reporting import (
    filter_events_by_period,
    local_timestamp_iso,
    summarize_report_counts,
)


def test_filter_events_by_period_keeps_only_recent_valid_timestamps():
    events = pd.DataFrame({
        "event_time": [
            "2026-11-26T08:30:00Z",
            "2026-11-25T08:00:00Z",
            "invalid",
        ],
        "event_type": ["recent", "old", "unknown"],
    })
    result = filter_events_by_period(
        events,
        "Son 24 saat",
        now=pd.Timestamp("2026-11-26T09:00:00Z"),
    )
    assert result["event_type"].tolist() == ["recent"]


def test_all_time_filter_preserves_rows_and_invalid_timestamps():
    events = pd.DataFrame({
        "timestamp": ["bad", "2020-01-01T00:00:00Z"],
        "event": ["legacy", "old"],
    })
    result = filter_events_by_period(events, "Tüm zamanlar")
    assert result.equals(events)


def test_period_filter_without_time_column_returns_empty_with_schema():
    events = pd.DataFrame({"event": ["up"]})
    result = filter_events_by_period(events, "Son 7 gün")
    assert result.empty
    assert list(result.columns) == ["event"]


def test_unknown_period_is_rejected():
    with pytest.raises(ValueError, match="Unsupported report period"):
        filter_events_by_period(pd.DataFrame({"timestamp": []}), "last year")


def test_report_counts_do_not_infer_open_or_closed_findings():
    inventory = pd.DataFrame([{"ip": "192.0.2.1"}])
    events = pd.DataFrame({"severity": ["warning", "info", "review"]})
    findings = pd.DataFrame([{"type": "finding"}])
    result = summarize_report_counts(inventory, events, findings)
    assert result == {
        "devices": 1,
        "events": 3,
        "findings": 1,
        "attention_events": 2,
    }


def test_local_timestamp_iso_includes_timezone_offset():
    value = local_timestamp_iso()
    parsed = pd.Timestamp(value)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() is not None
