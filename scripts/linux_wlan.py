"""Read-only Linux Wi-Fi RSSI collector using cached nl80211 BSS results.

The `iw dev <interface> scan dump` command reads the kernel's existing scan
cache. This module never invokes `iw ... scan` without `dump`, never starts
a scan, and never exposes/persists SSIDs or raw BSSIDs.
"""
from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable

from scripts.windows_wlan import _alias_for_bssid, _load_local_alias_key


_INTERFACE_RE = re.compile(r"^\s*Interface\s+(\S+)\s*$", re.MULTILINE)
_BSS_RE = re.compile(r"^\s*BSS\s+((?:[0-9a-f]{2}:){5}[0-9a-f]{2})(?=\s|\(|$)", re.I | re.M)
_SIGNAL_RE = re.compile(r"^\s*signal:\s*(-?\d+(?:\.\d+)?)\s*dBm\s*$", re.I | re.M)


def parse_iw_interfaces(output: str) -> list[str]:
    """Return interface names from `iw dev` output."""
    return list(dict.fromkeys(_INTERFACE_RE.findall(output or "")))


def parse_iw_scan_dump(output: str) -> list[tuple[bytes, int]]:
    """Extract BSSID/RSSI pairs only; callers must pseudonymise before return."""
    text = output or ""
    starts = list(_BSS_RE.finditer(text))
    entries: list[tuple[bytes, int]] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        block = text[match.end():end]
        signal = _SIGNAL_RE.search(block)
        if not signal:
            continue
        try:
            bssid = bytes.fromhex(match.group(1).replace(":", ""))
            rssi = int(round(float(signal.group(1))))
        except (ValueError, OverflowError):
            continue
        if len(bssid) == 6 and -120 <= rssi <= -1:
            entries.append((bssid, rssi))
    return entries


def _default_runner(args: list[str]):
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )


def _error_message(return_code: int) -> str:
    if return_code in {1, 13}:
        return "Linux denied access to cached Wi-Fi scan results. Check user permissions and wireless capabilities."
    if return_code == 127:
        return "The 'iw' utility is unavailable. Install the distribution's iw package to enable Linux RSSI collection."
    return f"The Linux Wi-Fi utility returned exit code {return_code}."


def collect_linux_rssi_measurements(
    *,
    key_path: str | Path | None = None,
    now: datetime | None = None,
    command_runner: Callable[[list[str]], object] | None = None,
) -> dict[str, object]:
    """Read cached BSS results for each Linux Wi-Fi interface; do not scan."""
    runner = command_runner or _default_runner
    observed_at = (now or datetime.now().astimezone()).isoformat(timespec="seconds")
    try:
        result = runner(["iw", "dev"])
    except FileNotFoundError:
        return {
            "status": "unsupported_tool",
            "source": "linux_iw_cached_bss",
            "observed_at": observed_at,
            "measurements": {},
            "measurement_count": 0,
            "errors": [{"code": 127, "message": _error_message(127)}],
            "collection_mode": "read_only_cached_bss_list_no_scan",
        }
    except (OSError, subprocess.TimeoutExpired):
        return {
            "status": "unavailable",
            "source": "linux_iw_cached_bss",
            "observed_at": observed_at,
            "measurements": {},
            "measurement_count": 0,
            "errors": [{"code": None, "message": "Could not query Linux Wi-Fi interfaces."}],
            "collection_mode": "read_only_cached_bss_list_no_scan",
        }

    if getattr(result, "returncode", 1) != 0:
        code = int(getattr(result, "returncode", 1))
        return {
            "status": "unavailable",
            "source": "linux_iw_cached_bss",
            "observed_at": observed_at,
            "measurements": {},
            "measurement_count": 0,
            "errors": [{"code": code, "message": _error_message(code)}],
            "collection_mode": "read_only_cached_bss_list_no_scan",
        }

    interfaces = parse_iw_interfaces(getattr(result, "stdout", "") or "")
    if not interfaces:
        return {
            "status": "no_wifi_interface",
            "source": "linux_iw_cached_bss",
            "observed_at": observed_at,
            "measurements": {},
            "measurement_count": 0,
            "interfaces": [],
            "errors": [],
            "collection_mode": "read_only_cached_bss_list_no_scan",
        }

    raw_entries: list[tuple[bytes, int]] = []
    interface_reports = []
    errors = []
    for interface in interfaces:
        try:
            scan_result = runner(["iw", "dev", interface, "scan", "dump"])
        except FileNotFoundError:
            scan_result = None
            code = 127
        except (OSError, subprocess.TimeoutExpired):
            scan_result = None
            code = None
        else:
            code = int(getattr(scan_result, "returncode", 1))

        if scan_result is None or code != 0:
            message = (
                _error_message(code)
                if code is not None
                else "The cached Wi-Fi scan list could not be read."
            )
            errors.append({"code": code, "message": message})
            interface_reports.append({
                "name": interface,
                "status": "error",
                "bss_entries": 0,
                "error_code": code,
            })
            continue

        entries = parse_iw_scan_dump(getattr(scan_result, "stdout", "") or "")
        raw_entries.extend(entries)
        interface_reports.append({
            "name": interface,
            "status": "available" if entries else "empty_bss_list",
            "bss_entries": len(entries),
            "error_code": None,
        })

    measurements = {}
    if raw_entries:
        key = _load_local_alias_key(key_path)
        for bssid, rssi in raw_entries:
            alias = _alias_for_bssid(bssid, key)
            measurements[alias] = max(rssi, measurements.get(alias, -120))
        measurements = dict(sorted(measurements.items()))

    if measurements and errors:
        status = "available_with_warnings"
    elif measurements:
        status = "available"
    elif errors:
        status = "unavailable"
    else:
        status = "no_measurements"

    return {
        "status": status,
        "source": "linux_iw_cached_bss",
        "observed_at": observed_at,
        "measurements": measurements,
        "measurement_count": len(measurements),
        "interfaces_seen": len(interfaces),
        "interfaces_queried": sum(item["status"] != "error" for item in interface_reports),
        "interfaces_with_entries": sum(item["status"] == "available" for item in interface_reports),
        "interfaces": interface_reports,
        "errors": errors,
        "collection_mode": "read_only_cached_bss_list_no_scan",
        "privacy": {
            "raw_bssid_returned": False,
            "ssid_returned": False,
            "alias_scope": "stable_on_this_local_installation",
        },
        "note": (
            "RSSI is read from the kernel's cached BSS list. This command does not "
            "trigger a Wi-Fi scan; freshness depends on the driver and last scan."
        ),
    }


def collector_availability(system_name: str | None = None) -> dict[str, str]:
    name = (system_name or "Linux").casefold()
    if name in {"linux", "posix"}:
        return {
            "status": "implemented",
            "backend": "iw cached BSS list",
            "detail": "Read-only cached BSS RSSI query; iw, driver and permissions may vary.",
        }
    return {
        "status": "not_implemented",
        "backend": "none",
        "detail": "A native Linux RSSI backend is available only on Linux.",
    }
