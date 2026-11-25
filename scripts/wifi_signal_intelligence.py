"""Collect and persist the active Windows Wi-Fi interface signal snapshot."""
from __future__ import annotations

import csv
import re
import subprocess
from datetime import datetime

from scripts.common import DATA, overwrite_rows, write_rows

HISTORY = DATA / "wifi_signal_history.csv"
STATUS = DATA / "wifi_signal_status.csv"
FIELDS = [
    "observed_at", "ssid", "bssid", "band", "channel",
    "radio_type", "signal_percent", "rssi_dbm",
    "receive_mbps", "transmit_mbps", "quality", "change_percent",
]
ALIASES = {
    "ssid": ("ssid", "ağ adı", "ag adi"),
    "bssid": ("ap bssid", "bssid", "erişim noktası bssid", "erisim noktasi bssid"),
    "signal": ("signal", "sinyal"),
    "channel": ("channel", "kanal"),
    "radio_type": ("radio type", "radyo türü", "radyo turu"),
    "band": ("band", "bant", "frequency band", "frekans bandı", "frekans bandi"),
    "rssi": ("rssi", "signal strength", "sinyal gücü", "sinyal gucu"),
    "receive_mbps": ("receive rate (mbps)", "alım hızı (mbps)", "alim hizi (mbps)", "alma hızı (mbps)", "alma hizi (mbps)"),
    "transmit_mbps": ("transmit rate (mbps)", "iletim hızı (mbps)", "iletim hizi (mbps)", "gönderme hızı (mbps)", "gonderme hizi (mbps)"),
    "state": ("state", "durum"),
}


def _normalise_key(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _read_blocks(output: str) -> list[dict[str, str]]:
    blocks = []
    current = {}
    for line in output.splitlines():
        if not line.strip():
            if current:
                blocks.append(current)
                current = {}
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key, value = _normalise_key(key), value.strip()
        if key and value:
            current[key] = value
    if current:
        blocks.append(current)
    return blocks


def _value(block: dict[str, str], field: str) -> str:
    aliases = {_normalise_key(alias) for alias in ALIASES[field]}
    return next((value for key, value in block.items() if key in aliases), "")


def parse_interfaces_output(output: str) -> dict[str, str]:
    """Parse English/Turkish netsh output; pure function for fixture-based tests."""
    candidates = []
    for block in _read_blocks(output):
        if not _value(block, "signal"):
            continue
        state = _value(block, "state").casefold()
        if state and state not in {"connected", "bağlı", "bagli"}:
            continue
        candidates.append((bool(state), block))
    if not candidates:
        raise RuntimeError(
            "Aktif Wi-Fi bağlantısı veya sinyal bilgisi bulunamadı. "
            "Wi-Fi bağlantınızı kontrol edin."
        )
    candidates.sort(key=lambda item: item[0], reverse=True)
    block = candidates[0][1]

    signal_match = re.search(r"(?<![-\d])(\d{1,3})\s*%", _value(block, "signal"))
    if not signal_match:
        raise RuntimeError("Wi-Fi sinyal yüzdesi okunamadı.")
    signal_percent = int(signal_match.group())
    if not 0 <= signal_percent <= 100:
        raise RuntimeError("Wi-Fi sinyal yüzdesi 0-100 aralığında değil.")
    rssi_match = re.search(r"-?\d{1,3}", _value(block, "rssi"))
    channel_match = re.search(r"\d{1,3}", _value(block, "channel"))
    return {
        "ssid": _value(block, "ssid"),
        "bssid": _value(block, "bssid").upper().replace("-", ":"),
        "band": _value(block, "band"),
        "channel": channel_match.group() if channel_match else "",
        "radio_type": _value(block, "radio_type"),
        "signal_percent": str(signal_percent),
        "rssi_dbm": rssi_match.group() if rssi_match else "",
        "receive_mbps": _value(block, "receive_mbps"),
        "transmit_mbps": _value(block, "transmit_mbps"),
    }


def _quality(signal_percent: int) -> str:
    if signal_percent >= 80:
        return "Excellent"
    if signal_percent >= 60:
        return "Good"
    if signal_percent >= 40:
        return "Fair"
    return "Weak"


def run():
    """Read one active-interface snapshot and persist history plus latest status."""
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=15, check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("netsh komutu bulunamadı; bu modül Windows gerektirir.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Wi-Fi arayüz bilgisi alınırken zaman aşımı oluştu.") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            "Windows Wi-Fi arayüz bilgisi alınamadı."
            + (f" Ayrıntı: {detail[:240]}" if detail else "")
        )

    parsed = parse_interfaces_output(result.stdout or "")
    signal_percent = int(parsed["signal_percent"])
    previous_rows = []
    if HISTORY.exists() and HISTORY.stat().st_size:
        with HISTORY.open("r", encoding="utf-8-sig", newline="") as handle:
            previous_rows = list(csv.DictReader(handle))
    previous = next(
        (row for row in reversed(previous_rows)
         if parsed["bssid"] and row.get("bssid", "").casefold() == parsed["bssid"].casefold()),
        None,
    )
    change = ""
    if previous:
        try:
            change = signal_percent - int(previous["signal_percent"])
        except (KeyError, TypeError, ValueError):
            pass
    record = {
        "observed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        **parsed,
        "quality": _quality(signal_percent),
        "change_percent": change,
    }
    write_rows(HISTORY, [record], FIELDS)
    overwrite_rows(STATUS, [record], FIELDS)
    print(
        f"Wi-Fi signal recorded: {record['ssid'] or '(hidden SSID)'} | "
        f"{signal_percent}% | {record['rssi_dbm'] or 'RSSI n/a'} dBm | "
        f"Channel {record['channel'] or 'n/a'}",
        flush=True,
    )
    return record


if __name__ == "__main__":
    run()
