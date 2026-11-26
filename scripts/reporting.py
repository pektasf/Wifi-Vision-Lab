"""Report-period helpers for local network observations."""
from __future__ import annotations

import pandas as pd


PERIODS = {
    "Son 24 saat": pd.Timedelta(hours=24),
    "Son 7 gün": pd.Timedelta(days=7),
    "Son 30 gün": pd.Timedelta(days=30),
    "Tüm zamanlar": None,
}

TIME_FIELDS = ("event_time", "timestamp", "observed_at", "time")


def filter_events_by_period(
    events: pd.DataFrame,
    period: str,
    now: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Filter events by a named UTC window, preserving all rows for all-time."""
    if events is None:
        return pd.DataFrame()
    if events.empty or period == "Tüm zamanlar":
        return events.copy()
    duration = PERIODS.get(period)
    if duration is None:
        raise ValueError(f"Unsupported report period: {period}")

    time_column = next((field for field in TIME_FIELDS if field in events.columns), None)
    if time_column is None:
        return events.iloc[0:0].copy()

    current = now or pd.Timestamp.now(tz="UTC")
    current = pd.Timestamp(current)
    if current.tzinfo is None:
        current = current.tz_localize("UTC")
    else:
        current = current.tz_convert("UTC")

    parsed = pd.to_datetime(events[time_column], utc=True, errors="coerce")
    cutoff = current - duration
    return events[parsed.ge(cutoff)].copy().reset_index(drop=True)


def summarize_report_counts(
    inventory: pd.DataFrame,
    events: pd.DataFrame,
    findings: pd.DataFrame,
) -> dict[str, int]:
    """Return factual record counts; no inferred health or open/closed states."""
    return {
        "devices": 0 if inventory is None else int(len(inventory)),
        "events": 0 if events is None else int(len(events)),
        "findings": 0 if findings is None else int(len(findings)),
        "attention_events": (
            int(
                events["severity"].fillna("").astype(str).str.casefold()
                .isin({"critical", "warning", "review"}).sum()
            )
            if events is not None and not events.empty and "severity" in events.columns
            else 0
        ),
    }
