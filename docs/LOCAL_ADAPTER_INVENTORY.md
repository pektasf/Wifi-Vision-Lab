# Local Windows adapter inventory

The Network Infrastructure view can enumerate all adapters returned by
Get-NetAdapter -IncludeHidden, including interfaces that have no IPv4 address
or are currently disabled. It displays interface description, status,
hardware/software classification, media details, link speed, and interface
index. MAC addresses remain local to the application.

This inventory helps identify Wi-Fi Direct / hosted-network adapters that
would not necessarily appear in the IPv4-only scan-interface list. It still
describes only the computer running WiFi Vision Lab. It does not reveal
virtual adapters installed on other LAN devices.
