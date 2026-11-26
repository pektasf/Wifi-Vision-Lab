"""Evidence-based review findings from the current local device inventory."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.common import DATA, overwrite_rows, stamp


FINDING_FIELDS = ["timestamp", "severity", "type", "subject", "detail"]


def analyze_inventory(inventory: pd.DataFrame) -> list[dict[str, str]]:
    """Find duplicate address mappings in one inventory snapshot.

    These are review signals only. They do not establish spoofing, compromise,
    or malicious behavior.
    """
    if inventory is None or inventory.empty:
        return []
    if "ip" not in inventory.columns or "mac" not in inventory.columns:
        return []

    frame = inventory.copy()
    frame["ip"] = frame["ip"].fillna("").astype(str).str.strip()
    frame["mac"] = (
        frame["mac"].fillna("").astype(str).str.strip().str.upper()
    )
    frame = frame[(frame["ip"] != "") | (frame["mac"] != "")]
    timestamp = stamp()
    findings: list[dict[str, str]] = []

    with_mac = frame[frame["mac"] != ""]
    for mac, group in with_mac.groupby("mac", sort=True):
        ips = sorted(value for value in group["ip"].unique().tolist() if value)
        if len(ips) > 1:
            findings.append({
                "timestamp": timestamp,
                "severity": "review",
                "type": "MULTIPLE_IPS_SAME_MAC",
                "subject": mac,
                "detail": (
                    "Aynı MAC adresi tek envanter anlık görüntüsünde birden fazla "
                    "IP ile eşleşti: " + ", ".join(ips)
                ),
            })

    with_ip = frame[frame["ip"] != ""]
    for ip, group in with_ip.groupby("ip", sort=True):
        macs = sorted(value for value in group["mac"].unique().tolist() if value)
        if len(macs) > 1:
            findings.append({
                "timestamp": timestamp,
                "severity": "review",
                "type": "MULTIPLE_MACS_SAME_IP",
                "subject": ip,
                "detail": (
                    "Aynı IP adresi tek envanter anlık görüntüsünde birden fazla "
                    "MAC ile eşleşti: " + ", ".join(macs)
                ),
            })

    return findings


def run(
    inventory_path=None,
    output_path=None,
) -> list[dict[str, str]]:
    """Analyze the current local inventory and persist the resulting findings."""
    source = Path(inventory_path) if inventory_path is not None else DATA / "device_inventory.csv"
    destination = Path(output_path) if output_path is not None else DATA / "behavior_findings.csv"
    try:
        inventory = pd.read_csv(
            source, dtype=str, keep_default_na=False, encoding="utf-8-sig"
        )
    except FileNotFoundError:
        return []
    except (OSError, UnicodeError, pd.errors.ParserError):
        return []

    findings = analyze_inventory(inventory)
    overwrite_rows(destination, findings, FINDING_FIELDS)
    return findings


if __name__ == "__main__":
    print(len(run()))



def prepare_temporal_context(
    profiles: pd.DataFrame, events: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Summarize device continuity and corroborating IP-change event history.

    IP changes remain contextual observations, never threat verdicts.
    """
    columns = [
        "identity_key", "hostname", "ip_history", "ip_change_count",
        "observation_count", "first_seen", "last_seen", "history_span_days",
        "latest_observation_status", "ip_change_events", "last_ip_change",
        "last_ip_change_from", "last_ip_change_to",
    ]
    if profiles is None or profiles.empty or "identity_key" not in profiles.columns:
        return pd.DataFrame(columns=columns)

    result = profiles.copy()
    for column in columns:
        if column not in result.columns:
            result[column] = ""
    result["_ip_change_count"] = pd.to_numeric(
        result["ip_change_count"], errors="coerce"
    ).fillna(0)
    result["_observation_count"] = pd.to_numeric(
        result["observation_count"], errors="coerce"
    ).fillna(0)
    if "status" in result.columns:
        result["latest_observation_status"] = result["status"].fillna("").astype(str)

    first = pd.to_datetime(result["first_seen"], utc=True, errors="coerce")
    last = pd.to_datetime(result["last_seen"], utc=True, errors="coerce")
    result["history_span_days"] = (
        (last - first).dt.total_seconds() / 86400
    ).round(1).where(first.notna() & last.notna(), "")

    if events is not None and not events.empty and "identity_key" in events.columns:
        event_frame = events.copy()
        if "event_type" in event_frame.columns:
            event_frame = event_frame[
                event_frame["event_type"].astype(str).str.casefold() == "ip_changed"
            ].copy()
        else:
            event_frame = event_frame.iloc[0:0].copy()
        if not event_frame.empty:
            if "event_time" not in event_frame.columns:
                event_frame["event_time"] = ""
            event_frame["_event_time"] = pd.to_datetime(
                event_frame["event_time"], utc=True, errors="coerce"
            )
            event_frame = event_frame.sort_values(
                "_event_time", ascending=False, na_position="last", kind="stable"
            )
            for key, group in event_frame.groupby("identity_key", sort=False):
                mask = result["identity_key"].astype(str) == str(key)
                if not mask.any():
                    continue
                latest = group.iloc[0]
                result.loc[mask, "ip_change_events"] = len(group)
                result.loc[mask, "last_ip_change"] = str(latest.get("event_time", "") or "")
                result.loc[mask, "last_ip_change_from"] = str(latest.get("old_value", "") or "")
                result.loc[mask, "last_ip_change_to"] = str(latest.get("new_value", "") or "")

    result = result[result["_ip_change_count"] > 0].copy()
    result = result.sort_values(
        ["_ip_change_count", "_observation_count", "identity_key"],
        ascending=[False, False, True],
        kind="stable",
    )
    return result[columns].reset_index(drop=True)


