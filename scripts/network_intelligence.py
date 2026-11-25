import csv
from pathlib import Path
from datetime import datetime

DATA = Path("data/processed")

TOKENS = {
    "router": ["router", "gateway"],
    "access_point": ["access point", "wireless ap", "wlan", "wap"],
    "switch": ["switch"],
    "firewall": ["firewall"],
    "controller": ["controller", "wireless controller"],
    "network_device": ["network device", "network equipment"]
}

FIELDS = [
    "timestamp", "ip", "mac", "hostname",
    "category", "vendor", "vendor_role",
    "confidence", "candidate_type",
    "evidence", "verification_status"
]


def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def run():
    inventory = read_csv(DATA / "device_inventory.csv")
    classifications = read_csv(DATA / "device_classification.csv")

    by_ip = {x.get("ip", ""): x for x in inventory}
    results = []

    for item in classifications:
        role = str(item.get("vendor_role", "")).lower()
        category = str(item.get("category", "")).lower()
        description = role + " " + category

        matched = []
        for candidate, words in TOKENS.items():
            if any(word in description for word in words):
                matched.append(candidate)

        if not matched:
            continue

        ip = item.get("ip", "")
        device = by_ip.get(ip, {})

        results.append({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "ip": ip,
            "mac": device.get("mac", ""),
            "hostname": device.get("hostname", ""),
            "category": item.get("category", ""),
            "vendor": item.get("vendor", ""),
            "vendor_role": item.get("vendor_role", ""),
            "confidence": item.get("confidence", ""),
            "candidate_type": ";".join(matched),
            "evidence": "Device classification",
            "verification_status": "candidate_unverified"
        })

    output = DATA / "infrastructure_candidates.csv"
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(results)

    print(f"Altyapi cihaz adaylari: {len(results)}")
    print(f"Dosya: {output}")


if __name__ == "__main__":
    run()
