"""Conservative indicators for observed network identity variation."""

import csv
from pathlib import Path

from scripts.common import DATA, overwrite_rows

HISTORY_FIELDS = ["observed_at", "network_id", "ip", "mac", "hostname", "source"]
MAX_HISTORY_ROWS = 20000


def normalize_mac(value):
    value = str(value or "").strip().upper().replace("-", ":")
    parts = value.split(":")
    if len(parts) != 6 or any(len(part) != 2 for part in parts):
        return ""
    try:
        bytes.fromhex("".join(parts))
    except ValueError:
        return ""
    return value


def is_locally_administered_mac(value):
    mac = normalize_mac(value)
    return bool(mac) and bool(int(mac.split(":")[0], 16) & 0x02)


def load_identity_history(path=None):
    path = Path(path or DATA / "discovery_identity_history.csv")
    if not path.exists():
        return []
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))[-MAX_HISTORY_ROWS:]
    except (OSError, csv.Error):
        return []


def analyze_identity_variation(observations, history=None):
    """Return per-observation indicators, not a claim of a device's true identity."""
    history = list(history or [])
    all_rows = [*history, *observations]
    ip_macs = {}
    mac_ips = {}
    hostname_macs = {}
    current_ip_macs = {}

    for row in all_rows:
        network = str(row.get("network_id", "")).strip()
        mac = normalize_mac(row.get("mac"))
        ip = str(row.get("ip", "")).strip()
        hostname = str(row.get("hostname", "")).strip().casefold()
        if not network or not mac:
            continue
        if ip:
            ip_macs.setdefault((network, ip), set()).add(mac)
            mac_ips.setdefault((network, mac), set()).add(ip)
        if hostname:
            hostname_macs.setdefault((network, hostname), set()).add(mac)

    for row in observations:
        network = str(row.get("network_id", "")).strip()
        ip = str(row.get("ip", "")).strip()
        mac = normalize_mac(row.get("mac"))
        if network and ip and mac:
            current_ip_macs.setdefault((network, ip), set()).add(mac)

    result = {}
    for row in observations:
        network = str(row.get("network_id", "")).strip()
        ip = str(row.get("ip", "")).strip()
        hostname = str(row.get("hostname", "")).strip().casefold()
        mac = normalize_mac(row.get("mac"))
        matching_macs = ip_macs.get((network, ip), set()) if ip and not mac else set()
        resolved_mac = next(iter(matching_macs)) if len(matching_macs) == 1 else mac
        identity = (
            f"{network}|mac|{resolved_mac}" if resolved_mac
            else f"{network}|ip|{ip}" if ip else ""
        )
        if not identity:
            continue

        signals = set()
        if not mac:
            signals.add("mac_not_observed")
        else:
            if is_locally_administered_mac(mac):
                signals.add("locally_administered_mac")
            if ip and len(current_ip_macs.get((network, ip), set())) > 1:
                signals.add("same_ip_multiple_macs")
            if ip and len(ip_macs.get((network, ip), set())) > 1:
                signals.add("ip_mac_changed_over_time")
            if len(mac_ips.get((network, mac), set())) > 1:
                signals.add("mac_seen_with_multiple_ips")
            if hostname and len(hostname_macs.get((network, hostname), set())) > 1:
                signals.add("hostname_seen_with_multiple_macs")

        result.setdefault(identity, set()).update(signals)

    output = {}
    for identity, signals in result.items():
        if {"same_ip_multiple_macs", "ip_mac_changed_over_time"} & signals:
            assessment = "review"
        elif signals:
            assessment = "indicator"
        else:
            assessment = "no_indicator_observed"
        output[identity] = {
            "identity_assessment": assessment,
            "identity_signals": ";".join(sorted(signals)),
        }
    return output


def save_identity_history(observations, history=None, path=None):
    """Persist a bounded, local-only history for detecting address rotation."""
    path = Path(path or DATA / "discovery_identity_history.csv")
    rows = list(history if history is not None else load_identity_history(path))
    seen = {
        (r.get("observed_at", ""), r.get("network_id", ""), r.get("ip", ""),
         r.get("mac", ""), r.get("source", ""))
        for r in rows
    }
    for observation in observations:
        row = {field: str(observation.get(field, "") or "") for field in HISTORY_FIELDS}
        key = (row["observed_at"], row["network_id"], row["ip"], row["mac"], row["source"])
        if (row["ip"] or row["mac"]) and key not in seen:
            rows.append(row)
            seen.add(key)
    rows = rows[-MAX_HISTORY_ROWS:]
    overwrite_rows(path, rows, HISTORY_FIELDS)
    return rows
