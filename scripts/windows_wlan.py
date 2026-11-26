"""Read-only Windows WLAN BSS RSSI collector.

This queries the Windows WLAN API for the BSS list already maintained by the
WLAN AutoConfig service. It never calls WlanScan, connects to an AP, changes
adapter settings, or returns/persists raw SSIDs or BSSIDs.
"""
from __future__ import annotations

import ctypes
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping

from scripts.common import DATA

_DWORD = ctypes.c_uint32
_WORD = ctypes.c_uint16
_BYTE = ctypes.c_uint8
_BOOL = ctypes.c_int32
_HANDLE = ctypes.c_void_p
_VOID_P = ctypes.c_void_p


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", _DWORD),
        ("Data2", _WORD),
        ("Data3", _WORD),
        ("Data4", _BYTE * 8),
    ]


class _WLAN_INTERFACE_INFO(ctypes.Structure):
    _fields_ = [
        ("InterfaceGuid", _GUID),
        # WCHAR is always 16-bit in the Windows ABI, including when tests run
        # on non-Windows hosts where ctypes.c_wchar is 32-bit.
        ("strInterfaceDescription", _WORD * 256),
        ("isState", _DWORD),
    ]





_INTERFACE_STATES = {
    0: "not_ready",
    1: "connected",
    2: "ad_hoc_network_formed",
    3: "disconnecting",
    4: "disconnected",
    5: "associating",
    6: "discovering",
    7: "authenticating",
}


def _decode_interface_description(value) -> str:
    """Decode the fixed-width Windows WCHAR[256] field on every host ABI."""
    try:
        return bytes(value).decode("utf-16-le", errors="replace").split("\x00", 1)[0].strip()
    except (TypeError, UnicodeError):
        return "Unknown Wi-Fi adapter"


def _interface_state_name(value: int) -> str:
    return _INTERFACE_STATES.get(int(value), "unknown")


class _WLAN_INTERFACE_INFO_LIST(ctypes.Structure):
    _fields_ = [
        ("dwNumberOfItems", _DWORD),
        ("dwIndex", _DWORD),
        ("InterfaceInfo", _WLAN_INTERFACE_INFO * 1),
    ]


class _DOT11_SSID(ctypes.Structure):
    _fields_ = [("uSSIDLength", _DWORD), ("ucSSID", _BYTE * 32)]


class _WLAN_RATE_SET(ctypes.Structure):
    _fields_ = [("uRateSetLength", _DWORD), ("usRateSet", _WORD * 126)]


class _WLAN_BSS_ENTRY(ctypes.Structure):
    _fields_ = [
        ("dot11Ssid", _DOT11_SSID),
        ("uPhyId", _DWORD),
        ("dot11Bssid", _BYTE * 6),
        ("dot11BssType", _DWORD),
        ("dot11BssPhyType", _DWORD),
        ("lRssi", ctypes.c_int32),
        ("uLinkQuality", _DWORD),
        ("bInRegDomain", _BYTE),
        ("usBeaconPeriod", _WORD),
        ("ullTimestamp", ctypes.c_uint64),
        ("ullHostTimestamp", ctypes.c_uint64),
        ("usCapabilityInformation", _WORD),
        ("ulChCenterFrequency", _DWORD),
        ("wlanRateSet", _WLAN_RATE_SET),
        ("ulIeOffset", _DWORD),
        ("ulIeSize", _DWORD),
    ]


class _WLAN_BSS_LIST(ctypes.Structure):
    _fields_ = [
        ("dwTotalSize", _DWORD),
        ("dwNumberOfItems", _DWORD),
        ("wlanBssEntries", _WLAN_BSS_ENTRY * 1),
    ]


def _load_wlan_api():
    if os.name != "nt":
        raise RuntimeError("The Windows WLAN API is available only on Windows.")
    return ctypes.WinDLL("wlanapi.dll", use_last_error=True)


def _configure_api(api) -> None:
    api.WlanOpenHandle.argtypes = [
        _DWORD, _VOID_P, ctypes.POINTER(_DWORD), ctypes.POINTER(_HANDLE)
    ]
    api.WlanOpenHandle.restype = _DWORD
    api.WlanEnumInterfaces.argtypes = [
        _HANDLE, _VOID_P, ctypes.POINTER(ctypes.POINTER(_WLAN_INTERFACE_INFO_LIST))
    ]
    api.WlanEnumInterfaces.restype = _DWORD
    api.WlanGetNetworkBssList.argtypes = [
        _HANDLE, ctypes.POINTER(_GUID), ctypes.POINTER(_DOT11_SSID),
        _DWORD, _BOOL, _VOID_P, ctypes.POINTER(ctypes.POINTER(_WLAN_BSS_LIST))
    ]
    api.WlanGetNetworkBssList.restype = _DWORD
    api.WlanFreeMemory.argtypes = [_VOID_P]
    api.WlanFreeMemory.restype = None
    api.WlanCloseHandle.argtypes = [_HANDLE, _VOID_P]
    api.WlanCloseHandle.restype = _DWORD


