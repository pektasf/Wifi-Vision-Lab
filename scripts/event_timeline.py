"""Normalize local network observations into one searchable event timeline."""
from __future__ import annotations

import pandas as pd

EVENT_SOURCES = {
    "device_events.csv": "Cihaz olayları",
    "network_events.csv": "Ağ olayları",
    "live_events.csv": "Canlı izleme",
    "behavior_findings.csv": "Davranış analizi",
}

TIME_FIELDS = ("event_time", "timestamp", "observed_at", "time")
TYPE_FIELDS = ("event_type", "event", "type", "event_name")
DETAIL_FIELDS = ("details", "detail", "description", "message")

EVENT_SEVERITY = {
    "ip_changed": "warning",
    "not_in_latest_scan": "warning",
    "ping_not_responding": "warning",
    "multiple_ips_same_mac": "review",
    "multiple_macs_same_ip": "review",
}


def _value(row: pd.Series, fields: tuple[str, ...], default: str = "") -> str:
    for field in fields:
        value = row.get(field, "")
        if pd.notna(value) and str(value).strip():
            return str(value).strip()
    return default


def _severity(row: pd.Series, event_type: str) -> str:
    explicit = _value(row, ("severity",))
    if explicit:
        return explicit
    return EVENT_SEVERITY.get(event_type.strip().lower(), "info")


def summarize_event_severity(frame: pd.DataFrame) -> dict[str, int]:
    """Count normalized severity levels, including any custom explicit levels."""
    if frame is None or frame.empty or "severity" not in frame.columns:
        return {}
    values = frame["severity"].fillna("").astype(str).str.strip().str.lower()
    values = values[values != ""]
    counts = values.value_counts()
    return {str(level): int(count) for level, count in counts.items()}


def normalize_event_frames(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Return a stable, newest-first timeline without discarding source context."""
    records: list[dict[str, str]] = []
    for filename, frame in frames.items():
        if frame is None or frame.empty:
            continue
        source = EVENT_SOURCES.get(filename, filename)
        for _, row in frame.fillna("").iterrows():
            subject = _value(
                row, ("identity_key", "subject", "mac", "client_mac", "ip"),
                "Genel ağ olayı",
            )
            records.append({
                "event_time": _value(row, TIME_FIELDS),
                "event_type": _value(row, TYPE_FIELDS, "unknown_event"),
                "subject": subject,
                "severity": _severity(row, _value(row, TYPE_FIELDS, "unknown_event")),
                "old_value": _value(row, ("old_value",)),
                "new_value": _value(row, ("new_value",)),
                "details": _value(row, DETAIL_FIELDS),
                "source": source,
            })

    columns = [
        "event_time", "event_type", "subject", "severity",
        "old_value", "new_value", "details", "source",
    ]
    if not records:
        return pd.DataFrame(columns=columns)

    result = pd.DataFrame(records, columns=columns)
    result["_parsed_time"] = pd.to_datetime(
        result["event_time"], utc=True, errors="coerce"
    )
    result["_order"] = range(len(result))
    result = result.sort_values(
        ["_parsed_time", "_order"],
        ascending=[False, True],
        na_position="last",
        kind="stable",
    )
    return result.drop(columns=["_parsed_time", "_order"]).reset_index(drop=True)
