"""Read-only laptop Wi-Fi capability audit for Spatial Intelligence.

This module inspects Windows driver/interface metadata only. It does not scan
networks, connect to access points, change adapter settings, or persist data.
"""
from __future__ import annotations

import json
import platform
import re
import subprocess
from datetime import datetime
from typing import Callable


_DRIVER_LABELS = {
    "interface_name": ("Interface name", "Arayüz adı", "Arayuz adi"),
    "driver": ("Driver", "Sürücü", "Surucu"),
    "vendor": ("Vendor", "Sağlayıcı", "Saglayici"),
    "provider": ("Provider", "Sağlayıcı", "Saglayici"),
    "date": ("Date", "Tarih"),
    "version": ("Version", "Sürüm", "Surum"),
    "radio_types": (
        "Radio types supported", "Desteklenen radyo türleri",
        "Desteklenen radyo turleri",
    ),
    "hosted_network": (
        "Hosted network supported", "Barındırılan ağ destekleniyor",
        "Barindirilan ag destekleniyor",
    ),
}

_INTERFACE_LABELS = {
    "interface_name": ("Name", "Ad", "Interface name", "Arayüz adı"),
    "state": ("State", "Durum"),
    "signal": ("Signal", "Sinyal"),
    "channel": ("Channel", "Kanal"),
    "radio_type": ("Radio type", "Radyo türü", "Radyo turu"),
}


