"""Parse bounded Nmap XML host-discovery exports as local evidence."""

import ipaddress
from datetime import datetime, timezone

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

from scripts.discovery.identity_signals import (
    normalize_mac, is_locally_administered_mac,
)

NMAP_DISCOVERY_FIELDS = [
    "imported_at", "scan_started_at", "observed_at", "source",
    "ip", "mac", "hostname", "host_state", "host_reason",
    "mac_vendor", "mac_address_type", "evidence_status",
]
MAX_NMAP_XML_BYTES = 10 * 1024 * 1024
MAX_NMAP_HOSTS = 100000


def _timestamp(value):
    if value in (None, ""):
        return ""
    try:
        number = float(value)
        if number > 0:
            return datetime.fromtimestamp(number, timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        pass
    return str(value).strip()


def _normalize_ipv4(value):
    try:
        return str(ipaddress.IPv4Address(str(value).strip()))
    except ValueError:
        return ""


def normalize_nmap_xml(content, imported_at=""):
    """Extract host/address evidence only; ignore port and service details."""
    if isinstance(content, bytes):
        if len(content) > MAX_NMAP_XML_BYTES:
            raise ValueError("Nmap XML dosyası 10 MB sınırını aşıyor.")
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Nmap XML dosyası UTF-8 olmalıdır.") from exc
    else:
        text = str(content or "")
        if len(text.encode("utf-8")) > MAX_NMAP_XML_BYTES:
            raise ValueError("Nmap XML dosyası 10 MB sınırını aşıyor.")

    try:
        root = SafeET.fromstring(
            text,
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        )
    except (DefusedXmlException, SafeET.ParseError, ValueError) as exc:
        raise ValueError(f"Nmap XML okunamadı veya güvenli değil: {exc}") from exc

    if root.tag != "nmaprun" or root.attrib.get("scanner") != "nmap":
        raise ValueError("Dosya geçerli bir Nmap XML çıktısı değil.")

    scan_started_at = _timestamp(root.attrib.get("start", ""))
    rows = []
    for host in root.findall("host"):
        if len(rows) >= MAX_NMAP_HOSTS:
            raise ValueError("Nmap host sayısı izin verilen sınırı aşıyor.")

        status_node = host.find("status")
        host_state = str(
            status_node.attrib.get("state", "unknown") if status_node is not None else "unknown"
        ).strip().casefold()
        host_reason = str(
            status_node.attrib.get("reason", "") if status_node is not None else ""
        ).strip()

        ip = ""
        mac = ""
        mac_vendor = ""
        for address in host.findall("address"):
            address_type = str(address.attrib.get("addrtype", "")).casefold()
            value = str(address.attrib.get("addr", "")).strip()
            if address_type == "ipv4" and not ip:
                ip = _normalize_ipv4(value)
            elif address_type == "mac" and not mac:
                mac = normalize_mac(value)
                mac_vendor = str(address.attrib.get("vendor", "")).strip()

        if not ip and not mac:
            continue

        hostname = ""
        hostnames = host.find("hostnames")
        if hostnames is not None:
            for item in hostnames.findall("hostname"):
                candidate = str(item.attrib.get("name", "")).strip()
                if candidate:
                    hostname = candidate
                    break

        evidence = []
        if host_state == "up":
            evidence.append("nmap_host_up")
        if mac:
            evidence.append(
                "nmap_arp_response" if host_reason == "arp-response"
                else "nmap_mac_observed"
            )
        mac_address_type = (
            "locally_administered" if mac and is_locally_administered_mac(mac)
            else "universally_administered" if mac else "unknown"
        )
        if mac and mac_address_type == "locally_administered":
            evidence.append("locally_administered_mac")
        rows.append({
            "imported_at": imported_at,
            "scan_started_at": scan_started_at,
            "observed_at": _timestamp(host.attrib.get("endtime") or host.attrib.get("starttime", "")),
            "source": "nmap_xml_import",
            "ip": ip,
            "mac": mac,
            "hostname": hostname,
            "host_state": host_state,
            "host_reason": host_reason,
            "mac_vendor": mac_vendor,
            "mac_address_type": mac_address_type,
            "evidence_status": ";".join(evidence) or "nmap_host_observation",
        })

    return rows
