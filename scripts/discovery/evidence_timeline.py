"""Build a non-merging timeline across local and imported identity evidence."""

import hashlib
import ipaddress
from datetime import datetime, timezone

from scripts.discovery.identity_signals import (
    normalize_mac, is_locally_administered_mac,
)

IDENTITY_TIMELINE_FIELDS = [
    "event_id", "observed_at", "source", "mac", "ip", "hostname",
    "evidence", "identity_indicator", "randomized_mac",
    "correlation_method", "inventory_match_count",
    "inventory_identity_assessment", "inventory_identity_signals",
    "details",
]
MAX_TIMELINE_ROWS = 10000


def _normalize_ipv4(value):
    try:
        return str(ipaddress.IPv4Address(str(value or "").strip()))
    except ValueError:
        return ""


def _network_scope(row):
    """Return only an explicitly supplied network scope; never infer a subnet."""
    for field in ("network_id", "subnet", "network"):
        value = str(row.get(field, "") or "").strip()
        if value:
            return value
    return ""


def _records(value):
    if value is None:
        return []
    if hasattr(value, "to_dict"):
        return value.to_dict("records")
    return list(value)


def _time_sort_key(value):
    value = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return (1, parsed.timestamp())
    except (TypeError, ValueError, OverflowError, OSError):
        return (0, value)


def build_identity_evidence_timeline(
    inventory=None,
    local_observations=None,
    endpoint_observations=None,
    wireless_observations=None,
    nmap_observations=None,
    zeek_observations=None,
    limit=MAX_TIMELINE_ROWS,
):
    """Correlate exact identifiers conservatively while keeping source rows separate.

    MAC matches are rejected when both records explicitly identify different
    networks. IP-only matches require an explicit, equal network scope on both
    sides because an IPv4 address can be reused on another network.
    """
    inventory_rows = _records(inventory)
    mac_index = {}
    ip_index = {}
    for item in inventory_rows:
        mac = normalize_mac(item.get("mac"))
        ip = _normalize_ipv4(item.get("ip"))
        if mac:
            mac_index.setdefault(mac, []).append(item)
        if ip:
            ip_index.setdefault(ip, []).append(item)

    timeline = []

    def append(source, row, mac_value="", ip_value="", hostname="", evidence="", details=""):
        mac = normalize_mac(mac_value)
        ip = _normalize_ipv4(ip_value)
        if not mac and not ip:
            return

        scope = _network_scope(row)
        matches = []
        correlation = "unmatched"

        if mac and mac in mac_index:
            candidates = mac_index[mac]
            matches = [
                item for item in candidates
                if not (scope and _network_scope(item)
                        and scope != _network_scope(item))
            ]
            if matches:
                correlation = "exact_mac"
            else:
                correlation = "network_mismatch"
        elif ip and ip in ip_index:
            candidates = ip_index[ip]
            if not scope or not any(_network_scope(item) for item in candidates):
                correlation = "ip_scope_unknown"
            else:
                matches = [
                    item for item in candidates
                    if _network_scope(item) == scope
                ]
                if matches:
                    correlation = "exact_ip"
                elif any(_network_scope(item) for item in candidates):
                    correlation = "network_mismatch"
                else:
                    correlation = "ip_scope_unknown"

        assessments = sorted({
            str(item.get("identity_assessment", "")).strip()
            for item in matches if str(item.get("identity_assessment", "")).strip()
        })
        signals = sorted({
            signal.strip()
            for item in matches
            for signal in str(item.get("identity_signals", "")).split(";")
            if signal.strip()
        })
        local_mac = bool(mac) and is_locally_administered_mac(mac)
        random_value = str(row.get("randomized_mac", "")).strip().casefold()
        if random_value not in {"true", "false"}:
            random_value = "unknown"
        indicator = (
            "Kismet randomized MAC" if random_value == "true"
            else "Locally administered MAC" if local_mac
            else ""
        )

        observed_at = str(
            row.get("observed_at") or row.get("ts") or row.get("imported_at") or ""
        ).strip()
        event_material = "|".join([
            source, observed_at, mac, ip,
            str(row.get("device_key") or row.get("server_ip") or ""),
            str(evidence or ""),
        ])
        event_id = hashlib.sha256(event_material.encode("utf-8")).hexdigest()[:20]

        timeline.append({
            "event_id": event_id,
            "observed_at": observed_at,
            "source": source,
            "mac": mac,
            "ip": ip,
            "hostname": str(hostname or "").strip(),
            "evidence": str(evidence or "").strip(),
            "identity_indicator": indicator,
            "randomized_mac": random_value,
            "correlation_method": correlation,
            "inventory_match_count": len(matches),
            "inventory_identity_assessment": ";".join(assessments),
            "inventory_identity_signals": ";".join(signals),
            "details": str(details or "").strip(),
        })

    for row in _records(local_observations):
        append(
            "Windows keşif",
            row,
            row.get("mac"),
            row.get("ip"),
            row.get("hostname"),
            row.get("evidence") or row.get("status"),
            row.get("source", ""),
        )

    for row in _records(endpoint_observations):
        append(
            "Yetkili endpoint",
            row,
            row.get("endpoint_mac"),
            row.get("endpoint_ip"),
            row.get("adapter_name"),
            row.get("evidence_status"),
            f"{row.get('adapter_kind', '')} · {row.get('adapter_description', '')}",
        )

    for row in _records(wireless_observations):
        append(
            "Kismet Wi-Fi",
            row,
            row.get("mac"),
            "",
            row.get("name") or row.get("device_type"),
            row.get("evidence_status"),
            f"BSSID: {row.get('last_bssid', '')} · Kanal: {row.get('channel', '')} · Sinyal: {row.get('signal_dbm', '')} dBm",
        )

    for row in _records(nmap_observations):
        append(
            "Nmap host keşfi",
            row,
            row.get("mac"),
            row.get("ip"),
            row.get("hostname"),
            row.get("evidence_status"),
            f"Durum: {row.get('host_state', '')} · Neden: {row.get('host_reason', '')}",
        )

    for row in _records(zeek_observations):
        append(
            "Zeek DHCP",
            row,
            row.get("mac"),
            row.get("assigned_ip") or row.get("client_ip"),
            row.get("hostname") or row.get("client_fqdn"),
            row.get("evidence_status"),
            f"DHCP sunucusu: {row.get('server_ip', '')} · Mesajlar: {row.get('message_types', '')}",
        )

    timeline.sort(key=lambda item: _time_sort_key(item["observed_at"]), reverse=True)
    return timeline[:max(1, min(int(limit), MAX_TIMELINE_ROWS))]
