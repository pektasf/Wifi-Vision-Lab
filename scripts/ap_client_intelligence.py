import csv
import subprocess
from pathlib import Path
from datetime import datetime

DATA = Path("data/processed")
OUTPUT = DATA / "ap_client_relationships.csv"

FIELDS = [
    "observed_at", "client_mac", "client_ip", "client_hostname",
    "ap_bssid", "ssid", "source", "evidence_type",
    "confidence", "verification_status"
]

def read_rows(path):
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []

def run():
    DATA.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["netsh", "wlan", "show", "interfaces"],
        capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=15
    )

    values = {}
    for line in result.stdout.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip().lower()] = value.strip()

    state = values.get("state", "").lower()
    bssid = values.get("ap bssid", "").lower()
    ssid = values.get("ssid", "")

    if state != "connected" or not bssid:
        print("AP-client: Aktif Wi-Fi ba?lant?s? bulunamad?.")
        return

    inventory = read_rows(DATA / "device_inventory.csv")
    client_mac = values.get("physical address", "").lower()

    client_ip = ""
    client_hostname = ""

    for row in inventory:
        mac = (row.get("mac") or row.get("mac_address") or "").lower()
        if mac and mac == client_mac:
            client_ip = row.get("ip", row.get("ip_address", ""))
            client_hostname = row.get("hostname", "")
            break

    record = {
        "observed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "client_mac": client_mac,
        "client_ip": client_ip,
        "client_hostname": client_hostname,
        "ap_bssid": bssid,
        "ssid": ssid,
        "source": "windows_wlan",
        "evidence_type": "direct_association",
        "confidence": "verified",
        "verification_status": "verified"
    }

    existing = read_rows(OUTPUT)
    existing.append(record)

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(existing[-10000:])

    print(
        f"AP-client ili?kisi do?ruland?: "
        f"{client_mac} -> {bssid} ({ssid})"
    )
    print(f"?li?ki ge?mi?i: {OUTPUT}")
