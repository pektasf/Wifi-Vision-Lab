"""Capture the local Windows WLAN interface's current AP association."""
import csv
import re
import subprocess
import unicodedata
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


def _normalize_label(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", value).strip().casefold()


def parse_wlan_interface_output(output):
    """Parse English and Turkish netsh output; return only direct associations."""
    values = {}
    aliases = {
        "state": "state",
        "durum": "state",
        "physical address": "client_mac",
        "physical adres": "client_mac",
        "fiziksel adres": "client_mac",
        "mac adresi": "client_mac",
        "ap bssid": "ap_bssid",
        "bssid": "ap_bssid",
        "ssid": "ssid",
    }

    for line in str(output or "").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized_key = _normalize_label(key)
        target = aliases.get(normalized_key)
        if target and value.strip():
            # Prefer an explicit AP BSSID label over a generic BSSID label.
            if target not in values or normalized_key == "ap bssid":
                values[target] = value.strip()

    state = _normalize_label(values.get("state", ""))
    connected_states = {"connected", "bagli", "baglandi", "connected."}
    if state not in connected_states:
        return None

    client_mac = normalize_mac(values.get("client_mac", ""))
    ap_bssid = normalize_mac(values.get("ap_bssid", ""))
    if not client_mac or not ap_bssid:
        return None

    return {
        "client_mac": client_mac,
        "ap_bssid": ap_bssid,
        "ssid": values.get("ssid", ""),
    }


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

    association = parse_wlan_interface_output(result.stdout)
    if not association:
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
        if mac and mac == association["client_mac"]:
            client_ip = row.get("ip", row.get("ip_address", ""))
            client_hostname = row.get("hostname", "")
            break

    record = {
        "observed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        **association,
        "client_ip": client_ip,
        "client_hostname": client_hostname,
        "source": "windows_wlan",
        "evidence_type": "direct_association",
        "confidence": "verified",
        "verification_status": "verified"
    }

    existing = read_rows(OUTPUT)
    existing.append(record)
    overwrite_rows(OUTPUT, existing[-10000:], FIELDS)

    print(
        f"AP-client iliskisi dogrulandi: "
        f"{association['client_mac']} -> {association['ap_bssid']} "
        f"({association['ssid']})"
    )
    print(f"Iliski gecmisi: {OUTPUT}")


if __name__ == "__main__":
    run()
