"""Normalize authorized Kismet Wi-Fi device exports as separate evidence."""

import json
from datetime import datetime, timezone

from scripts.discovery.identity_signals import normalize_mac, is_locally_administered_mac

KISMET_WIRELESS_FIELDS = [
    "imported_at", "observed_at", "source", "device_key", "mac",
    "device_type", "phy", "name", "manufacturer", "last_bssid",
    "channel", "frequency_mhz", "signal_dbm", "packets",
    "randomized_mac", "mac_address_type", "evidence_status",
]
MAX_KISMET_BYTES = 25 * 1024 * 1024
MAX_KISMET_RECORDS = 100000


def _first(record, *keys):
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return ""


def _as_bool(value):
    if value is True or value == 1:
        return True
    if value is False or value == 0:
        return False
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "yes", "1", "on"}:
            return True
        if normalized in {"false", "no", "0", "off"}:
            return False
    return None


def _as_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if number != number or number in (float("inf"), float("-inf")):
        return ""
    return str(int(number)) if number.is_integer() else str(number)


def _timestamp(value):
    if value in (None, ""):
        return ""
    try:
        number = float(value)
        if number > 0:
            return datetime.fromtimestamp(number, timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        pass
    return str(value).strip()


def _records_from_text(text):
    try:
        payload = json.loads(text)
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("devices", "records", "results"):
                if isinstance(payload.get(key), list):
                    return payload[key]
            return [payload]
    except json.JSONDecodeError:
        pass

    records = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Kismet EKJSON satır {line_number} okunamadı: {exc.msg}"
            ) from exc
        if isinstance(record, dict):
            records.append(record)
        if len(records) > MAX_KISMET_RECORDS:
            raise ValueError("Kismet kaydı izin verilen sınırı aşıyor.")
    return records


def normalize_kismet_export(content, imported_at=""):
    """Accept Kismet JSON/EKJSON exports; never merge randomized identities."""
    if isinstance(content, bytes):
        if len(content) > MAX_KISMET_BYTES:
            raise ValueError("Kismet dosyası 25 MB sınırını aşıyor.")
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Kismet dışa aktarımı UTF-8 olmalıdır.") from exc
    else:
        text = str(content or "")
        if len(text.encode("utf-8")) > MAX_KISMET_BYTES:
            raise ValueError("Kismet dosyası 25 MB sınırını aşıyor.")

    records = _records_from_text(text)
    if len(records) > MAX_KISMET_RECORDS:
        raise ValueError("Kismet kaydı izin verilen sınırı aşıyor.")

    rows = []
    for record in records:
        if not isinstance(record, dict):
            continue
        phy = str(_first(
            record, "kismet.device.base.phyname", "phyname", "phy"
        )).strip()
        device_type = str(_first(
            record, "kismet.device.base.type", "type", "device_type"
        )).strip()
        wifi_record = (
            phy.casefold() in {"ieee802.11", "802.11", "wifi", "wi-fi"}
            or "wi-fi" in device_type.casefold()
            or "wifi" in device_type.casefold()
        )
        if not wifi_record:
            continue

        mac = normalize_mac(_first(
            record, "kismet.device.base.macaddr", "macaddr", "mac"
        ))
        if not mac:
            continue

        explicit_random = _as_bool(_first(
            record, "dot11.device.randomized_mac", "randomized_mac"
        ))
        laa = is_locally_administered_mac(mac)
        randomized = explicit_random if explicit_random is not None else (True if laa else None)
        address_type = "locally_administered" if laa else "universally_administered"

        rows.append({
            "imported_at": imported_at,
            "observed_at": _timestamp(_first(
                record, "kismet.device.base.last_time", "last_time"
            )),
            "source": "kismet_import",
            "device_key": str(_first(
                record, "kismet.device.base.key", "key", "device_key"
            )).strip(),
            "mac": mac,
            "device_type": device_type,
            "phy": phy or "IEEE802.11",
            "name": str(_first(
                record, "kismet.device.base.name", "name"
            )).strip(),
            "manufacturer": str(_first(
                record, "kismet.device.base.manuf", "manuf", "manufacturer"
            )).strip(),
            "last_bssid": normalize_mac(_first(
                record, "dot11.device.last_bssid", "last_bssid"
            )),
            "channel": str(_first(
                record, "kismet.device.base.channel", "channel"
            )).strip(),
            "frequency_mhz": _as_number(_first(
                record, "kismet.device.base.frequency", "frequency"
            )),
            "signal_dbm": _as_number(_first(
                record,
                "kismet.device.base.signal/kismet.common.signal.last_signal",
                "kismet.common.signal.last_signal",
                "signal",
            )),
            "packets": _as_number(_first(
                record, "kismet.device.base.packets.total", "packets"
            )),
            "randomized_mac": (
                "true" if randomized is True
                else "false" if randomized is False
                else "unknown"
            ),
            "mac_address_type": address_type,
            "evidence_status": (
                "kismet_reported_randomized" if explicit_random is True
                else "locally_administered_address" if laa
                else "kismet_imported"
            ),
        })
        if len(rows) > MAX_KISMET_RECORDS:
            raise ValueError("Kismet Wi-Fi kayıt sayısı izin verilen sınırı aşıyor.")

    return rows
