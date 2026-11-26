"""Evidence-based topology generation.

The graph distinguishes observations and subnet context from verified
relationships. A shared subnet is never represented as a physical link.
"""
from __future__ import annotations

import ipaddress
import re

import pandas as pd

from scripts.common import DATA, overwrite_rows


NODE_FIELDS = [
    "id", "label", "node_type", "ip", "mac", "vendor", "status",
    "classification", "evidence_type", "evidence_source", "confidence",
    "details",
]
EDGE_FIELDS = [
    "source", "target", "relation", "confidence", "evidence_type",
    "evidence_source", "observed_at", "details",
]
MAC_PATTERN = re.compile(r"^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$")


def read_data(filename):
    path = DATA / filename
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except (OSError, UnicodeError, pd.errors.ParserError):
        return pd.DataFrame()


def is_network_equipment(classification, hostname):
    value = f"{classification} {hostname}".casefold()
    indicators = (
        "network equipment", "router", "access point", "wireless access point",
        "repeater", "range extender", "switch", "mesh node", "firewall",
        "gateway", "bridge", "controller",
    )
    return any(term in value for term in indicators)


def _valid_mac(value):
    normalized = str(value or "").strip().upper().replace("-", ":")
    return normalized if MAC_PATTERN.fullmatch(normalized) else ""


def _same_subnet(ip_value, subnet_value):
    try:
        address = ipaddress.ip_address(str(ip_value).strip())
        network = ipaddress.ip_network(str(subnet_value).strip(), strict=False)
        return address.version == 4 and network.version == 4 and address in network
    except ValueError:
        return False


