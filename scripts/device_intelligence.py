import re
import pandas as pd
from scripts.common import DATA, ROOT, stamp, overwrite_rows
from scripts.device_fingerprints import resolve_device_fingerprint

REFERENCE = ROOT / "data" / "reference"
OUI_FILES = [
    ("MA-S", REFERENCE / "oui-ma-s.csv"),
    ("MA-M", REFERENCE / "oui-ma-m.csv"),
    ("MA-L", REFERENCE / "oui-ma-l.csv"),
]

def normalize_mac(mac):
    return re.sub(r"[^0-9A-F]", "", str(mac).upper())

def load_oui():
    database = {}
    for registry, path in OUI_FILES:
        if not path.exists():
            print(f"Dosya bulunamadı: {path}")
            continue
        df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        count = 0
        for _, row in df.iterrows():
            prefix = normalize_mac(row.get("Assignment", ""))
            vendor = str(row.get("Organization Name", "")).strip()
            if prefix and vendor:
                database[prefix] = vendor
                count += 1
        print(f"{registry}: {count} kayıt")
    return database

def identify_mac(mac, oui):
    value = normalize_mac(mac)

    if len(value) != 12:
        return "Invalid / unavailable", "", "Invalid MAC"

    first_byte = int(value[:2], 16)

    if first_byte & 1:
        return "Multicast", "", "Multicast address"

    if first_byte & 2:
        return "Locally administered / randomized", "", "IEEE vendor cannot be inferred"

    for size in (9, 7, 6):
        vendor = oui.get(value[:size])
        if vendor:
            return "Globally administered", vendor, "IEEE OUI match"

    return "Globally administered", "", "No IEEE match"

def vendor_intelligence(vendor):
    v = vendor.lower()

    mappings = [
        ("ruijie", "Network equipment manufacturer"),
        ("liteon", "Electronics / wireless module OEM"),
        ("azurewave", "Wireless module manufacturer"),
        ("wnc corporation", "Wireless / networking OEM"),
        ("cloud network technology", "Electronics manufacturing OEM"),
        ("chongqing fugui", "Electronics manufacturing OEM"),
        ("intel", "Computing / semiconductor manufacturer"),
        ("samsung", "Consumer electronics manufacturer"),
        ("apple", "Consumer electronics brand"),
    ]

    for key, role in mappings:
        if key in v:
            return role

    return "Manufacturer role not classified"

def classify_device(hostname, vendor):
    h = hostname.lower()
    v = vendor.lower()
    combined = h + " " + v

    # DNS cihaz adi Ruijie RAP2200E ailesine isaret ediyor.
    # Bu, guclu bir model ailesi tahminidir; yonetim arayuzu
    # veya cihaz uzerinden dogrulanmis fiziksel rol degildir.
    if "rap2200e" in h and "ruijie" in v:
        return "Ruijie RAP2200E access point (hostname-based inference)", 85

    rules = [
        (["printer", "epson", "brother", "canon", "xerox"], "Printer", 90),
        (["router", "gateway", "access point", "mikrotik", "ubiquiti", "zyxel", "tp-link", "netgear"], "Network device", 85),
        (["iphone", "ipad"], "Apple mobile device (possible)", 65),
        (["macbook", "imac"], "Apple computer (possible)", 75),
        (["galaxy", "samsung"], "Samsung device (type uncertain)", 35),
        (["android", "pixel"], "Android device (possible)", 60),
        (["windows", "desktop", "laptop", "thinkpad", "macbook"], "Computer (possible)", 70),
        (["camera", "hikvision", "dahua"], "Camera / surveillance device", 85),
        (["smart tv", "television"], "TV / entertainment device", 80),
    ]

    for keywords, category, confidence in rules:
        if any(word in combined for word in keywords):
            return category, confidence

    if "ruijie" in v:
        return "Network equipment (manufacturer-based inference)", 65

    return "Unknown / unclassified", 0