def _load_local_alias_key(key_path: str | Path | None = None) -> bytes:
    """Load/create a machine-local HMAC key; the ignored data folder holds it."""
    path = Path(key_path) if key_path is not None else DATA / "spatial_alias.key"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            key = secrets.token_bytes(32)
            handle.write(key)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return key
    except FileExistsError:
        key = path.read_bytes()
        if len(key) != 32:
            raise RuntimeError(
                "The local AP-alias key is invalid; move it aside to create a new local identity key."
            )
        return key


def _alias_for_bssid(bssid: bytes, key: bytes) -> str:
    if len(bssid) != 6:
        raise ValueError("A BSSID must contain exactly six bytes.")
    digest = hmac.new(key, bssid, hashlib.sha256).hexdigest()[:10].upper()
    return f"AP-{digest}"


def normalise_bss_entries(
    entries: list[tuple[bytes, int] | tuple[bytes, int, int]], key: bytes
) -> dict[str, int]:
    """Convert raw API tuples to stable local aliases without exposing BSSIDs."""
    measurements: dict[str, int] = {}
    for item in entries:
        if len(item) < 2:
            continue
        bssid, rssi = item[0], item[1]
        if not isinstance(bssid, (bytes, bytearray)) or len(bssid) != 6:
            continue
        try:
            level = int(rssi)
        except (TypeError, ValueError):
            continue
        if not -120 <= level <= -1:
            continue
        alias = _alias_for_bssid(bytes(bssid), key)
        # A duplicate BSSID can be reported by multiple interfaces; retain the
        # strongest observed level without storing interface or network identity.
        measurements[alias] = max(level, measurements.get(alias, -120))
    return dict(sorted(measurements.items()))


def _query_bss_entries(api) -> dict[str, object]:
    _configure_api(api)
    negotiated_version = _DWORD()
    client_handle = _HANDLE()
    result = api.WlanOpenHandle(2, None, ctypes.byref(negotiated_version), ctypes.byref(client_handle))
    if result != 0:
        raise OSError(result, "WlanOpenHandle failed.")

    interface_list = ctypes.POINTER(_WLAN_INTERFACE_INFO_LIST)()
    collected: list[tuple[bytes, int, int]] = []
    diagnostics = {
        "interfaces_seen": 0,
        "interfaces_queried": 0,
        "interfaces_with_entries": 0,
        "interface_error_codes": [],
        "interfaces": [],
    }
    try:
        result = api.WlanEnumInterfaces(client_handle, None, ctypes.byref(interface_list))
        if result != 0:
            raise OSError(result, "WlanEnumInterfaces failed.")
        if not interface_list:
            return {"entries": collected, **diagnostics}

        diagnostics["interfaces_seen"] = int(interface_list.contents.dwNumberOfItems)
        list_address = ctypes.addressof(interface_list.contents)
        entries_offset = _WLAN_INTERFACE_INFO_LIST.InterfaceInfo.offset
        entry_size = ctypes.sizeof(_WLAN_INTERFACE_INFO)
        for index in range(int(interface_list.contents.dwNumberOfItems)):
            interface_ptr = ctypes.cast(
                list_address + entries_offset + index * entry_size,
                ctypes.POINTER(_WLAN_INTERFACE_INFO),
            )
            bss_list = ctypes.POINTER(_WLAN_BSS_LIST)()
            result = api.WlanGetNetworkBssList(
                client_handle,
                ctypes.byref(interface_ptr.contents.InterfaceGuid),
                None,
                3,  # dot11_BSS_type_any
                False,
                None,
                ctypes.byref(bss_list),
            )
            interface_info = interface_ptr.contents
            interface_report = {
                "name": _decode_interface_description(
                    interface_info.strInterfaceDescription
                ),
                "state": _interface_state_name(interface_info.isState),
                "status": "error" if result != 0 else "empty_bss_list",
                "bss_entries": 0,
                "error_code": int(result) if result != 0 else None,
            }
            if result != 0:
                diagnostics["interface_error_codes"].append(int(result))
                diagnostics["interfaces"].append(interface_report)
                continue
            diagnostics["interfaces_queried"] += 1
            if not bss_list:
                diagnostics["interfaces"].append(interface_report)
                continue
            try:
                item_count = int(bss_list.contents.dwNumberOfItems)
                interface_report["bss_entries"] = item_count
                interface_report["status"] = (
                    "available" if item_count else "empty_bss_list"
                )
                diagnostics["interfaces"].append(interface_report)
                if item_count:
                    diagnostics["interfaces_with_entries"] += 1
                bss_address = ctypes.addressof(bss_list.contents)
                bss_offset = _WLAN_BSS_LIST.wlanBssEntries.offset
                bss_size = ctypes.sizeof(_WLAN_BSS_ENTRY)
                for item_index in range(item_count):
                    entry_ptr = ctypes.cast(
                        bss_address + bss_offset + item_index * bss_size,
                        ctypes.POINTER(_WLAN_BSS_ENTRY),
                    )
                    entry = entry_ptr.contents
                    collected.append((
                        bytes(entry.dot11Bssid),
                        int(entry.lRssi),
                        int(entry.ullHostTimestamp),
                    ))
            finally:
                api.WlanFreeMemory(ctypes.cast(bss_list, _VOID_P))
    finally:
        if interface_list:
            api.WlanFreeMemory(ctypes.cast(interface_list, _VOID_P))
        api.WlanCloseHandle(client_handle, None)
    return {"entries": collected, **diagnostics}


