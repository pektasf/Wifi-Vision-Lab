_ADAPTER_TYPES = []


def register_adapter(adapter_type):
    if adapter_type not in _ADAPTER_TYPES:
        _ADAPTER_TYPES.append(adapter_type)


def get_adapters():
    return [adapter_type() for adapter_type in _ADAPTER_TYPES]


from scripts.discovery.adapters.windows import WindowsNetworkAdapter

register_adapter(WindowsNetworkAdapter)

from scripts.discovery.adapters.windows_arp import WindowsArpAdapter

register_adapter(WindowsArpAdapter)