def classify_infrastructure_role(hostname, vendor):
    """Classify infrastructure roles only from explicit device evidence.

    A manufacturer OUI identifies a network-equipment vendor at most; it does
    not prove that an observed endpoint is a router, AP, switch, or controller.
    """
    host = str(hostname or "").strip().casefold()
    maker = str(vendor or "").strip().casefold()

    if "rap2200e" in host and "ruijie" in maker:
        return "Access Point", 85, "hostname_model_family_inference"

    rules = [
        (r"\b(router|gateway)\b", "Router / Gateway", 85),
        (r"access[\s_-]?point|\b(wap|wireless ap)\b", "Access Point", 85),
        (r"\b(switch|managed-switch)\b", "Switch", 85),
        (r"\b(repeater|range extender)\b", "Repeater", 85),
        (r"\b(mesh|mesh node)\b", "Mesh Node", 80),
        (r"\b(firewall)\b", "Firewall", 85),
        (r"\b(controller|wireless controller)\b", "Controller", 85),
    ]
    for pattern, role, confidence in rules:
        if re.search(pattern, host):
            return role, confidence, "hostname_role_hint"

    infrastructure_vendors = (
        "ruijie", "ubiquiti", "mikrotik", "cisco", "huawei",
        "tp-link", "zyxel", "netgear", "aruba", "juniper",
    )
    if any(name in maker for name in infrastructure_vendors):
        return "Network equipment candidate", 30, "vendor_only"

    return "Unknown", 0, "insufficient_evidence"


def run():
    source = DATA / "device_inventory.csv"
    if not source.exists():
        print("device_inventory.csv bulunamadı.")
        return []

    df = pd.read_csv(source, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    oui = load_oui()
    rows = []

    for _, record in df.iterrows():
        mac_type, vendor, mac_evidence = identify_mac(record.get("mac", ""), oui)
        hostname = record.get("hostname", "")
        vendor_role = vendor_intelligence(vendor)
        category, device_confidence = classify_device(hostname, vendor)
        device_role, role_confidence, role_evidence_type = classify_infrastructure_role(hostname, vendor)
        fingerprint = resolve_device_fingerprint(record.to_dict())

        vendor_confidence = 95 if vendor else 0
        if mac_type == "Locally administered / randomized":
            vendor_confidence = 0

        evidence = [mac_evidence]
        if vendor:
            evidence.append("IEEE vendor: " + vendor)
        if vendor_role != "Manufacturer role not classified":
            evidence.append("Vendor role: " + vendor_role)
        if hostname:
            evidence.append("Hostname available")
        if category != "Unknown / unclassified":
            evidence.append("Device category is heuristic")

        rows.append({
            "timestamp": stamp(),
            "ip": record.get("ip", ""),
            "mac": record.get("mac", ""),
            "hostname": hostname,
            "vendor": vendor,
            "mac_type": mac_type,
            "vendor_role": vendor_role,
            "device_role": device_role,
            "role_confidence": role_confidence,
            "role_evidence_type": role_evidence_type,
            **fingerprint,
            "classification": category,
            "vendor_confidence": vendor_confidence,
            "device_confidence": device_confidence,
            "evidence": "; ".join(evidence)
        })

    fields = [
        "timestamp", "ip", "mac", "hostname", "vendor", "mac_type",
        "vendor_role", "device_role", "role_confidence",
        "role_evidence_type", "model", "model_confidence", "model_status",
        "model_source", "firmware_version", "firmware_confidence",
        "firmware_status", "firmware_source", "fingerprint_evidence",
        "classification", "vendor_confidence",
        "device_confidence", "evidence"
    ]
    overwrite_rows(DATA / "device_intelligence.csv", rows, fields)

    print(f"Cihaz analizi tamamlandı: {len(rows)} kayıt")
    print(f"IEEE veritabanı: {len(oui)} kayıt")
    return rows

if __name__ == "__main__":
    run()
