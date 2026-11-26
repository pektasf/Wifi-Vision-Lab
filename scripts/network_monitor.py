"""Compare consecutive local inventories using stable device identity."""
from __future__ import annotations

import pandas as pd

from scripts.common import DATA, overwrite_rows, stamp, write_rows

EVENT_FIELDS = [
    "timestamp", "event", "ip", "identity_key", "old_value", "new_value",
]


def _identity(row: pd.Series) -> str:
    mac = str(row.get("mac", "")).strip().upper()
    if mac:
        return mac
    ip = str(row.get("ip", "")).strip()
    return f"IP:{ip}" if ip else ""


def compare_inventories(previous: pd.DataFrame, current: pd.DataFrame) -> list[dict[str, str]]:
    """Detect arrivals, absences and address changes without treating DHCP churn as new devices."""
    old_by_id = {}
    new_by_id = {}

    for _, row in previous.fillna("").iterrows():
        key = _identity(row)
        if key:
            old_by_id[key] = str(row.get("ip", "")).strip()

    for _, row in current.fillna("").iterrows():
        key = _identity(row)
        if key:
            new_by_id[key] = str(row.get("ip", "")).strip()

    timestamp = stamp()
    events = []

    for key in sorted(new_by_id.keys() - old_by_id.keys()):
        ip = new_by_id[key]
        events.append({
            "timestamp": timestamp,
            "event": "FIRST_OBSERVED",
            "ip": ip,
            "identity_key": key,
            "old_value": "",
            "new_value": ip,
        })

    for key in sorted(old_by_id.keys() - new_by_id.keys()):
        ip = old_by_id[key]
        events.append({
            "timestamp": timestamp,
            "event": "NOT_IN_LATEST_SCAN",
            "ip": ip,
            "identity_key": key,
            "old_value": ip,
            "new_value": "",
        })

    for key in sorted(old_by_id.keys() & new_by_id.keys()):
        old_ip, new_ip = old_by_id[key], new_by_id[key]
        if old_ip and new_ip and old_ip != new_ip:
            events.append({
                "timestamp": timestamp,
                "event": "IP_CHANGED",
                "ip": new_ip,
                "identity_key": key,
                "old_value": old_ip,
                "new_value": new_ip,
            })

    return events


def _migrate_event_csv_schema(path) -> None:
    """Append new event context columns while retaining all legacy event rows."""
    if not path.exists() or not path.stat().st_size:
        return

    existing = pd.read_csv(path, dtype=str).fillna("")
    columns = list(existing.columns)
    if columns == EVENT_FIELDS:
        return

    unexpected = set(columns) - set(EVENT_FIELDS)
    if unexpected:
        raise ValueError(
            f"Unexpected network event columns in {path}: {sorted(unexpected)!r}"
        )

    for field in EVENT_FIELDS:
        if field not in existing.columns:
            existing[field] = ""
    overwrite_rows(path, existing.reindex(columns=EVENT_FIELDS).to_dict("records"), EVENT_FIELDS)


def run():
    inventory_path = DATA / "device_inventory.csv"
    if not inventory_path.exists():
        return []

    current = pd.read_csv(inventory_path, dtype=str).fillna("")
    previous_path = DATA / "last_inventory.csv"
    previous = (
        pd.read_csv(previous_path, dtype=str).fillna("")
        if previous_path.exists()
        else pd.DataFrame(columns=["ip", "mac"])
    )

    events = compare_inventories(previous, current)
    event_path = DATA / "network_events.csv"
    _migrate_event_csv_schema(event_path)
    write_rows(event_path, events, EVENT_FIELDS)
    current.to_csv(previous_path, index=False)
    return events


if __name__ == "__main__":
    print(len(run()))
