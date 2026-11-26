"""Safety limits and explicit authorization for local IPv4 discovery."""
from __future__ import annotations

import ipaddress
import os
from itertools import islice


DEFAULT_MAX_HOSTS = 1024
HARD_MAX_HOSTS = 4096
DEFAULT_WORKERS = 32
MAX_WORKERS = 64
DEFAULT_PING_TIMEOUT_MS = 600
MAX_PING_TIMEOUT_MS = 3000

RFC1918_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return value


def load_scan_settings() -> dict:
    """Read bounded scan settings from environment variables."""
    return {
        "max_hosts": _env_int(
            "WIFI_VISION_MAX_SCAN_HOSTS", DEFAULT_MAX_HOSTS, 1, HARD_MAX_HOSTS
        ),
        "workers": _env_int(
            "WIFI_VISION_SCAN_WORKERS", DEFAULT_WORKERS, 1, MAX_WORKERS
        ),
        "ping_timeout_ms": _env_int(
            "WIFI_VISION_PING_TIMEOUT_MS",
            DEFAULT_PING_TIMEOUT_MS,
            100,
            MAX_PING_TIMEOUT_MS,
        ),
    }


def _is_rfc1918(network: ipaddress.IPv4Network) -> bool:
    return any(network.subnet_of(private) for private in RFC1918_NETWORKS)


def build_scan_targets(
    network_cidr: str,
    local_ip: str,
    gateway_ip: str,
    max_hosts: int = DEFAULT_MAX_HOSTS,
    *,
    active_network_cidr: str | None = None,
    approved: bool = False,
    confirmation: str | None = None,
) -> tuple[list[str], bool]:
    """Build a bounded target list; non-default CIDRs require exact approval."""
    if not isinstance(max_hosts, int) or isinstance(max_hosts, bool):
        raise ValueError("max_hosts must be an integer.")
    if not 1 <= max_hosts <= HARD_MAX_HOSTS:
        raise ValueError(f"max_hosts must be between 1 and {HARD_MAX_HOSTS}.")

    try:
        network = ipaddress.ip_network(network_cidr, strict=True)
        active_network = ipaddress.ip_network(
            active_network_cidr or network_cidr, strict=True
        )
        local = ipaddress.ip_address(local_ip)
        gateway = (\n            ipaddress.ip_address(gateway_ip) if str(gateway_ip or "").strip() else None\n        )
    except ValueError as exc:
        raise ValueError(
            "A valid IPv4 target CIDR, active network, local IP and gateway are required."
        ) from exc

    if (
        network.version != 4 or active_network.version != 4
        or local.version != 4 or (gateway is not None and gateway.version != 4)
    ):
        raise ValueError("Only IPv4 local network discovery is supported.")

    if not _is_rfc1918(active_network):
        raise ValueError("The active interface must use an RFC1918 private IPv4 subnet.")
    if local not in active_network or gateway not in active_network:
        raise ValueError("The local IP and default gateway must belong to the active subnet.")
    if gateway.is_multicast or gateway.is_unspecified:
        raise ValueError("The default gateway address is not valid for discovery.")

    if (
        not _is_rfc1918(network)
        or network.is_loopback
        or network.is_link_local
        or network.is_multicast
        or network.is_reserved
    ):
        raise ValueError(
            "Scan targets must be RFC1918 private IPv4 networks "
            "(10/8, 172.16/12 or 192.168/16)."
        )

    if network != active_network:
        if not approved:
            raise ValueError(
                "A custom CIDR requires explicit authorization confirmation."
            )
        if str(confirmation or "").strip() != str(network):
            raise ValueError(
                f"To confirm this scope, enter the canonical CIDR exactly: {network}"
            )

    if network.prefixlen >= 31:
        host_count = network.num_addresses
    else:
        host_count = max(0, network.num_addresses - 2)

    targets = [str(ip) for ip in islice(network.hosts(), max_hosts)]
    return targets, host_count > len(targets)
