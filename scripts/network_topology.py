from scripts.common import DATA, overwrite_rows
from pathlib import Path
import pandas as pd


def read_data(filename):
    path = DATA / filename
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def is_network_equipment(classification, hostname):
    text = f"{classification} {hostname}".casefold()

    indicators = [
        "network equipment",
        "router",
        "access point",
        "wireless access point",
        "repeater",
        "range extender",
        "switch",
        "mesh node",
        "firewall",
        "gateway",
        "bridge"
    ]

    return any(term in text for term in indicators)


def run():
    inventory = read_data("device_inventory.csv")
    profiles = read_data("device_profiles.csv")
    intelligence = read_data("device_intelligence.csv")
    classifications = read_data("device_classification.csv")

    node_fields = [
        "id", "label", "node_type", "ip",
        "mac", "vendor", "status", "classification"
    ]

    edge_fields = [
        "source", "target", "relation", "confidence"
    ]

    if inventory.empty or "ip" not in inventory.columns:
        overwrite_rows(DATA / "topology_nodes.csv", [], node_fields)
        overwrite_rows(DATA / "topology_edges.csv", [], edge_fields)
        print("Envanter bulunamadi.")
        return

    inventory = inventory.drop_duplicates("ip", keep="last")

    profile_map = {}
    intelligence_map = {}
    classification_map = {}

    if not intelligence.empty and "ip" in intelligence.columns:
        intelligence_map = {
            str(r.get("ip", "")).strip(): r.to_dict()
            for _, r in intelligence.iterrows()
            if str(r.get("ip", "")).strip()
        }

    if not classifications.empty and "ip" in classifications.columns:
        classification_map = {
            str(r.get("ip", "")).strip(): r.to_dict()
            for _, r in classifications.iterrows()
            if str(r.get("ip", "")).strip()
        }

    if not profiles.empty and "mac" in profiles.columns:
        for _, profile in profiles.iterrows():
            mac = str(profile.get("mac", "")).strip().upper()
            if mac:
                profile_map[mac] = profile.to_dict()

    gateway_ip = ""

    if "gateway" in inventory.columns:
        values = inventory["gateway"].astype(str).str.strip()
        values = values[values != ""]
        if not values.empty:
            gateway_ip = values.iloc[0]

    if not gateway_ip:
        gateway_ip = str(inventory.iloc[0]["ip"])

    gateway_rows = inventory[
        inventory["ip"].astype(str).str.strip() == gateway_ip
    ]
    gateway_record = (
        gateway_rows.iloc[-1].to_dict() if not gateway_rows.empty else {}
    )
    gateway_mac = str(gateway_record.get("mac", "")).strip().upper()
    gateway_profile = profile_map.get(gateway_mac, {})
    gateway_intelligence = intelligence_map.get(gateway_ip, {})

    gateway_vendor = str(
        gateway_intelligence.get("vendor", "")
        or gateway_profile.get("vendor", "")
        or gateway_record.get("vendor", "")
    ).strip()

    nodes = [{
        "id": gateway_ip,
        "label": "Gateway",
        "node_type": "gateway",
        "ip": gateway_ip,
        "mac": gateway_mac,
        "vendor": gateway_vendor,
        "status": "gateway",
        "classification": "Default gateway (observed)"
    }]

    edges = []

    for _, row in inventory.iterrows():
        ip = str(row.get("ip", "")).strip()

        if not ip or ip == gateway_ip:
            continue

        mac = str(row.get("mac", "")).strip()
        profile = profile_map.get(mac.upper(), {})

        intelligence_record = intelligence_map.get(ip, {})
        classification_record = classification_map.get(ip, {})

        hostname = str(
            row.get("hostname", "")
            or intelligence_record.get("hostname", "")
            or profile.get("hostname", "")
        ).strip()

        vendor = str(
            intelligence_record.get("vendor", "")
            or profile.get("vendor", "")
            or row.get("vendor", "")
        ).strip()

        classification = str(
            intelligence_record.get("classification", "")
            or classification_record.get("category", "")
            or profile.get("classification", "")
            or row.get("classification", "")
        ).strip()

        if is_network_equipment(classification, hostname):
            node_type = "network_device"
            label = classification or hostname or "Ag ekipmani adayi"
        else:
            node_type = "endpoint"
            label = hostname or classification or "Bilinmeyen cihaz"

        nodes.append({
            "id": ip,
            "label": label,
            "node_type": node_type,
            "ip": ip,
            "mac": mac,
            "vendor": vendor,
            "status": str(row.get("status", "unknown")),
            "classification": classification
        })

        edges.append({
            "source": gateway_ip,
            "target": ip,
            "relation": "same_network",
            "confidence": "context_only"
        })

    overwrite_rows(DATA / "topology_nodes.csv", nodes, node_fields)
    overwrite_rows(DATA / "topology_edges.csv", edges, edge_fields)

    network_count = sum(
        node["node_type"] == "network_device" for node in nodes
    )
    endpoint_count = sum(
        node["node_type"] == "endpoint" for node in nodes
    )

    print("Topoloji yeniden olusturuldu.")
    print("Toplam dugum:", len(nodes))
    print("Gateway: 1")
    print("Ag ekipmani adayi:", network_count)
    print("Uc cihaz:", endpoint_count)
    print("Fiziksel baglantilar dogrulanmadi.")


if __name__ == "__main__":
    run()
