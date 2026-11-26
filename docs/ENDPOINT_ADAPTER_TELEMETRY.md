# Authorized endpoint adapter telemetry

A standard LAN scan cannot list the network adapters installed on another
computer. For devices you own or are authorized to administer, run the
PowerShell collector on that endpoint:

    powershell -ExecutionPolicy Bypass -File .\tools\collect_endpoint_adapters.ps1

The script writes wifi_vision_endpoint_adapters.json beside itself. It does
not send data over the network. The file contains interface descriptions,
MAC addresses, adapter status, and IPv4 addresses, so transfer it only through
a channel you control and import it in Network Infrastructure using the
endpoint JSON uploader.

Imported rows are labelled endpoint_reported, not verified. The JSON file is
not cryptographically signed; a file can be modified before import. Matching
an imported MAC/IP to the local inventory is a correlation, not proof of a
person's identity or proof that a device is malicious. The import is intended
for authorized endpoint inventory and virtual-adapter visibility only.


When imported endpoint evidence matches an inventory row, the Cihaz Envanteri
page displays the reported adapter type and description. Matching prefers an
exact MAC address; if no MAC match exists, it can fall back to an exact IPv4
address. The UI records which matching method was used. An IP-only match is
weaker because DHCP reuse is possible, and must not be treated as proof of
persistent device identity.


## Inventory correlation scope

Endpoint adapter evidence can be attached to an inventory row by exact MAC
when the records do not declare conflicting network scopes. IP-only fallback
requires the endpoint report and inventory row to carry the same explicit
network scope. If scope is absent or differs, the importer keeps the endpoint
evidence separate instead of assuming that a reused private IPv4 address
identifies the same device.
