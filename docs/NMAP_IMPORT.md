# Nmap XML evidence import

WiFi Vision Lab can import Nmap XML output as a separate source of host-discovery
evidence. It does not invoke Nmap, accept arbitrary targets, or perform scans.

## Workflow

1. Only scan networks and devices you own or are explicitly authorized to assess.
2. Use Nmap's XML output option (\`-oX\`) for the authorized host-discovery run.
   For host discovery without a port scan, Nmap documents \`-sn\`; on a local
   Ethernet network, ARP discovery is normally used by default.
3. In WiFi Vision Lab, open **Ağ Altyapısı**, upload the resulting \`.xml\` file,
   and import it.
4. Review imported observations separately from the live Windows discovery
   results. Exact IP/MAC matches are correlations, not verified physical
   identity.

## Data retained

The importer keeps scan start time, host observation time, IPv4 address, MAC
address when Nmap observed one, hostname, host state/reason, and the vendor
string supplied by Nmap. Port and service details are intentionally ignored.

MAC addresses are commonly available when Nmap performs ARP discovery on the
same Ethernet segment. When scanning across a router, Nmap may only observe
the target IP and cannot reveal the remote host's MAC address.

## Security and privacy

- XML parsing uses defusedxml and rejects DTD/entity declarations.
- Files are limited to 10 MB and 100,000 host records.
- The scan command line and target list are not stored.
- Imported results are stored locally in
  \`data/processed/nmap_observations.csv\`.
- No external network connection is made by the importer.
- A host being up, or an IP/MAC pair matching, does not identify a person or
  prove that the device is malicious.
