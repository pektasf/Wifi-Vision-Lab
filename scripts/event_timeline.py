"""Normalize local network observations into one searchable event timeline."""
from __future__ import annotations

import hashlib
import json

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
                "identity_key": _value(row, ("identity_key",)),
                "ip": _value(row, ("ip", "client_ip")),
                "severity": _severity(row, _value(row, TYPE_FIELDS, "unknown_event")),
                "old_value": _value(row, ("old_value",)),
                "new_value": _value(row, ("new_value",)),
                "details": _value(row, DETAIL_FIELDS),
                "source": source,
            })

    columns = [
        "event_time", "event_type", "subject", "identity_key", "ip", "severity",
        "old_value", "new_value", "details", "source",
    ]
    if not records:
        return pd.DataFrame(columns=columns)

    result = pd.DataFrame(records, columns=columns)
    result["_parsed_time"] = pd.to_datetime(
        result["event_time"], format="mixed", utc=True, errors="coerce"
    )
    result["_order"] = range(len(result))
    result = result.sort_values(
        ["_parsed_time", "_order"],
        ascending=[False, True],
        na_position="last",
        kind="stable",
    )
    return result.drop(columns=["_parsed_time", "_order"]).reset_index(drop=True)



def filter_event_timeline(
    frame: pd.DataFrame,
    *,
    search: str = "",
    source: str = "",
    severity: str = "",
    event_type: str = "",
) -> pd.DataFrame:
    """Apply exact category filters and a literal, case-insensitive text search."""
    if frame is None:
        return pd.DataFrame()
    result = frame.copy()
    sentinels = {"source": "Tüm kaynaklar", "severity": "Tüm seviyeler", "event_type": "Tüm olay türleri"}
    for column, selected in (("source", source), ("severity", severity), ("event_type", event_type)):
        if selected and selected != sentinels[column]:
            if column not in result.columns:
                return result.iloc[0:0].copy()
            result = result[result[column].fillna("").astype(str) == str(selected)]
    term = str(search or "").strip()
    if term:
        mask = result.astype(str).apply(
            lambda column: column.str.contains(term, case=False, na=False, regex=False)
        ).any(axis=1)
        result = result[mask]
    return result.reset_index(drop=True)


def related_event_context(
    frame: pd.DataFrame,
    selected_event: pd.Series,
    window_minutes: float = 15,
) -> pd.DataFrame:
    """Return nearby events for the same stable device identity.

    Legacy rows without an identity key are intentionally not correlated by IP
    or subject because those values can change or be reused.
    """
    try:
        window = float(window_minutes)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("window_minutes must be a non-negative number")
    if pd.isna(window) or window < 0:
        raise ValueError("window_minutes must be a non-negative number")
    if frame is None or frame.empty or selected_event is None:
        return pd.DataFrame(columns=frame.columns if frame is not None else [])
    if "identity_key" not in frame.columns or "event_time" not in frame.columns:
        return frame.iloc[0:0].copy()

    identity = str(selected_event.get("identity_key", "") or "").strip()
    selected_time = pd.to_datetime(
        selected_event.get("event_time", ""), format="mixed", utc=True, errors="coerce"
    )
    if not identity or pd.isna(selected_time):
        return frame.iloc[0:0].copy()

    identities = frame["identity_key"].fillna("").astype(str).str.strip()
    times = pd.to_datetime(
        frame["event_time"], format="mixed", utc=True, errors="coerce"
    )
    mask = identities.eq(identity) & times.notna()
    mask &= (times - selected_time).abs() <= pd.Timedelta(minutes=window)
    result = frame.loc[mask].copy()
    result["_context_time"] = times.loc[mask]
    result = result.sort_values(
        "_context_time", ascending=False, kind="stable"
    ).drop(columns=["_context_time"])
    return result.reset_index(drop=True)