_WLAN_ERROR_MESSAGES = {
    5: "Windows denied access to the WLAN results. Check Windows privacy and app permissions.",
    8: "Windows could not allocate enough memory for the WLAN result list.",
    50: "The WLAN service or adapter driver does not support this query.",
    1062: "The WLAN AutoConfig service is not running.",
    1168: "Windows could not find the requested WLAN interface.",
    0x80342000: "The Wi-Fi radio is powered off.",
}


def describe_wlan_error(code: int) -> str:
    """Return a safe, actionable explanation for a Windows WLAN error code."""
    numeric_code = int(code)
    return _WLAN_ERROR_MESSAGES.get(
        numeric_code,
        f"Windows WLAN API returned error {numeric_code} (0x{numeric_code & 0xFFFFFFFF:08X}).",
    )


def _windows_filetime_age_seconds(
    filetime: int, now: datetime | None = None
) -> float | None:
    """Convert WLAN_BSS_ENTRY host FILETIME into age seconds."""
    if not filetime:
        return None
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    received = datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(
        microseconds=int(filetime) / 10
    )
    age = (current.astimezone(timezone.utc) - received).total_seconds()
    return round(max(0.0, age), 1)


def collect_windows_rssi_measurements(
    *,
    key_path: str | Path | None = None,
    now: datetime | None = None,
    api=None,
) -> dict[str, object]:
    """Read the Windows WLAN BSS list; never explicitly request a new scan."""
    if api is None:
        try:
            api = _load_wlan_api()
        except RuntimeError as exc:
            return {
                "status": "unsupported_platform",
                "source": "windows_wlan_bss_api",
                "measurements": {},
                "measurement_count": 0,
                "errors": [{"code": None, "message": str(exc)}],
            }

    try:
        query = _query_bss_entries(api)
    except OSError as exc:
        code = int(exc.errno or 0)
        return {
            "status": "unavailable",
            "source": "windows_wlan_bss_api",
            "observed_at": (now or datetime.now().astimezone()).isoformat(timespec="seconds"),
            "measurements": {},
            "measurement_count": 0,
            "error_code": code,
            "errors": [{"code": code, "message": describe_wlan_error(code)}],
            "collection_mode": "read_only_bss_list_no_wlan_scan_call",
        }

    alias_key = _load_local_alias_key(key_path)
    measurements = normalise_bss_entries(query["entries"], alias_key)
    measurement_ages = {}
    for item in query["entries"]:
        if len(item) < 3:
            continue
        age = _windows_filetime_age_seconds(item[2], now)
        if age is None:
            continue
        alias = _alias_for_bssid(item[0], alias_key)
        measurement_ages[alias] = min(age, measurement_ages.get(alias, age))
    errors = [
        {"code": code, "message": describe_wlan_error(code)}
        for code in query["interface_error_codes"]
    ]
    if measurements and errors:
        status = "available_with_warnings"
    elif measurements:
        status = "available"
    elif not query["interfaces_seen"]:
        status = "no_wifi_interface"
    elif errors:
        status = "unavailable"
    else:
        status = "no_measurements"

    return {
        "status": status,
        "source": "windows_wlan_bss_api",
        "observed_at": (now or datetime.now().astimezone()).isoformat(timespec="seconds"),
        "measurements": measurements,
        "measurement_count": len(measurements),
        "measurement_ages_seconds": dict(sorted(measurement_ages.items())),
        "interfaces_seen": query["interfaces_seen"],
        "interfaces_queried": query["interfaces_queried"],
        "interfaces_with_entries": query["interfaces_with_entries"],
        "interfaces": query.get("interfaces", []),
        "errors": errors,
        "collection_mode": "read_only_bss_list_no_wlan_scan_call",
        "privacy": {
            "raw_bssid_returned": False,
            "ssid_returned": False,
            "alias_scope": "stable_on_this_local_installation",
        },
        "note": (
            "RSSI is reported by the local Wi-Fi driver in dBm. The API query does not "
            "call WlanScan; freshness depends on the Windows WLAN service and driver."
        ),
    }


def collector_availability(system_name: str | None = None) -> dict[str, str]:
    """Describe the current platform backend without guessing adapter support."""
    name = (system_name or os.name).casefold()
    if name in {"nt", "windows"}:
        return {
            "status": "implemented",
            "backend": "Windows Native WLAN API",
            "detail": "Read-only BSS RSSI query; adapter/driver results may vary.",
        }
    if name in {"posix", "linux", "darwin", "macos"}:
        return {
            "status": "not_implemented",
            "backend": "none",
            "detail": "This platform needs its own native Wi-Fi collector; other app features remain available.",
        }
    return {
        "status": "unsupported_platform",
        "backend": "none",
        "detail": "No native Wi-Fi measurement backend is available for this platform yet.",
    }
