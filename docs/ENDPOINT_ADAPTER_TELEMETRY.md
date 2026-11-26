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