def prepare_ip_change_history(events: pd.DataFrame) -> pd.DataFrame:
    """Return recorded IP transitions newest-first, preserving original evidence."""
    columns = [
        "event_time", "identity_key", "old_value", "new_value", "details"
    ]
    if events is None or events.empty or "event_type" not in events.columns:
        return pd.DataFrame(columns=columns)
    result = events[
        events["event_type"].astype(str).str.casefold() == "ip_changed"
    ].copy()
    if result.empty:
        return pd.DataFrame(columns=columns)
    for column in columns:
        if column not in result.columns:
            result[column] = ""
    result["_sort_time"] = pd.to_datetime(
        result["event_time"], utc=True, errors="coerce"
    )
    result = result.sort_values(
        "_sort_time", ascending=False, na_position="last", kind="stable"
    )
    return result[columns].reset_index(drop=True)


def prepare_observation_gaps(
    history: pd.DataFrame,
    events: pd.DataFrame | None = None,
    minimum_gap_minutes: float = 10,
) -> pd.DataFrame:
    """Summarize intervals between stored observations, not device downtime."""
    columns = [
        "identity_key", "previous_observation", "next_observation",
        "gap_minutes", "reappearance_event_recorded", "evidence",
    ]
    try:
        threshold = float(minimum_gap_minutes)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("minimum_gap_minutes must be a non-negative number")
    if pd.isna(threshold) or threshold < 0:
        raise ValueError("minimum_gap_minutes must be a non-negative number")
    if history is None or history.empty or not {"identity_key", "observed_at"}.issubset(history.columns):
        return pd.DataFrame(columns=columns)

    frame = history[["identity_key", "observed_at"]].copy()
    frame["identity_key"] = frame["identity_key"].fillna("").astype(str).str.strip()
    frame["_time"] = pd.to_datetime(frame["observed_at"], utc=True, errors="coerce")
    frame = frame[frame["identity_key"].ne("") & frame["_time"].notna()]
    frame = frame.drop_duplicates(["identity_key", "_time"])
    if frame.empty:
        return pd.DataFrame(columns=columns)

    recorded: set[tuple[str, pd.Timestamp]] = set()
    required = {"identity_key", "event_type", "event_time"}
    if events is not None and not events.empty and required.issubset(events.columns):
        event_frame = events.copy()
        event_frame["identity_key"] = event_frame["identity_key"].fillna("").astype(str).str.strip()
        event_frame = event_frame[
            event_frame["event_type"].fillna("").astype(str).str.casefold().eq("seen_again")
        ].copy()
        event_frame["_time"] = pd.to_datetime(event_frame["event_time"], utc=True, errors="coerce")
        recorded = {
            (str(row["identity_key"]), row["_time"])
            for _, row in event_frame.iterrows()
            if str(row["identity_key"]).strip() and pd.notna(row["_time"])
        }

    gaps = []
    for identity, group in frame.groupby("identity_key", sort=True):
        times = group.sort_values("_time", kind="stable")["_time"].tolist()
        for previous, current in zip(times, times[1:]):
            minutes = (current - previous).total_seconds() / 60
            if minutes < threshold:
                continue
            event_recorded = (identity, current) in recorded
            gaps.append({
                "identity_key": identity,
                "previous_observation": previous.isoformat(),
                "next_observation": current.isoformat(),
                "gap_minutes": round(minutes, 1),
                "reappearance_event_recorded": event_recorded,
                "evidence": (
                    "Kayıtlı seen_again olayı mevcut; yalnızca yeniden gözlemlenmeyi doğrular."
                    if event_recorded else
                    "Ardışık kayıt zamanları arasında gözlem aralığı var; bağlantı durumu bilinmiyor."
                ),
                "_sort_time": current,
            })
    gaps.sort(key=lambda item: item["_sort_time"], reverse=True)
    for item in gaps:
        item.pop("_sort_time", None)
    return pd.DataFrame(gaps, columns=columns)
