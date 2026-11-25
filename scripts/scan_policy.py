"""Safety limits for local IPv4 network discovery.

The scanner only accepts the private subnet reported by the active local
interface. It never accepts arbitrary target hosts or CIDR ranges from users.
"""
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


def build_scan_targets(
    network_cidr: str,
    local_ip: str,
    gateway_ip: str,
    max_hosts: int = DEFAULT_MAX_HOSTS,
) -> tuple[list[str], bool]:
    """Return a bounded host list for the active private IPv4 subnet."""
    if not isinstance(max_hosts, int) or isinstance(max_hosts, bool):
        raise ValueError("max_hosts must be an integer.")
    if not 1 <= max_hosts <= HARD_MAX_HOSTS:
        raise ValueError(f"max_hosts must be between 1 and {HARD_MAX_HOSTS}.")

    try:
        network = ipaddress.ip_network(network_cidr, strict=True)
        local = ipaddress.ip_address(local_ip)
        gateway = ipaddress.ip_address(gateway_ip)
    except ValueError as exc:
        raise ValueError("A valid IPv4 network, local IP and gateway are required.") from exc

    if network.version != 4 or local.version != 4 or gateway.version != 4:
        raise ValueError("Only IPv4 local network discovery is supported.")
    if (
        not network.is_private
        or network.is_loopback
        or network.is_link_local
        or network.is_multicast
        or network.is_reserved
    ):
        raise ValueError("Discovery is restricted to private local IPv4 networks.")
    if local not in network or gateway not in network:
        raise ValueError("The local IP and default gateway must belong to the active subnet.")
    if gateway.is_multicast or gateway.is_unspecified:
        raise ValueError("The default gateway address is not valid for discovery.")

    if network.prefixlen >= 31:
        host_count = network.num_addresses
    else:
        host_count = max(0, network.num_addresses - 2)

    targets = [str(ip) for ip in islice(network.hosts(), max_hosts)]
    return targets, host_count > len(targets)
