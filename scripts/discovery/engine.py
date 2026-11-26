import hashlib
import json

from scripts.common import DATA, stamp, overwrite_rows
from scripts.discovery.registry import get_adapters


FIELDS = [
    "observation_id", "observed_at", "source", "network_id",
    "ip", "mac", "hostname", "status", "gateway", "adapter",
    "evidence", "raw_data"
]

SOURCE_FIELDS = ["source", "status", "devices_found", "checked_at", "error"]

DEVICE_FIELDS = [
    "device_id", "identity_basis", "network_id", "mac",
    "ips", "hostnames", "sources", "source_count",
    "statuses", "last_seen"
]


def build_observation_identity_keys(observations):
    """Link IP-only observations only when one MAC is unambiguous on that network."""
    macs_by_network_ip = {}

    for observation in observations:
        network = str(observation.get("network_id", "")).strip()
        mac = str(observation.get("mac", "")).strip().upper()
        ip = str(observation.get("ip", "")).strip()
        if network and mac and ip:
            macs_by_network_ip.setdefault((network, ip), set()).add(mac)

    identity_keys = []
    for observation in observations:
        network = str(observation.get("network_id", "")).strip()
        mac = str(observation.get("mac", "")).strip().upper()
        ip = str(observation.get("ip", "")).strip()

        if mac:
            identity_keys.append(f"{network}|mac|{mac}")
            continue

        matching_macs = (
            macs_by_network_ip.get((network, ip), set()) if ip else set()
        )
        if len(matching_macs) == 1:
            identity_keys.append(f"{network}|mac|{next(iter(matching_macs))}")
        elif ip:
            identity_keys.append(f"{network}|ip|{ip}")
        else:
            identity_keys.append("")

    return identity_keys


def build_device_profiles(observations):
    grouped = {}
    identity_keys = build_observation_identity_keys(observations)

    for observation, identity in zip(observations, identity_keys):
        network = str(observation.get("network_id", "")).strip()
        ip = str(observation.get("ip", "")).strip()

        if not identity:
            continue

        identity_basis = "mac" if "|mac|" in identity else "network_ip"
        device_mac = identity.rsplit("|mac|", 1)[-1] if identity_basis == "mac" else ""
        device_id = hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()[:20]

        if device_id not in grouped:
            grouped[device_id] = {
                "device_id": device_id,
                "identity_basis": identity_basis,
                "network_id": network,
                "mac": device_mac,
                "ips": set(),
                "hostnames": set(),
                "sources": set(),
                "statuses": set(),
                "last_seen": ""
            }

        item = grouped[device_id]

        if ip:
            item["ips"].add(ip)

        if observation.get("hostname"):
            item["hostnames"].add(observation["hostname"])

        if observation.get("source"):
            item["sources"].add(observation["source"])

        if observation.get("status"):
            item["statuses"].add(observation["status"])

        observed_at = observation.get("observed_at", "")
        if observed_at > item["last_seen"]:
            item["last_seen"] = observed_at

    rows = []

    for item in grouped.values():
        rows.append({
            "device_id": item["device_id"],
            "identity_basis": item["identity_basis"],
            "network_id": item["network_id"],
            "mac": item["mac"],
            "ips": ";".join(sorted(item["ips"])),
            "hostnames": ";".join(sorted(item["hostnames"])),
            "sources": ";".join(sorted(item["sources"])),
            "source_count": len(item["sources"]),
            "statuses": ";".join(sorted(item["statuses"])),
            "last_seen": item["last_seen"]
        })

    return rows


class DiscoveryEngine:
    def __init__(self, adapters):
        self.adapters = adapters

    def run(self):
        observations = []
        source_results = []
        primary_network = {}
        primary_devices = []

        for adapter in self.adapters:
            source = getattr(adapter, "source", adapter.__class__.__name__)

            try:
                network, devices = adapter.collect()

                if not primary_network:
                    primary_network = network
                    primary_devices = devices

                for device in devices:
                    raw = dict(device)
                    ip = raw.get("ip", "")
                    mac = raw.get("mac", "")
                    subnet = raw.get("subnet", network.get("network", ""))

                    identity = mac or ip or json.dumps(raw, sort_keys=True)
                    observation_id = hashlib.sha256(
                        f"{source}|{subnet}|{identity}".encode("utf-8")
                    ).hexdigest()[:20]

                    observations.append({
                        "observation_id": observation_id,
                        "observed_at": raw.get("timestamp", ""),
                        "source": source,
                        "network_id": subnet,
                        "ip": ip,
                        "mac": mac,
                        "hostname": raw.get("hostname", ""),
                        "status": raw.get("status", ""),
                        "gateway": raw.get("gateway", network.get("gateway", "")),
                        "adapter": raw.get("adapter", network.get("adapter", "")),
                        "evidence": "Windows local discovery",
                        "raw_data": json.dumps(raw, ensure_ascii=False)
                    })

                source_results.append({
                    "source": source,
                    "status": "success",
                    "devices_found": len(devices),
                    "checked_at": stamp(),
                    "error": ""
                })

            except Exception as exc:
                source_results.append({
                    "source": source,
                    "status": "failed",
                    "devices_found": 0,
                    "checked_at": stamp(),
                    "error": str(exc)
                })
                print(f"Discovery adapter failed ({source}): {exc}", flush=True)

        overwrite_rows(DATA / "discovery_sources.csv", source_results, SOURCE_FIELDS)

        if observations:
            overwrite_rows(DATA / "discovery_observations.csv", observations, FIELDS)

        profiles = build_device_profiles(observations)

        overwrite_rows(
            DATA / "discovery_devices.csv",
            profiles,
            DEVICE_FIELDS
        )

        inventory_rows = build_inventory_rows(observations, profiles)

        overwrite_rows(
            DATA / "device_inventory.csv",
            inventory_rows,
            [
                "timestamp", "ip", "mac", "hostname",
                "status", "gateway", "adapter", "subnet"
            ]
        )

        print(
            f"Unified inventory updated: {len(inventory_rows)} devices.",
            flush=True
        )

        if not primary_network:
            raise RuntimeError("No discovery adapter completed successfully.")

        print(
            f"Discovery observations: {len(observations)} | "
            f"Consolidated device profiles: {len(profiles)}",
            flush=True
        )

        return primary_network, primary_devices


def build_inventory_rows(observations, profiles):
    grouped = {}
    identity_keys = build_observation_identity_keys(observations)

    for observation, identity in zip(observations, identity_keys):
        if not identity:
            continue

        device_id = hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()[:20]

        grouped.setdefault(device_id, []).append(observation)

    rows = []

    for profile in profiles:
        matches = grouped.get(profile["device_id"], [])
        if not matches:
            continue

        ips = sorted({
            item.get("ip", "") for item in matches if item.get("ip")
        })
        hostnames = sorted({
            item.get("hostname", "") for item in matches
            if item.get("hostname")
        })
        statuses = sorted({
            item.get("status", "") for item in matches
            if item.get("status")
        })

        rows.append({
            "timestamp": profile["last_seen"],
            "ip": ips[0] if ips else "",
            "mac": profile["mac"],
            "hostname": hostnames[0] if hostnames else "",
            "status": ";".join(statuses),
            "gateway": next(
                (item.get("gateway", "") for item in matches if item.get("gateway")),
                ""
            ),
            "adapter": next(
                (item.get("adapter", "") for item in matches if item.get("adapter")),
                ""
            ),
            "subnet": profile["network_id"]
        })

    return rows


def run():
    return DiscoveryEngine(get_adapters()).run()
