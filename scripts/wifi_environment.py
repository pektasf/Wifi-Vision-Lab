from pathlib import Path
from datetime import datetime
import csv
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
DATA.mkdir(parents=True, exist_ok=True)

MAC_PATTERN = r"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}"


def run_command(args):
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20
        )
        return result.stdout
    except Exception as exc:
        print(f"Komut calistirilamadi: {exc}")
        return ""


def parse_connected():
    output = run_command(["netsh", "wlan", "show", "interfaces"])

    data = {
        "ssid": "",
        "bssid": "",
        "signal": "",
        "channel": "",
        "radio_type": ""
    }

    for line in output.splitlines():
        stripped = line.strip()

        if re.match(r"SSID\s*:", stripped, re.I):
            data["ssid"] = stripped.split(":", 1)[1].strip()

        elif re.match(r"(?:AP\s+)?BSSID\s*:", stripped, re.I):
            match = re.search(MAC_PATTERN, stripped)
            if match:
                data["bssid"] = match.group(0).upper().replace("-", ":")

        elif re.match(r"Signal\s*:", stripped, re.I) or re.match(
            r"Sinyal\s*:", stripped, re.I
        ):
            match = re.search(r"\d+\s*%", stripped)
            if match:
                data["signal"] = match.group(0).replace(" ", "")

        elif re.match(r"Channel\s*:", stripped, re.I) or re.match(
            r"Kanal\s*:", stripped, re.I
        ):
            match = re.search(r"\d+", stripped)
            if match:
                data["channel"] = match.group(0)

        elif re.match(r"Radio type\s*:", stripped, re.I) or re.match(
            r"Radyo türü\s*:", stripped, re.I
        ):
            data["radio_type"] = stripped.split(":", 1)[1].strip()

    return data



def parse_visible_access_points():
    output = run_command([
        "netsh", "wlan", "show", "networks", "mode=bssid"
    ])

    access_points = []
    current_ssid = ""
    current_auth = ""
    current_encryption = ""
    current_point = None

    for line in output.splitlines():
        stripped = line.strip()

        ssid_match = re.match(r"SSID\s+\d+\s*:\s*(.*)", stripped, re.I)
        if ssid_match:
            current_ssid = ssid_match.group(1).strip()
            current_auth = ""
            current_encryption = ""
            current_point = None
            continue

        auth_match = re.match(
            r"Authentication\s*:\s*(.*)|Kimlik do?rulama\s*:\s*(.*)",
            stripped, re.I
        )
        if auth_match:
            current_auth = next(
                (v for v in auth_match.groups() if v is not None), ""
            ).strip()
            continue

        encryption_match = re.match(
            r"Encryption\s*:\s*(.*)|Sifreleme\s*:\s*(.*)",
            stripped, re.I
        )
        if encryption_match:
            current_encryption = next(
                (v for v in encryption_match.groups() if v is not None), ""
            ).strip()
            continue

        bssid_match = re.match(r"BSSID\s+\d+\s*:\s*(.*)", stripped, re.I)
        if bssid_match:
            mac_match = re.search(MAC_PATTERN, bssid_match.group(1))
            if not mac_match:
                current_point = None
                continue

            bssid = mac_match.group(0).upper().replace("-", ":")
            current_point = {
                "ssid": current_ssid,
                "bssid": bssid,
                "signal": "",
                "channel": "",
                "authentication": current_auth,
                "encryption": current_encryption
            }
            access_points.append(current_point)
            continue

        if current_point is None:
            continue

        signal_match = re.match(
            r"(?:Signal|Sinyal)\s*:\s*(\d+)\s*%", stripped, re.I
        )
        if signal_match:
            current_point["signal"] = signal_match.group(1)
            continue

        channel_match = re.match(
            r"(?:Channel|Kanal)\s*:\s*(\d+)", stripped, re.I
        )
        if channel_match:
            current_point["channel"] = channel_match.group(1)

    return access_points


def save_csv(filename, rows, fields):
    path = DATA / filename

    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run():
    print("\\nWi-Fi erisim noktasi kesfi basliyor...\\n")

    connected = parse_connected()
    access_points = parse_visible_access_points()

    # BSSID arayuz bilgisinde yoksa tarama sonuclarindan eslestir.
    bssid_source = "interface_direct"

    if not connected["bssid"]:
        same_ssid = [
            point for point in access_points
            if point["ssid"].casefold() == connected["ssid"].casefold()
            and connected["ssid"]
        ]

        if len(same_ssid) == 1:
            connected["bssid"] = same_ssid[0]["bssid"]
            bssid_source = "unique_ssid_match"

        elif len(same_ssid) > 1 and connected["channel"]:
            same_channel = [
                point for point in same_ssid
                if point["channel"] == connected["channel"]
            ]

            if len(same_channel) == 1:
                connected["bssid"] = same_channel[0]["bssid"]
                bssid_source = "unique_ssid_channel_match"
            else:
                bssid_source = "ambiguous"
        else:
            bssid_source = "not_found"

    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")

    for point in access_points:
        point["observed_at"] = timestamp
        point["connected_to_this_pc"] = (
            point["bssid"] == connected["bssid"]
            if connected["bssid"] else False
        )

    save_csv(
        "wifi_access_points.csv",
        access_points,
        [
            "ssid", "bssid", "signal", "channel",
            "authentication", "encryption",
            "radio_type", "band", "connected_stations",
            "channel_utilization",
            "connected_to_this_pc", "observed_at"
        ]
    )

    connected["bssid_source"] = bssid_source

    save_csv(
        "wifi_connection.csv",
        [{**connected, "observed_at": timestamp}],
        [
            "ssid", "bssid", "signal", "channel",
            "radio_type", "bssid_source", "observed_at"
        ]
    )

    print("BU BILGISAYARIN BAGLANTISI")
    print("--------------------------")
    print("SSID:", connected["ssid"] or "Bulunamadi")
    print("BSSID:", connected["bssid"] or "Bulunamadi")
    print("BSSID kaynagi:", bssid_source)
    print("Sinyal:", connected["signal"] or "Bulunamadi")
    print("Kanal:", connected["channel"] or "Bulunamadi")

    print("\\nGORULEBILEN ERISIM NOKTALARI")
    print("----------------------------")

    for point in access_points:
        marker = (
            " [BU BILGISAYARIN BAGLI OLDUGU AP]"
            if point["connected_to_this_pc"] else ""
        )
        print(
            f'{point["ssid"] or "(Gizli SSID)"} | '
            f'{point["bssid"]} | '
            f'Sinyal: {point["signal"] or "?"} | '
            f'Kanal: {point["channel"] or "?"}{marker}'
        )

    print(f"\\nToplam BSSID: {len(access_points)}")
    print("CSV dosyalari kaydedildi.")


if __name__ == "__main__":
    run()
