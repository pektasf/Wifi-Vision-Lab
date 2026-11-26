# Zeek DHCP evidence import

WiFi Vision Lab can import Zeek \`dhcp.log\` records exported as JSON or
newline-delimited JSON (NDJSON). Zeek observes DHCP transactions and can
provide the client MAC, hostname, requested/assigned IPv4 address, DHCP server,
lease duration, and message types.

## Workflow

1. Deploy Zeek only on a network you own or are authorized to monitor.
2. Configure Zeek to write JSON logs (for example, load its JSON logging
   policy) and collect \`dhcp.log\`.
3. In WiFi Vision Lab, open **Ağ Altyapısı**, upload the JSON/NDJSON DHCP log,
   and import it.
4. Review DHCP observations and the optional hostname-to-MAC variation
   summary. Exact MAC/IP matches to the local inventory are correlations.

## Why this helps identity-variation analysis

DHCP records can show one client hostname appearing with multiple MAC
addresses over time, or one MAC receiving different IP addresses. This can
happen because of Wi-Fi MAC randomization, interface changes, DHCP renewal,
multiple devices sharing a hostname, or ordinary network changes. It is an
indicator for review, not proof of concealment or malicious behavior.

Zeek may not log a server address or assigned address for every DHCP
transaction. For example, an initial DISCOVER may contain a client MAC and
hostname but no lease assignment yet. Missing values are retained as empty;
they are not inferred.

## Limits and privacy

- The importer accepts JSON/NDJSON up to 20 MB and 100,000 records.
- Only DHCP client/lease fields are retained; packet payloads and other Zeek
  logs are not imported.
- The source file is processed locally and stored in
  \`data/processed/zeek_dhcp_observations.csv\`.
- No Zeek process is installed, configured, or started by WiFi Vision Lab.
- A locally administered MAC is not proof of spoofing or a malicious device.


## Inventory matching safeguard

A Zeek DHCP record's server address is not a subnet identifier. Therefore,
the import view does not claim an IP-only inventory match unless both records
carry the same explicit network scope. An exact MAC observation may still be
shown as a MAC correlation, but it is not proof of a physical device or person.
