from scripts.ap_client_intelligence import parse_wlan_interface_output


def test_parse_english_connected_wlan_association():
    output = """
    Name                   : Wi-Fi
    State                  : connected
    SSID                   : OfficeNet
    BSSID                  : aa-bb-cc-dd-ee-ff
    Physical address       : 11-22-33-44-55-66
    """
    result = parse_wlan_interface_output(output)

    assert result == {
        "client_mac": "11:22:33:44:55:66",
        "ap_bssid": "AA:BB:CC:DD:EE:FF",
        "ssid": "OfficeNet",
    }


def test_parse_turkish_connected_wlan_association():
    output = """
    Ad                     : Wi-Fi
    Durum                  : bağlı
    SSID                   : Ev Agi
    BSSID                  : aa:bb:cc:dd:ee:ff
    Fiziksel adres         : 11:22:33:44:55:66
    """
    result = parse_wlan_interface_output(output)

    assert result is not None
    assert result["client_mac"] == "11:22:33:44:55:66"
    assert result["ap_bssid"] == "AA:BB:CC:DD:EE:FF"
    assert result["ssid"] == "Ev Agi"


def test_disconnected_interface_does_not_create_association():
    output = """
    State                  : disconnected
    SSID                   : OfficeNet
    BSSID                  : AA:BB:CC:DD:EE:FF
    Physical address       : 11:22:33:44:55:66
    """
    assert parse_wlan_interface_output(output) is None


def test_missing_client_or_ap_mac_does_not_create_association():
    output = """
    State                  : connected
    SSID                   : OfficeNet
    BSSID                  : AA:BB:CC:DD:EE:FF
    """
    assert parse_wlan_interface_output(output) is None


def test_invalid_mac_does_not_create_association():
    output = """
    State                  : connected
    SSID                   : OfficeNet
    BSSID                  : not-a-mac
    Physical address       : 11:22:33:44:55:66
    """
    assert parse_wlan_interface_output(output) is None
