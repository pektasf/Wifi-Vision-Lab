# Windows virtual adapter evidence

The Windows scanner records the selected local adapter's hardware-interface
flag and interface description from Get-NetIPConfiguration / Get-NetAdapter.
A non-hardware interface whose alias or description explicitly identifies
Wi-Fi Direct or a hosted network is labelled virtual_wlan. Other
non-hardware interfaces are labelled virtual_or_software. Missing metadata
is labelled unknown.

This describes the scanner computer's selected interface, not every device on
the LAN. A normal remote IP/ARP scan cannot enumerate another endpoint's
network adapters. Remote virtual WLAN identification requires authorized
endpoint telemetry or a trusted AP/router/controller export that reports
client interface capabilities. SSID, vendor OUI, subnet, and signal strength
must not be used as proof.
