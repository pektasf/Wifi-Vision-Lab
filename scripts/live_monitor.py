"""Local ping-state monitoring with stable device identity context."""
from __future__ import annotations

import ipaddress
import re
import time
from pathlib import Path

import pandas as pd

from scripts.common import DATA, overwrite_rows, stamp, write_rows
from scripts.device_inventory import get_network, ping_one


LIVE_EVENT_FIELDS = [
    "timestamp", "ip", "event", "identity_key", "old_value", "new_value",
]


def normalize_mac_identity(mac: object, ip: str) -> str:
    """Prefer a valid normalized MAC; otherwise use an explicit IP fallback."""
    compact = re.sub(r"[^0-9A-Fa-f]", "", str(mac or ""))
    if re.fullmatch(r"[0-9A-Fa-f]{12}", compact):
        compact = compact.upper()
        return ":".join(compact[index:index + 2] for index in range(0, 12, 2))
    return f"IP:{ip}" if ip else ""


def load_identity_map(inventory_path: Path | None = None) -> dict[str, str]:
    """Read the latest local inventory and map IPv4 addresses to stable identities."""
    path = Path(inventory_path) if inventory_path is not None else DATA / "device_inventory.csv"
    if not path.exists() or not path.stat().st_size:
        return {}
    try:
        inventory = pd.read_csv(path, dtype=str).fillna("")
    except (OSError, pd.errors.ParserError, UnicodeError):
        return {}

    if "ip" not in inventory.columns:
        return {}

    result = {}
    for _, row in inventory.iterrows():
        ip = str(row.get("ip", "")).strip()
        if not ip:
            continue
        result[ip] = normalize_mac_identity(row.get("mac", ""), ip)
    return result


def build_ping_transition(
    ip: str,
    was_responding: bool,
    is_responding: bool,
    identity_map: dict[str, str],
    timestamp: str | None = None,
) -> dict[str, str]:
    """Build one transition record with MAC identity when available."""
    old_value = "responding" if was_responding else "not_responding"
    new_value = "responding" if is_responding else "not_responding"
    return {
        "timestamp": timestamp or stamp(),
        "ip": ip,
        "event": "PING_RESPONDING" if is_responding else "PING_NOT_RESPONDING",
        "identity_key": identity_map.get(ip) or f"IP:{ip}",
        "old_value": old_value,
        "new_value": new_value,
    }


def migrate_live_events_schema(path: Path | None = None) -> None:
    """Add identity and transition fields without discarding legacy ping events."""
    event_path = Path(path) if path is not None else DATA / "live_events.csv"
    if not event_path.exists() or not event_path.stat().st_size:
        return

    existing = pd.read_csv(event_path, dtype=str).fillna("")
    columns = list(existing.columns)
    if columns == LIVE_EVENT_FIELDS:
        return

    unexpected = set(columns) - set(LIVE_EVENT_FIELDS)
    if unexpected:
        raise ValueError(
            f"Unexpected live event columns in {event_path}: {sorted(unexpected)!r}"
        )

    for field in LIVE_EVENT_FIELDS:
        if field not in existing.columns:
            existing[field] = ""
    overwrite_rows(
        event_path,
        existing.reindex(columns=LIVE_EVENT_FIELDS).to_dict("records"),
        LIVE_EVENT_FIELDS,
    )


def main():
    network = get_network()
    hosts = [
        str(address)
        for address in ipaddress.ip_network(network["network"], strict=False).hosts()
    ][:512]
    previous_states: dict[str, bool] = {}
    event_path = DATA / "live_events.csv"
    migrate_live_events_schema(event_path)

    print(f"Monitoring {network['network']}; Ctrl+C to stop")
    while True:
        identity_map = load_identity_map()
        for ip in hosts:
            responding = bool(ping_one(ip))
            if ip in previous_states and previous_states[ip] != responding:
                event = build_ping_transition(
                    ip,
                    previous_states[ip],
                    responding,
                    identity_map,
                )
                write_rows(event_path, [event], LIVE_EVENT_FIELDS)
            previous_states[ip] = responding
        time.sleep(30)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Stopped")
