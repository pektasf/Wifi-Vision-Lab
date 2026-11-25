import csv
import re
import subprocess
from pathlib import Path
from datetime import datetime

DATA = Path("data/processed")
HISTORY = DATA / "wifi_signal_history.csv"
STATUS = DATA / "wifi_signal_status.csv"

FIELDS = [
    "observed_at", "ssid", "bssid", "band", "channel",
    "radio_type", "signal_percent", "rssi_dbm",
    "receive_mbps", "transmit_mbps", "quality", "change_percent"
]

def run():
    DATA.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["netsh", "wlan", "show", "interfaces"],
        capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=15
    )
    output = result.stdout or ""

    values = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip().lower()] = value.strip()

    def get(*keys):
        for key in keys:
            value = values.get(key.lower())
            if value:
                return value
        return ""

    ssid = get("ssid")
    bssid = get("ap bssid", "bssid")
    signal = get("signal")
    rssi = get("rssi")
    channel = get("channel")

    if not ssid or not bssid or not signal:
        raise RuntimeError("Aktif Wi-Fi ba?lant?s? veya sinyal bilgisi bulunamad?.")

    percent_match = re.search(r"\d+", signal)
    signal_percent = int(percent_match.group()) if percent_match else 0

    rssi_match = re.search(r"-?\d+", rssi)
    rssi_dbm = int(rssi_match.group()) if rssi_match else ""

    quality = (
        "Excellent" if signal_percent >= 80 else
        "Good" if signal_percent >= 60 else
        "Fair" if signal_percent >= 40 else
        "Weak"
    )

    previous = None
    if HISTORY.exists():
        with HISTORY.open("r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
            for row in reversed(rows):
                if row.get("bssid", "").lower() == bssid.lower():
                    previous = row
                    break

    change = ""
    if previous:
        try:
            change = signal_percent - int(previous["signal_percent"])
        except (ValueError, KeyError):
            pass

    record = {
        "observed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "ssid": ssid,
        "bssid": bssid,
        "band": get("band"),
        "channel": channel,
        "radio_type": get("radio type"),
        "signal_percent": signal_percent,
        "rssi_dbm": rssi_dbm,
        "receive_mbps": get("receive rate (Mbps)"),
        "transmit_mbps": get("transmit rate (Mbps)"),
        "quality": quality,
        "change_percent": change
    }

    write_header = not HISTORY.exists() or HISTORY.stat().st_size == 0
    with HISTORY.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(record)

    with STATUS.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(record)

    print(
        f"Wi-Fi signal recorded: {ssid} | {signal_percent}% | "
        f"{rssi_dbm} dBm | Channel {channel}"
    )

if __name__ == "__main__":
    run()
