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
