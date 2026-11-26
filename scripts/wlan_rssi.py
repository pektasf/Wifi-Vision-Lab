"""Platform-neutral RSSI collector dispatch for Spatial Intelligence."""
from __future__ import annotations

import platform
from datetime import datetime
from pathlib import Path


def collector_availability(system_name: str | None = None) -> dict[str, str]:
    name = (system_name or platform.system()).casefold()
    if name == "windows":
        from scripts.windows_wlan import collector_availability as windows_availability

        return windows_availability("Windows")
    if name == "linux":
        from scripts.linux_wlan import collector_availability as linux_availability

        return linux_availability("Linux")
    if name == "darwin":
        return {
            "status": "not_implemented",
            "backend": "none",
            "detail": "A native macOS RSSI collector has not been implemented yet.",
        }
    return {
        "status": "unsupported_platform",
        "backend": "none",
        "detail": f"No native RSSI collector is available for {system_name or platform.system()}.",
    }


def collect_rssi_measurements(
    *,
    system_name: str | None = None,
    key_path: str | Path | None = None,
    now: datetime | None = None,
    command_runner=None,
    api=None,
) -> dict[str, object]:
    """Collect local RSSI through the native backend for the current OS."""
    name = (system_name or platform.system()).casefold()
    if name == "windows":
        from scripts.windows_wlan import collect_windows_rssi_measurements

        return collect_windows_rssi_measurements(
            key_path=key_path,
            now=now,
            api=api,
        )
    if name == "linux":
        from scripts.linux_wlan import collect_linux_rssi_measurements

        return collect_linux_rssi_measurements(
            key_path=key_path,
            now=now,
            command_runner=command_runner,
        )

    status = "not_implemented" if name == "darwin" else "unsupported_platform"
    return {
        "status": status,
        "source": "none",
        "observed_at": (now or datetime.now().astimezone()).isoformat(timespec="seconds"),
        "measurements": {},
        "measurement_count": 0,
        "errors": [{
            "code": None,
            "message": (
                "A native macOS RSSI collector has not been implemented yet."
                if name == "darwin"
                else f"No native RSSI collector is available for {system_name or platform.system()}."
            ),
        }],
    }
