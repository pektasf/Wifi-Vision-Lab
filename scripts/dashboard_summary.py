"""Small, source-aware summaries for the network control-center dashboard."""
from __future__ import annotations

import pandas as pd


RESPONDING_STATES = {"responding", "online", "active", "reachable"}
UNRESPONSIVE_STATES = {
    "offline", "down", "unreachable", "not_responding", "not responding",
    "ping_not_responding",
}
UNKNOWN_STATES = {"", "unknown", "unk", "n/a", "na", "none", "nan", "bilinmiyor"}


def inventory_status_summary(inventory: pd.DataFrame) -> dict[str, object]:
    """Summarize only explicit status values; missing values stay unknown."""
    if inventory is None or inventory.empty:
        return {
            "total": 0, "responding": 0, "unresponsive": 0,
            "unknown": 0, "status_counts": pd.Series(dtype="int64"),
        }

    if "status" not in inventory.columns:
        return {
            "total": len(inventory), "responding": 0, "unresponsive": 0,
            "unknown": len(inventory), "status_counts": pd.Series(
                {"Bilinmiyor": len(inventory)}, dtype="int64"
            ),
        }

    raw = inventory["status"].fillna("").astype(str).str.strip()
    normalized = raw.str.casefold()
    display = raw.where(raw.ne(""), "Bilinmiyor")
    return {
        "total": int(len(inventory)),
        "responding": int(normalized.isin(RESPONDING_STATES).sum()),
        "unresponsive": int(normalized.isin(UNRESPONSIVE_STATES).sum()),
        "unknown": int(normalized.isin(UNKNOWN_STATES).sum()),
        "status_counts": display.value_counts(),
    }


def latest_observation_timestamp(*frames: pd.DataFrame) -> pd.Timestamp | None:
    """Return the newest parseable timestamp across known observation fields."""
    candidates = []
    fields = ("timestamp", "observed_at", "last_seen", "event_time", "time")
    for frame in frames:
        if frame is None or frame.empty:
            continue
        for field in fields:
            if field in frame.columns:
                parsed = pd.to_datetime(frame[field], utc=True, errors="coerce")
                if parsed.notna().any():
                    candidates.append(parsed.max())
    return max(candidates) if candidates else None


def select_attention_events(
    timeline: pd.DataFrame, limit: int = 5
) -> pd.DataFrame:
    """Return recent warning-level events without inventing open/closed state."""
    if timeline is None or timeline.empty:
        return pd.DataFrame() if timeline is None else timeline.head(0).copy()
    if "severity" not in timeline.columns:
        return timeline.head(0).copy()
    levels = timeline["severity"].fillna("").astype(str).str.casefold()
    selected = timeline[levels.isin({"critical", "warning", "review"})]
    return selected.head(max(int(limit), 0)).copy()
