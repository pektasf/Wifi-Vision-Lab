# Identity variation indicators

WiFi Vision Lab records observable indicators; it does not claim to recover a
person's or device's hidden real-world identity.

Current indicators:
- \`locally_administered_mac\`: the MAC address has the locally administered
  bit set. This can indicate MAC randomization, a virtual adapter, or manual
  configuration; it is not proof of spoofing.
- \`same_ip_multiple_macs\`: one scan observed multiple MAC addresses claiming
  the same IP on the same network. This can result from stale ARP data, address
  conflicts, failover, or spoofing and requires review.
- \`ip_mac_changed_over_time\`: the same network/IP pair was observed with
  different MAC addresses in retained local history. DHCP reuse and privacy
  randomization are possible benign causes.
- \`hostname_seen_with_multiple_macs\`: a hostname appeared with multiple MAC
  addresses on the same network. Hostname reuse and virtual machines are
  possible benign causes.
- \`mac_not_observed\`: an observation had an IP but no MAC evidence.

History is stored locally in \`data/processed/discovery_identity_history.csv\`
and bounded to 20,000 rows. It is not sent to GitHub or an external service.

A remote device's virtual WLAN/virtual adapter cannot generally be proven from
ordinary IP/ARP observations alone. Detecting remote virtual interfaces needs
trusted endpoint telemetry or a supported controller/agent export. The local
Windows scanner can separately identify whether its selected adapter is
hardware-backed; that does not reveal the interface type of every remote host.


## Local virtual WLAN adapter evidence

On Windows, the scanner also records whether the selected local network
interface is reported as hardware-backed by Get-NetAdapter, along with its
interface description. A non-hardware interface explicitly described as
Wi-Fi Direct / hosted network is classified as virtual_wlan; other
non-hardware interfaces remain virtual_or_software. Missing metadata stays
unknown. This is evidence about the scanner computer's own interface only.

A remote phone, laptop, or other endpoint may use a virtual interface behind
an access point, hotspot, bridge, or tethering device. Standard LAN scans do
not expose that endpoint's complete adapter list. To identify remote virtual
interfaces, the platform needs an authorized endpoint agent or a trusted
router/AP/controller export. Shared SSID, vendor prefix, IP range, or signal
strength are not sufficient proof.


Additional indicator:
- \`mac_seen_with_multiple_ips\`: the same MAC was observed at more than one
  IPv4 address on the same network across the retained history. DHCP renewal,
  multiple configured addresses, and network changes are common benign causes;
  this is an informational indicator, not a concealment verdict.

IP-only observations are linked to a MAC profile only when the same network/IP
maps to exactly one MAC across the available local history. Ambiguous mappings
remain separate.


## Cross-source evidence timeline

The Network Infrastructure page also presents a unified timeline from local
Windows discovery, authorized endpoint reports, Kismet Wi-Fi exports, Nmap
XML, and Zeek DHCP logs. Source observations remain separate rows; they are
not merged into one asserted physical identity.

Inventory correlation prefers an exact MAC match. If no MAC match exists, an
exact IPv4 match may be shown as weaker context because addresses can be
reassigned. The timeline can carry identity indicators already attached to a
matched inventory row, but a correlation is not proof of a person or device
identity.

Kismet's explicit randomized-MAC field and the locally-administered MAC bit
are shown as indicators only. Multiple randomized addresses are never
automatically grouped by this timeline.
