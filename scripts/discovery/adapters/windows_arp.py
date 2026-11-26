import ipaddress
import os

from scripts.device_inventory import get_network, arp_map
from scripts.common import stamp


class WindowsArpAdapter:
    source = "windows_arp_cache"

    def collect(self):
        network = get_network()
        arp = arp_map()

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
