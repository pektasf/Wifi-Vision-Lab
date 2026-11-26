# Topology evidence model

## Confidence levels

Topology edges and device-role labels are separate concepts. A device can be
observed without its physical role or its upstream connection being known.

- verified: direct association evidence from a supported source, currently
  Windows WLAN reporting the connected client MAC and AP BSSID.
- strong: configuration or direct local observation supports the fact, but
  does not prove a physical cable or device identity.
- inferred: a role guess based on hostname or classification text.
- context_only: shared scan-scope or configuration context, not a physical link.
- unknown: insufficient evidence.

## Relationships

### Verified Wi-Fi association

An edge with relation wifi_association is created only when the source record
contains all of the following:
- verification_status = verified;
- evidence_type = direct_association;
- valid client MAC and AP BSSID.

The AP is represented as a BSSID radio-interface node, not necessarily as the
whole physical access point. The client is matched to the observed inventory
by MAC where possible.

### Scan-scope context

A network_scope node represents the CIDR that was scanned. observed_in_scope
edges only mean that an address appeared in the inventory under that scan
scope. They do not mean that devices are physically connected to one another.

### Default gateway configuration

A configured_default_gateway edge is emitted only when the gateway address
belongs to the observed subnet. It records interface configuration context,
not a cable-level topology relationship. When scanning a separately routed
private subnet, the local machine's default gateway is not mislabeled as the
target subnet's gateway.

### Device role candidates

Network equipment candidates are inferred from hostname/classification text.
A candidate label does not establish that a device is an AP, router, switch,
controller, repeater, or mesh node.

## Data fields

topology_nodes.csv now includes evidence_type, evidence_source, confidence,
and details. topology_edges.csv includes those fields plus observed_at.
The topology UI draws only verified edges as connections and lists
context_only relationships separately.

## Limitations

- The current direct AP-client evidence is for the local Windows WLAN
  interface only; it is not a complete client list for an AP.
- No SNMP credentials or controller API access are assumed.
- Physical Ethernet links, switch port mappings, mesh backhaul links, and
  other AP clients require additional supported evidence.
- Historical verified associations show that an association was observed at
  a time; they do not necessarily describe the current connection.


## Large-topology rendering

The topology graph keeps vector traces for smaller maps and switches node/edge
traces to Plotly WebGL when there are at least 300 devices or 500 verified
relationships. Device labels are shown on maps with up to 120 devices; larger
maps keep hover details and reduce always-visible text to avoid visual and
rendering overload. The map exposes Plotly zoom, pan, scroll zoom and autoscale
controls, and preserves the current viewport across Streamlit reruns.


### DHCP server configuration context

When the selected Windows adapter reports DHCP enabled and a valid DHCP server
IPv4 address, the topology may include a configured_dhcp_server edge from the
adapter's subnet context to that address. This edge is always context_only and
uses network_context.csv as its local source. It does not prove server identity,
a physical link, or provide the router's DHCP client lease table. Disabled,
unknown, or invalid DHCP values do not create a DHCP server node or edge.


### Physical AP identity and radio grouping

BSSIDs remain separate radio nodes by default. A physical AP node and
`radio_of` edge are created only when relationship data contains a valid
`ap_device_mac`, `device_identity_verification=verified`, and
`device_identity_evidence=direct_ap_device_identity`. SSID similarity, shared
vendor OUI, and BSSID proximity are not identity evidence. The Windows WLAN
client association collector currently reports BSSID, not a physical AP base
MAC or controller identity, so it does not populate these fields by itself.
