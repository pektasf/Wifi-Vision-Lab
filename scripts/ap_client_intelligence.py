"""Capture the local Windows WLAN interface's current AP association."""
import csv
import re
import subprocess
from datetime import datetime

from scripts.common import DATA, overwrite_rows
OUTPUT = DATA / "ap_client_relationships.csv"

FIELDS = [
    "observed_at", "client_mac", "client_ip", "client_hostname",
    "ap_bssid", "ssid", "source", "evidence_type",
    "confidence", "verification_status"
]
MAC_PATTERN = re.compile(r"^(?:[0-9A-F]{2}[:-]){5}[0-9A-F]{2}$")


def normalize_mac(value):
    normalized = str(value or "").strip().upper().replace("-", ":")
    return normalized if MAC_PATTERN.fullmatch(normalized) else ""


def read_rows(path):
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except (OSError, UnicodeError, csv.Error):
        return []


def run():
    DATA.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=15
        )
    except FileNotFoundError:
        print("AP-client: Windows netsh komutu bulunamadi.")
        return
    except subprocess.TimeoutExpired:
        print("AP-client: WLAN arayuzu sorgusu zaman asimina ugradi.")
        return
    except OSError as exc:
        print(f"AP-client: WLAN arayuzu sorgulanamadi: {exc}")
        return

    if result.returncode:
        detail = result.stderr.strip() or "netsh basarisiz sonuc dondurdu."
        print(f"AP-client: WLAN bilgisi okunamadi: {detail[:250]}")
        return

    values = {}
    for line in result.stdout.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip().lower()] = value.strip()

    state = values.get("state", "").lower()
    bssid = normalize_mac(values.get("ap bssid", ""))
    client_mac = normalize_mac(values.get("physical address", ""))
    ssid = values.get("ssid", "")

    if state != "connected" or not bssid or not client_mac:
        print(
            "AP-client: Dogrudan iliski kurulamadi. "
            "Baglanti durumu, istemci MAC ve AP BSSID gerekli."
        )
        return

    inventory = read_rows(DATA / "device_inventory.csv")
    client_ip = ""
    client_hostname = ""
    for row in inventory:
        mac = normalize_mac(row.get("mac") or row.get("mac_address") or "")
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
    overwrite_rows(OUTPUT, existing[-10000:], FIELDS)

    print(f"AP-client iliskisi dogrulandi: {client_mac} -> {bssid} ({ssid})")
    print(f"Iliski gecmisi: {OUTPUT}")


if __name__ == "__main__":
    run()
