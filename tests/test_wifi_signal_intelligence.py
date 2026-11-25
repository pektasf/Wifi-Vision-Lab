import pytest

from scripts.wifi_signal_intelligence import parse_interfaces_output


ENGLISH = """
Name : Wi-Fi
State : connected
SSID : Home Network
BSSID : aa:bb:cc:dd:ee:ff
Radio type : 802.11ax
Channel : 36
Receive rate (Mbps) : 866.7
Transmit rate (Mbps) : 780
Signal : 87%
"""

TURKISH = """
Ad : Wi-Fi
Durum : bağlı
SSID : Ev Ağı
BSSID : aa-bb-cc-dd-ee-ff
Radyo türü : 802.11ac
Kanal : 11
Alma hızı (Mbps) : 144.4
Gönderme hızı (Mbps) : 130
Sinyal : 64%
"""


def test_parse_english_netsh_output():
    result = parse_interfaces_output(ENGLISH)
    assert result["ssid"] == "Home Network"
    assert result["bssid"] == "AA:BB:CC:DD:EE:FF"
    assert result["signal_percent"] == "87"
    assert result["channel"] == "36"
    assert result["receive_mbps"] == "866.7"


def test_parse_turkish_netsh_output():
    result = parse_interfaces_output(TURKISH)
    assert result["ssid"] == "Ev Ağı"
    assert result["bssid"] == "AA:BB:CC:DD:EE:FF"
    assert result["signal_percent"] == "64"
    assert result["channel"] == "11"
    assert result["transmit_mbps"] == "130"


def test_prefers_connected_interface_when_multiple_are_reported():
    output = """
Name : Wi-Fi 2
State : disconnected
Signal : 99%

Name : Wi-Fi
State : connected
SSID : Office
BSSID : 00:11:22:33:44:55
Signal : 72%
"""
    result = parse_interfaces_output(output)
    assert result["ssid"] == "Office"
    assert result["signal_percent"] == "72"


@pytest.mark.parametrize("output", ["", "Name : Wi-Fi\nState : disconnected\nSignal : 90%"])
def test_missing_active_signal_raises_clear_error(output):
    with pytest.raises(RuntimeError, match="Aktif Wi-Fi"):
        parse_interfaces_output(output)


@pytest.mark.parametrize("signal", ["101%", "-1%", "unknown"])
def test_invalid_signal_values_are_rejected(signal):
    output = f"Name : Wi-Fi\nState : connected\nSignal : {signal}"
    with pytest.raises(RuntimeError):
        parse_interfaces_output(output)
