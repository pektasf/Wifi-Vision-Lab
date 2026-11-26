# Kismet Wi-Fi evidence import

WiFi Vision Lab can import a Kismet Wi-Fi device export in JSON or EKJSON
format. This is an optional evidence source; it does not replace the Windows
subnet scanner and does not start Kismet or perform packet capture.

## Workflow

1. Run Kismet only on a network and radio environment you own or are authorized
   to monitor.
2. In Kismet, use its Wi-Fi / IEEE 802.11 device view and export the device
   records as JSON or EKJSON. Prefer a bounded recent-device view rather than
   exporting a very large all-device database.
3. In WiFi Vision Lab, open **Ağ Altyapısı**, select the Kismet JSON/EKJSON file,
   and import it.
4. Review the imported records separately from the IP-based device inventory.
   Exact MAC matches are displayed as correlations, not proof of persistent
   physical identity.

## Randomized MAC interpretation

Kismet may explicitly report \`dot11.device.randomized_mac\`. WiFi Vision Lab
preserves this as a Kismet-reported field. It also records whether the MAC is
locally administered (the U/L bit). A locally administered address is an
indicator of address administration, not proof of spoofing, concealment, or
malicious behavior.

Every observed address remains a separate record. WiFi Vision Lab does not
automatically link randomized addresses into one physical device. Kismet's
optional randomized-address linking is disabled by default because it is a
best-effort inference which can link different devices or miss related ones.
If enabled by an authorized Kismet operator, any alias/linking evidence should
be reviewed separately and must not be treated as a verified identity.

## Hardware and operating-system limits

Capturing raw 802.11 management and client frames requires a monitor-mode
capable adapter and a compatible driver. Kismet documentation notes that
Windows has very limited public monitor-mode driver support. A Windows laptop's
built-in adapter may therefore be unable to provide this data. An authorized
Linux sensor with a supported external adapter can collect the data and export
it for local import into WiFi Vision Lab.

Normal Wi-Fi scan mode is not equivalent to monitor mode: it can discover
advertising access points but does not expose client devices or packet data.

## Privacy and limits

- Imported files are processed locally and stored in
  \`data/processed/wireless_observations.csv\`.
- The importer accepts UTF-8 JSON/EKJSON up to 25 MB and at most 100,000
  records.
- No Kismet server connection, credentials, packet capture, or remote scan is
  configured by this importer.
- The importer stores only explicit device and radio fields; it does not
  reconstruct a person's identity.
- Wi-Fi MAC randomization can create multiple addresses for one device. A
  matching MAC may also be shared, changed, or spoofed; address correlation
  alone is not identity verification.
