from scripts.device_inventory import scan


class WindowsNetworkAdapter:
    source = "windows_local"

    def collect(self):
        return scan()
