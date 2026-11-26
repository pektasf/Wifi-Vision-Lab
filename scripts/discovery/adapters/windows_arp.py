import ipaddress
import os

from scripts.device_inventory import get_network, arp_map
from scripts.common import stamp


class WindowsArpAdapter:
    source = "windows_arp_cache"

    def collect(self):
        interface_alias = os.getenv("WIFI_VISION_INTERFACE_ALIAS", "").strip() or None
        network = get_network(interface_alias)
        subnet = ipaddress.ip_network(network["network"], strict=True)
        arp = {
            ip: mac for ip, mac in arp_map().items()
            if ipaddress.ip_address(ip) in subnet
        }

        devices = []

        for ip, mac in arp.items():
            devices.append({
                "timestamp": stamp(),
                "ip": ip,
                "mac": mac,
                "hostname": "",
                "status": "arp_cache",
                "gateway": network["gateway"],
                "adapter": network["adapter"],
                "subnet": network["network"]
            })

        return network, devices
