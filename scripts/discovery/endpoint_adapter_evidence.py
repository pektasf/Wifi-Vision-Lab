"""Validate opt-in endpoint adapter telemetry imported from authorized Windows hosts."""

import ipaddress

ENDPOINT_ADAPTER_FIELDS = [
    "observed_at", "network_id", "endpoint_ip", "endpoint_mac",
    "adapter_name", "adapter_description", "adapter_status",
    "hardware_interface", "adapter_kind", "evidence_status", "evidence_source",
]


def _normalize_mac(value):
    value = str(value or "").strip().upper().replace("-", ":")
    parts = value.split(":")
    if len(parts) != 6 or any(len(part) != 2 for part in parts):
        return ""
    try:
        bytes.fromhex("".join(parts))
    except ValueError:
        return ""
    return value


def _normalize_ip(value):
    try:
        return str(ipaddress.IPv4Address(str(value).strip()))
    except ValueError:
        return ""


def normalize_endpoint_adapter_payload(payload):
    """Normalize a collector file; imported claims remain endpoint-reported."""
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("Desteklenmeyen endpoint telemetry şeması.")
    if payload.get("collector") != "wifi_vision_endpoint":
        raise ValueError("Bilinmeyen endpoint collector kaynağı.")
    adapters = payload.get("adapters")
    if not isinstance(adapters, list) or len(adapters) > 128:
        raise ValueError("Adaptör listesi geçersiz veya izin verilen sınırı aşıyor.")

    observed_at = str(payload.get("observed_at") or "").strip()
    rows = []
    for adapter in adapters:
        if not isinstance(adapter, dict):
            continue
        mac = _normalize_mac(adapter.get("mac"))
        ips = adapter.get("ipv4_addresses") or []
        if isinstance(ips, str):
            ips = [ips]
        if not isinstance(ips, list):
            continue
        normalized_ips = sorted({ip for value in ips if (ip := _normalize_ip(value))})
        if not mac and not normalized_ips:
            continue

        hardware = adapter.get("hardware_interface")
        if hardware not in (True, False):
            hardware = None
        description = str(adapter.get("description") or "").strip()
        name = str(adapter.get("name") or "Unknown").strip()
        adapter_kind = str(adapter.get("adapter_kind") or "").strip().casefold()
        markers = ("wi-fi direct", "wifi direct", "hosted network", "wireless virtual")
        if hardware is False and any(marker in f"{name} {description}".casefold() for marker in markers):
            adapter_kind = "virtual_wlan"
        elif hardware is False and adapter_kind not in {"virtual_wlan", "virtual_or_software"}:
            adapter_kind = "virtual_or_software"
        elif hardware is True:
            adapter_kind = "physical"
        else:
            adapter_kind = "unknown"

        for ip in normalized_ips or [""]:
            rows.append({
                "observed_at": observed_at,
                "network_id": str(adapter.get("network_cidr") or "").strip(),
                "endpoint_ip": ip,
                "endpoint_mac": mac,
                "adapter_name": name,
                "adapter_description": description,
                "adapter_status": str(adapter.get("status") or "Unknown"),
                "hardware_interface": (
                    "true" if hardware is True else "false" if hardware is False else "unknown"
                ),
                "adapter_kind": adapter_kind,
                "evidence_status": "endpoint_reported",
                "evidence_source": "wifi_vision_endpoint",
            })
    return rows



def enrich_inventory_with_endpoint_adapters(inventory_rows, endpoint_rows):
    """Attach endpoint-reported adapter evidence by exact MAC, else exact IP."""
    enriched = []
    for original in inventory_rows:
        row = dict(original)
        mac = _normalize_mac(row.get("mac"))
        ip = _normalize_ip(row.get("ip"))
        matches = []
        for evidence in endpoint_rows:
            evidence_mac = _normalize_mac(evidence.get("endpoint_mac"))
            evidence_ip = _normalize_ip(evidence.get("endpoint_ip"))
            if mac and evidence_mac and mac == evidence_mac:
                matches.append((evidence, "mac"))
            elif ip and evidence_ip and ip == evidence_ip:
                matches.append((evidence, "ip"))

        if matches:
            row["endpoint_adapter_name"] = ";".join(sorted({
                str(item.get("adapter_name") or "") for item, _ in matches
                if str(item.get("adapter_name") or "").strip()
            }))
            row["endpoint_adapter_kind"] = ";".join(sorted({
                str(item.get("adapter_kind") or "unknown") for item, _ in matches
            }))
            row["endpoint_adapter_description"] = ";".join(sorted({
                str(item.get("adapter_description") or "") for item, _ in matches
                if str(item.get("adapter_description") or "").strip()
            }))
            row["endpoint_evidence_status"] = "endpoint_reported"
            row["endpoint_match_method"] = (
                "mac" if any(method == "mac" for _, method in matches) else "ip"
            )
        else:
            row["endpoint_adapter_name"] = ""
            row["endpoint_adapter_kind"] = ""
            row["endpoint_adapter_description"] = ""
            row["endpoint_evidence_status"] = ""
            row["endpoint_match_method"] = ""
        enriched.append(row)
    return enriched
