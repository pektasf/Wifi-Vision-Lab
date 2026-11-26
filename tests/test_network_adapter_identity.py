from scripts.device_inventory import classify_network_adapter


def test_physical_adapter_is_not_mislabeled_as_virtual():
    assert classify_network_adapter(
        True, "Wi-Fi", "Intel(R) Wi-Fi 6 AX201"
    ) == "physical"


def test_wifi_direct_virtual_adapter_is_identified():
    assert classify_network_adapter(
        False, "Local Area Connection* 12",
        "Microsoft Wi-Fi Direct Virtual Adapter #2",
    ) == "virtual_wlan"


def test_other_software_adapter_is_not_called_virtual_wlan():
    assert classify_network_adapter(
        False, "vEthernet (Default Switch)", "Hyper-V Virtual Ethernet Adapter"
    ) == "virtual_or_software"


def test_missing_hardware_metadata_stays_unknown():
    assert classify_network_adapter(
        None, "Wi-Fi", "Unknown wireless adapter"
    ) == "unknown"


def test_virtual_wlan_classification_requires_non_hardware_adapter():
    assert classify_network_adapter(
        True, "Wi-Fi Direct", "Wi-Fi Direct"
    ) == "physical"