def build_topology(inventory, profiles=None, intelligence=None,
                   classifications=None, ap_relationships=None,
                   network_context=None, neighbor_relationships=None):
    """Return topology nodes/edges with explicit evidence provenance."""
    profiles = profiles if profiles is not None else pd.DataFrame()
    intelligence = intelligence if intelligence is not None else pd.DataFrame()
    classifications = classifications if classifications is not None else pd.DataFrame()
    ap_relationships = ap_relationships if ap_relationships is not None else pd.DataFrame()
    network_context = network_context if network_context is not None else pd.DataFrame()
    neighbor_relationships = neighbor_relationships if neighbor_relationships is not None else pd.DataFrame()

    if inventory.empty or "ip" not in inventory.columns:
        return [], []

    inventory = inventory.copy()
    inventory["ip"] = inventory["ip"].astype(str).str.strip()
    inventory = inventory[inventory["ip"] != ""].drop_duplicates("ip", keep="last")

    profile_map = {}
    if not profiles.empty and "mac" in profiles.columns:
        for _, row in profiles.iterrows():
            mac = _valid_mac(row.get("mac", ""))
            if mac:
                profile_map[mac] = row.to_dict()

    intelligence_map = {}
    if not intelligence.empty and "ip" in intelligence.columns:
        intelligence_map = {
            str(row.get("ip", "")).strip(): row.to_dict()
            for _, row in intelligence.iterrows()
            if str(row.get("ip", "")).strip()
        }

    classification_map = {}
    if not classifications.empty and "ip" in classifications.columns:
        classification_map = {
            str(row.get("ip", "")).strip(): row.to_dict()
            for _, row in classifications.iterrows()
            if str(row.get("ip", "")).strip()
        }

    nodes_by_id = {}
    edges = []
    mac_to_node = {}
    scopes = {}

    for _, row in inventory.iterrows():
        ip = str(row.get("ip", "")).strip()
        mac = _valid_mac(row.get("mac", ""))
        profile = profile_map.get(mac, {})
        intel = intelligence_map.get(ip, {})
        classification_row = classification_map.get(ip, {})

        hostname = str(
            row.get("hostname", "") or intel.get("hostname", "")
            or profile.get("hostname", "")
        ).strip()
        vendor = str(
            intel.get("vendor", "") or profile.get("vendor", "")
            or row.get("vendor", "")
        ).strip()
        classification = str(
            intel.get("classification", "")
            or classification_row.get("category", "")
            or profile.get("classification", "")
            or row.get("classification", "")
        ).strip()

        candidate = is_network_equipment(classification, hostname)
        node = {
            "id": ip,
            "label": classification or hostname or ("Network device candidate" if candidate else "Observed device"),
            "node_type": "network_device_candidate" if candidate else "endpoint",
            "ip": ip,
            "mac": mac,
            "vendor": vendor,
            "status": str(row.get("status", "") or "unknown"),
            "classification": classification,
            "evidence_type": "inventory_observation",
            "evidence_source": "device_inventory.csv",
            "confidence": "inferred" if candidate else "strong",
            "details": (
                "Network role is inferred from hostname/classification; "
                "physical role is not verified."
                if candidate else
                "Device address was observed by local discovery; physical topology is unknown."
            ),
        }
        nodes_by_id[ip] = node
        if mac:
            mac_to_node[mac] = ip

        subnet = str(row.get("subnet", "")).strip()
        if subnet:
            try:
                canonical_subnet = str(ipaddress.ip_network(subnet, strict=False))
            except ValueError:
                canonical_subnet = ""
            if canonical_subnet:
                scope_id = f"NETWORK:{canonical_subnet}"
                if scope_id not in nodes_by_id:
                    nodes_by_id[scope_id] = {
                        "id": scope_id,
                        "label": f"Observed subnet {canonical_subnet}",
                        "node_type": "network_scope",
                        "ip": "",
                        "mac": "",
                        "vendor": "",
                        "status": "observed_scope",
                        "classification": "Scan scope; not a physical device",
                        "evidence_type": "scan_scope",
                        "evidence_source": "device_inventory.csv",
                        "confidence": "context_only",
                        "details": "Membership means the address was included in this scan scope, not that a physical link was observed.",
                    }
                scopes[canonical_subnet] = scope_id
                edges.append({
                    "source": scope_id,
                    "target": ip,
                    "relation": "observed_in_scope",
                    "confidence": "context_only",
                    "evidence_type": "shared_scan_scope",
                    "evidence_source": "device_inventory.csv",
                    "observed_at": str(row.get("timestamp", "")),
                    "details": "Shared scan scope only; not a physical or wireless connection.",
                })

    # A default gateway is a configuration fact only when it belongs to the
    # observed subnet. It is never connected to every device as a physical hop.
    for _, row in inventory.iterrows():
        gateway_ip = str(row.get("gateway", "")).strip()
        subnet = str(row.get("subnet", "")).strip()
        if not gateway_ip or not subnet or not _same_subnet(gateway_ip, subnet):
            continue
        try:
            canonical_subnet = str(ipaddress.ip_network(subnet, strict=False))
        except ValueError:
            continue
        gateway_id = gateway_ip
        if gateway_id not in nodes_by_id:
            nodes_by_id[gateway_id] = {
                "id": gateway_id,
                "label": "Configured default gateway address",
                "node_type": "gateway_address",
                "ip": gateway_ip,
                "mac": "",
                "vendor": "",
                "status": "configured_not_observed",
                "classification": "Default gateway from interface configuration",
                "evidence_type": "default_gateway_configuration",
                "evidence_source": "Windows network configuration",
                "confidence": "strong",
                "details": "This is a configured gateway address; device identity and physical links are not confirmed.",
            }
        elif nodes_by_id[gateway_id]["node_type"] != "gateway_address":
            nodes_by_id[gateway_id]["node_type"] = "gateway_address"
            nodes_by_id[gateway_id]["details"] += " Default gateway address confirmed by interface configuration."
        scope_id = scopes.get(canonical_subnet)
        if scope_id:
            edges.append({
                "source": scope_id,
                "target": gateway_id,
                "relation": "configured_default_gateway",
                "confidence": "context_only",
                "evidence_type": "default_gateway_configuration",
                "evidence_source": "Windows network configuration",
                "observed_at": str(row.get("timestamp", "")),
                "details": "Configuration relationship only; not a physical link.",
            })

    # DHCP server data describes the local adapter's configuration only.
    # It is attached to the scanned subnet as context, never as a physical hop.
    if not network_context.empty:
        context_row = network_context.iloc[-1]
        dhcp_server = str(context_row.get("dhcp_server", "")).strip()
        network_cidr = str(context_row.get("network_cidr", "")).strip()
        if dhcp_server and str(context_row.get("dhcp_enabled", "")).strip().lower() in {"enabled", "true", "1"}:
            try:
                dhcp_address = ipaddress.ip_address(dhcp_server)
                if dhcp_address.version == 4:
                    canonical_subnet = str(ipaddress.ip_network(network_cidr, strict=False)) if network_cidr else ""
                    scope_id = scopes.get(canonical_subnet) if canonical_subnet else None
                    if not scope_id and canonical_subnet:
                        scope_id = f"NETWORK:{canonical_subnet}"
                        nodes_by_id.setdefault(scope_id, {
                            "id": scope_id,
                            "label": f"Observed subnet {canonical_subnet}",
                            "node_type": "network_scope",
                            "ip": "", "mac": "", "vendor": "",
                            "status": "adapter_context_scope",
                            "classification": "Local adapter network context",
                            "evidence_type": "adapter_configuration",
                            "evidence_source": "network_context.csv",
                            "confidence": "context_only",
                            "details": "Subnet from the selected local adapter configuration; not a physical device."
                        })
                    if scope_id:
                        server_id = dhcp_server
                        if server_id not in nodes_by_id:
                            nodes_by_id[server_id] = {
                                "id": server_id,
                                "label": "Configured DHCP server address",
                                "node_type": "dhcp_server_address",
                                "ip": dhcp_server, "mac": "", "vendor": "",
                                "status": "configured_not_observed",
                                "classification": "DHCP server from local adapter configuration",
                                "evidence_type": "dhcp_configuration",
                                "evidence_source": "Windows network configuration",
                                "confidence": "context_only",
                                "details": "The selected adapter reports this DHCP server address; server identity and physical links are not confirmed."
                            }
                        else:
                            nodes_by_id[server_id]["details"] += " DHCP server address is also reported by the selected adapter configuration."
                        edges.append({
                            "source": scope_id,
                            "target": server_id,
                            "relation": "configured_dhcp_server",
                            "confidence": "context_only",
                            "evidence_type": "dhcp_configuration",
                            "evidence_source": "Windows network configuration",
                            "observed_at": str(context_row.get("captured_at", "")),
                            "details": "Local adapter configuration only; this does not establish a physical link or enumerate DHCP clients."
                        })
            except ValueError:
                pass

    # Only the latest direct, verified WLAN association per client is a
    # current topology edge. Older observations remain in the local history CSV
    # and must not be drawn as if the client were still attached to old APs.
    latest_by_client = {}
    if not ap_relationships.empty:
        for position, (_, row) in enumerate(ap_relationships.iterrows()):
            if (
                str(row.get("verification_status", "")).strip().lower() != "verified"
                or str(row.get("evidence_type", "")).strip().lower() != "direct_association"
            ):
                continue
            client_mac = _valid_mac(row.get("client_mac", ""))
            ap_bssid = _valid_mac(row.get("ap_bssid", ""))
            if not client_mac or not ap_bssid:
                continue

            observed_at = str(row.get("observed_at", "")).strip()
            parsed_time = pd.to_datetime(observed_at, utc=True, errors="coerce")
            # Preserve file order as a deterministic fallback for missing or
            # malformed timestamps; the later row wins ties.
            sort_key = (
                1 if pd.notna(parsed_time) else 0,
                parsed_time.value if pd.notna(parsed_time) else position,
                position,
            )
            previous = latest_by_client.get(client_mac)
            if previous is None or sort_key >= previous[0]:
                latest_by_client[client_mac] = (sort_key, row.to_dict())

    for client_mac, (_, row) in latest_by_client.items():
        ap_bssid = _valid_mac(row.get("ap_bssid", ""))
        client_id = mac_to_node.get(client_mac, f"MAC:{client_mac}")
        if client_id not in nodes_by_id:
            nodes_by_id[client_id] = {
                "id": client_id,
                "label": str(row.get("client_hostname", "") or "Observed Wi-Fi client"),
                "node_type": "wifi_client",
                "ip": str(row.get("client_ip", "")),
                "mac": client_mac,
                "vendor": "",
                "status": "current_association_observed",
                "classification": "Wi-Fi client interface",
                "evidence_type": "direct_association",
                "evidence_source": str(row.get("source", "") or "Windows WLAN"),
                "confidence": "verified",
                "details": "Latest recorded client association from the local Windows WLAN interface; not a live continuous connection check.",
            }

        ap_id = f"BSSID:{ap_bssid}"
        if ap_id not in nodes_by_id:
            ssid = str(row.get("ssid", "")).strip()
            nodes_by_id[ap_id] = {
                "id": ap_id,
                "label": f"{ssid} (AP radio)" if ssid else "Observed AP radio",
                "node_type": "access_point_radio",
                "ip": "",
                "mac": ap_bssid,
                "vendor": "",
                "status": "latest_associated_ap_radio",
                "classification": "BSSID; physical AP identity may differ",
                "evidence_type": "direct_association",
                "evidence_source": str(row.get("source", "") or "Windows WLAN"),
                "confidence": "verified",
                "details": "BSSID from the latest recorded WLAN association; this identifies a radio interface, not necessarily the whole AP device.",
            }

        # A physical AP grouping is allowed only when a source explicitly
        # supplies its base/device MAC and marks that identity as verified.
        # SSID, vendor OUI, and BSSID similarity are never sufficient.
        ap_device_mac = _valid_mac(row.get("ap_device_mac", ""))
        has_verified_device_identity = (
            str(row.get("device_identity_verification", "")).strip().lower() == "verified"
            and str(row.get("device_identity_evidence", "")).strip().lower() == "direct_ap_device_identity"
        )
        if ap_device_mac and has_verified_device_identity:
            device_id = f"AP_DEVICE:{ap_device_mac}"
            if device_id not in nodes_by_id:
                nodes_by_id[device_id] = {
                    "id": device_id,
                    "label": "Verified physical access point",
                    "node_type": "access_point_device",
                    "ip": "", "mac": ap_device_mac, "vendor": "",
                    "status": "device_identity_verified",
                    "classification": "Physical AP identity from direct evidence",
                    "evidence_type": "direct_ap_device_identity",
                    "evidence_source": str(row.get("device_identity_source", "") or row.get("source", "") or "unspecified"),
                    "confidence": "verified",
                    "details": "Physical AP identity is explicitly supplied and verified; associated BSSIDs are radio interfaces."
                }
            edges.append({
                "source": device_id,
                "target": ap_id,
                "relation": "radio_of",
                "confidence": "verified",
                "evidence_type": "direct_ap_device_identity",
                "evidence_source": str(row.get("device_identity_source", "") or row.get("source", "") or "unspecified"),
                "observed_at": str(row.get("observed_at", "")),
                "details": "BSSID radio grouped under a physical AP only by explicit verified device identity."
            })

        edges.append({
            "source": ap_id,
            "target": client_id,
            "relation": "wifi_association",
            "confidence": "verified",
            "evidence_type": "direct_association",
            "evidence_source": str(row.get("source", "") or "Windows WLAN"),
            "observed_at": str(row.get("observed_at", "")),
            "details": "Latest recorded direct association reported by the local Windows WLAN interface; this is not a continuous live-state guarantee.",
        })


    # Direct neighbor advertisements from local exports; no subnet-based inference.
    from scripts.topology_evidence import prepare_verified_neighbor_edges
    for relationship in prepare_verified_neighbor_edges(neighbor_relationships):
        local_mac, neighbor_mac = relationship["local_mac"], relationship["neighbor_mac"]
        local_id = mac_to_node.get(local_mac, f"MAC:{local_mac}")
        neighbor_id = mac_to_node.get(neighbor_mac, f"MAC:{neighbor_mac}")
        for mac, node_id in ((local_mac, local_id), (neighbor_mac, neighbor_id)):
            if node_id not in nodes_by_id:
                nodes_by_id[node_id] = {
                    "id": node_id, "label": "Advertised network neighbor",
                    "node_type": "network_neighbor", "ip": "", "mac": mac,
                    "vendor": "", "status": "neighbor_advertised",
                    "classification": "Neighbor from direct protocol evidence",
                    "evidence_type": relationship["evidence_type"],
                    "evidence_source": relationship["evidence_source"],
                    "confidence": "verified",
                    "details": "MAC is present in a verified neighbor advertisement; management IP and full role may be unknown."
                }
        edges.append({
            "source": local_id, "target": neighbor_id,
            "relation": relationship["relation"], "confidence": "verified",
            "evidence_type": relationship["evidence_type"],
            "evidence_source": relationship["evidence_source"],
            "observed_at": relationship["observed_at"],
            "details": f"Verified {relationship['protocol'].upper()} or trusted mesh-controller relationship. Local port: {relationship['local_port'] or 'unknown'}; neighbor port: {relationship['neighbor_port'] or 'unknown'}.",
        })

    return list(nodes_by_id.values()), edges


def run():
    inventory = read_data("device_inventory.csv")
    profiles = read_data("device_profiles.csv")
    intelligence = read_data("device_intelligence.csv")
    classifications = read_data("device_classification.csv")
    ap_relationships = read_data("ap_client_relationships.csv")
    network_context = read_data("network_context.csv")
    neighbor_relationships = read_data("neighbor_relationships.csv")

    nodes, edges = build_topology(
        inventory, profiles, intelligence, classifications, ap_relationships,
        network_context, neighbor_relationships
    )
    overwrite_rows(DATA / "topology_nodes.csv", nodes, NODE_FIELDS)
    overwrite_rows(DATA / "topology_edges.csv", edges, EDGE_FIELDS)

    verified = sum(edge["confidence"] == "verified" for edge in edges)
    context = sum(edge["confidence"] == "context_only" for edge in edges)
    inferred = sum(edge["confidence"] == "inferred" for edge in edges)
    print("Topoloji yeniden olusturuldu.")
    print("Dugum:", len(nodes))
    print("Dogrulanmis iliski:", verified)
    print("Baglam iliskisi:", context)
    print("Tahmini iliski:", inferred)
    print("Ayni agda gorunmek fiziksel baglanti kaniti degildir.")


if __name__ == "__main__":
    run()
