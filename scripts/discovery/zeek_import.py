"""Normalize authorized Zeek DHCP JSON logs as local lease evidence."""

import ipaddress
import json

from scripts.discovery.identity_signals import (
    normalize_mac, is_locally_administered_mac,
)

ZEEK_DHCP_FIELDS = [
    "imported_at", "observed_at", "source", "client_ip", "assigned_ip",
    "requested_ip", "server_ip", "mac", "hostname", "client_fqdn",
    "lease_time_seconds", "duration_seconds", "message_types",
    "mac_address_type", "evidence_status",
]
MAX_ZEEK_BYTES = 20 * 1024 * 1024
MAX_ZEEK_RECORDS = 100000


def _ip(value):
    try:
        address = ipaddress.IPv4Address(str(value).strip())
        if address.is_unspecified or address.is_multicast or address.is_loopback or address.is_reserved:
            return ""
        return str(address)
    except (TypeError, ValueError):
        return ""


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if number < 0 or number != number or number in (float("inf"), float("-inf")):
        return ""
    return str(int(number)) if number.is_integer() else str(number)


def _records(text):
    try:
        payload = json.loads(text)
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("records", "events", "results"):
                if isinstance(payload.get(key), list):
                    return payload[key]
            return [payload]
    except json.JSONDecodeError:
        pass

    rows = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Zeek JSON satır {line_number} okunamadı: {exc.msg}"
            ) from exc
        if isinstance(item, dict):
            rows.append(item)
        if len(rows) > MAX_ZEEK_RECORDS:
            raise ValueError("Zeek DHCP kayıt sayısı izin verilen sınırı aşıyor.")
    return rows


def normalize_zeek_dhcp_export(content, imported_at=""):
    """Parse Zeek dhcp.log JSON without treating client claims as verified identity."""
    if isinstance(content, bytes):
        if len(content) > MAX_ZEEK_BYTES:
            raise ValueError("Zeek dosyası 20 MB sınırını aşıyor.")
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Zeek DHCP dışa aktarımı UTF-8 olmalıdır.") from exc
    else:
        text = str(content or "")
        if len(text.encode("utf-8")) > MAX_ZEEK_BYTES:
            raise ValueError("Zeek dosyası 20 MB sınırını aşıyor.")

    records = _records(text)
    if len(records) > MAX_ZEEK_RECORDS:
        raise ValueError("Zeek DHCP kayıt sayısı izin verilen sınırı aşıyor.")

    output = []
    for record in records:
        if not isinstance(record, dict):
            continue
        mac = normalize_mac(record.get("mac") or record.get("client_chaddr"))
        client_ip = _ip(record.get("client_addr"))
        assigned_ip = _ip(record.get("assigned_addr"))
        requested_ip = _ip(record.get("requested_addr"))
        server_ip = _ip(record.get("server_addr"))
        hostname = str(record.get("host_name") or "").strip()
        client_fqdn = str(record.get("client_fqdn") or "").strip()
        if not any((mac, client_ip, assigned_ip, hostname, client_fqdn)):
            continue

        if isinstance(record.get("msg_types"), list):
            message_types = ";".join(
                str(item).strip() for item in record["msg_types"] if str(item).strip()
            )
        else:
            message_types = str(record.get("msg_types") or "").strip()

        local_mac = bool(mac) and is_locally_administered_mac(mac)
        evidence = []
        if assigned_ip:
            evidence.append("dhcp_assigned_address")
        elif client_ip:
            evidence.append("dhcp_client_address_observed")
        if mac:
            evidence.append("dhcp_client_mac_observed")
        if hostname or client_fqdn:
            evidence.append("dhcp_client_hostname_reported")
        if local_mac:
            evidence.append("locally_administered_mac")

        output.append({
            "imported_at": imported_at,
            "observed_at": str(record.get("ts") or "").strip(),
            "source": "zeek_dhcp_import",
            "client_ip": client_ip,
            "assigned_ip": assigned_ip,
            "requested_ip": requested_ip,
            "server_ip": server_ip,
            "mac": mac,
            "hostname": hostname,
            "client_fqdn": client_fqdn,
            "lease_time_seconds": _number(record.get("lease_time")),
            "duration_seconds": _number(record.get("duration")),
            "message_types": message_types,
            "mac_address_type": (
                "locally_administered" if local_mac
                else "universally_administered" if mac else "unknown"
            ),
            "evidence_status": ";".join(evidence) or "dhcp_observation",
        })
        if len(output) > MAX_ZEEK_RECORDS:
            raise ValueError("Zeek DHCP kayıt sayısı izin verilen sınırı aşıyor.")

    return output