def _normalise_label(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _extract_labels(output: str, labels: dict[str, tuple[str, ...]]) -> dict[str, str]:
    aliases = {
        key: {_normalise_label(alias) for alias in values}
        for key, values in labels.items()
    }
    result = {key: "" for key in labels}
    for line in (output or "").splitlines():
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        normalised = _normalise_label(label)
        for key, candidates in aliases.items():
            if normalised in candidates and value.strip():
                result[key] = value.strip()
                break
    return result


def parse_driver_output(output: str) -> dict[str, str]:
    """Extract Wi-Fi driver metadata from English or Turkish netsh output."""
    return _extract_labels(output, _DRIVER_LABELS)


def parse_interface_output(output: str) -> dict[str, object]:
    """Extract non-identifying active-interface details.

    SSID and BSSID are intentionally excluded from this diagnostic report.
    """
    raw = _extract_labels(output, _INTERFACE_LABELS)
    signal_match = re.search(r"(?<!\d)(\d{1,3})\s*%", raw["signal"])
    channel_match = re.search(r"\d{1,3}", raw["channel"])
    state = raw["state"].strip()
    state_folded = state.casefold()
    connected = state_folded in {"connected", "bağlı", "bagli"}
    signal_percent = int(signal_match.group(1)) if signal_match else None
    if signal_percent is not None and not 0 <= signal_percent <= 100:
        signal_percent = None
    return {
        "interface_name": raw["interface_name"],
        "connected": connected,
        "state": state,
        "signal_percent": signal_percent,
        "channel": channel_match.group(0) if channel_match else "",
        "radio_type": raw["radio_type"],
    }


def _parse_adapter_output(output: str) -> list[dict[str, str]]:
    if not output.strip():
        return []
    try:
        decoded = json.loads(output)
    except (TypeError, ValueError):
        return []
    adapters = decoded if isinstance(decoded, list) else [decoded]
    fields = ("Name", "InterfaceDescription", "Status", "LinkSpeed")
    return [
        {field: str(item.get(field, "") or "") for field in fields}
        for item in adapters
        if isinstance(item, dict)
    ]


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


def _command_result(
    runner: Callable[[list[str]], object], args: list[str]
) -> tuple[str, dict[str, object]]:
    try:
        result = runner(args)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return "", {"available": False, "return_code": None}
    return_code = getattr(result, "returncode", 1)
    stdout = getattr(result, "stdout", "") or ""
    return stdout, {
        "available": return_code == 0,
        "return_code": return_code,
    }


def collect_capabilities(
    command_runner: Callable[[list[str]], object] | None = None,
    system_name: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Collect a read-only capability snapshot without scanning the network."""
    operating_system = system_name or platform.system()
    timestamp = now or datetime.now().astimezone()
    report: dict[str, object] = {
        "generated_at": timestamp.isoformat(timespec="seconds"),
        "operating_system": operating_system,
        "collection_mode": "read_only_no_network_scan",
        "driver": {},
        "active_interface": {},
        "physical_adapters": [],
        "commands": {},
        "capabilities": {
            "nearby_ap_signal_percent": {
                "status": "available_via_existing_wifi_scan",
                "detail": (
                    "The existing Windows WLAN scan can expose signal percentages; "
                    "this audit does not start that scan."
                ),
            },
            "connected_interface_signal_percent": {
                "status": "not_checked",
                "detail": "Requires a successful active-interface query.",
            },
            "rssi_dbm": {
                "status": (
                    "collector_available_driver_dependent"
                    if operating_system == "Windows"
                    else "not_implemented"
                ),
                "detail": (
                    "Windows Native WLAN API can return driver-reported BSS RSSI in dBm; "
                    "the adapter/driver may still return no measurements. netsh signal "
                    "percentage is not converted to dBm."
                    if operating_system == "Windows"
                    else "A native RSSI collector for this operating system is not implemented yet."
                ),
            },
            "monitor_mode": {
                "status": "unknown",
                "detail": (
                    "Driver metadata alone does not prove monitor-mode support. "
                    "A separate adapter/driver validation is required."
                ),
            },
            "csi": {
                "status": "unknown",
                "detail": (
                    "CSI support cannot be inferred from the adapter name or "
                    "standard netsh output."
                ),
            },
            "wifi_rtt_ftm": {
                "status": "unknown",
                "detail": (
                    "Windows WLAN driver metadata does not confirm usable RTT/FTM "
                    "measurement support."
                ),
            },
            "passive_presence_sensing": {
                "status": "not_verified",
                "detail": (
                    "No passive human/object sensing claim is made until a supported "
                    "CSI or equivalent measurement source is validated."
                ),
            },
        },
        "notes": [
            "No SSID or BSSID is included in this report.",
            "No nearby-network scan or packet capture is started.",
            "Unknown means not verified, not necessarily unsupported.",
        ],
    }

    if operating_system == "Linux":
        report["capabilities"]["rssi_dbm"] = {
            "status": "collector_available_tool_driver_dependent",
            "detail": (
                "The Linux iw backend reads cached BSS RSSI in dBm without triggering "
                "a scan. The iw utility, kernel wireless stack, driver, permissions, "
                "and freshness of the cached list determine whether measurements are available."
            ),
        }
        report["commands"] = {
            "iw_interfaces": {"available": None, "return_code": None},
            "netsh_drivers": {"available": False, "return_code": None},
            "netsh_interfaces": {"available": False, "return_code": None},
            "powershell_adapters": {"available": False, "return_code": None},
        }
        report["notes"].append(
            "Linux RSSI collection reads cached BSS data only; the capability audit does not invoke iw."
        )
        return report

    if operating_system != "Windows":
        report["capabilities"]["nearby_ap_signal_percent"] = {
            "status": "not_implemented",
            "detail": "The current capability audit uses Windows WLAN commands only.",
        }
        report["capabilities"]["connected_interface_signal_percent"] = {
            "status": "not_checked",
            "detail": "A native collector for this operating system is not implemented yet.",
        }
        report["capabilities"]["rssi_dbm"] = {
            "status": "not_implemented",
            "detail": "A native RSSI collector for this operating system is not implemented yet.",
        }
        report["commands"] = {
            "netsh_drivers": {"available": False, "return_code": None},
            "netsh_interfaces": {"available": False, "return_code": None},
            "powershell_adapters": {"available": False, "return_code": None},
        }
        report["notes"].append(
            "This first capability collector is designed for Windows laptops."
        )
        return report

    runner = command_runner or _default_runner
    driver_output, driver_status = _command_result(
        runner, ["netsh", "wlan", "show", "drivers"]
    )
    interface_output, interface_status = _command_result(
        runner, ["netsh", "wlan", "show", "interfaces"]
    )
    adapter_output, adapter_status = _command_result(
        runner,
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            (
                "Get-NetAdapter -Physical | Select-Object Name,"
                "InterfaceDescription,Status,LinkSpeed | ConvertTo-Json -Compress"
            ),
        ],
    )

    report["driver"] = parse_driver_output(driver_output)
    report["active_interface"] = parse_interface_output(interface_output)
    report["physical_adapters"] = _parse_adapter_output(adapter_output)
    report["commands"] = {
        "netsh_drivers": driver_status,
        "netsh_interfaces": interface_status,
        "powershell_adapters": adapter_status,
    }

    if interface_status["available"]:
        report["capabilities"]["connected_interface_signal_percent"] = {
            "status": (
                "available"
                if report["active_interface"]["signal_percent"] is not None
                else "not_available"
            ),
            "detail": "Signal percentage reported by the connected Windows Wi-Fi interface.",
        }

    return report
