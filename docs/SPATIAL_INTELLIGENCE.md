# Spatial Intelligence — laptop-first roadmap

## Product objective

Spatial Intelligence is a local-only extension of WiFi Vision Lab with two distinct
capabilities:

1. **Device positioning:** estimate the zone or position of Wi-Fi-connected devices
   when a supported measurement source provides enough evidence.
2. **Passive presence and motion sensing:** investigate whether changes in Wi-Fi
   channel measurements can detect presence or movement without requiring the
   observed person/object to carry a Wi-Fi client device.

These capabilities must remain separate in the processing pipeline and share a
common floor-plan, evidence, confidence, and event model.

## Laptop-only constraint

The initial implementation and acceptance path must work from the existing
Windows 11 laptop without requiring the user to purchase or connect ESP32 boards,
additional access points, Android phones, or specialist sensors.

The application must first audit the capabilities of the laptop's current Wi-Fi
adapter, driver, and Windows interfaces. Optional external hardware may be
considered only as a later, explicitly optional research extension; it is not a
prerequisite for the laptop-only roadmap.

## SI-0 — laptop capability audit

Implemented in scripts/spatial_capabilities.py and exposed in the Streamlit
**Mekânsal Zekâ** page.

The audit reads:

- netsh wlan show drivers
- netsh wlan show interfaces
- Physical adapter metadata through read-only PowerShell Get-NetAdapter

The audit does not run a nearby-network scan, capture packets, change adapter
settings, or persist SSID/BSSID data. The UI only runs the audit after the user
clicks its button. It can export a JSON compatibility report for review or
sharing; the report excludes SSID/BSSID and network names.

The report distinguishes measured facts from unknown capabilities:

- Windows netsh interface output normally reports signal percentage, not
  calibrated RSSI in dBm.
- Monitor-mode, CSI, and Wi-Fi RTT/FTM support are marked unknown unless a
  separate verified source proves support.
- An adapter model name alone is not proof of CSI or monitor-mode support.
- Unknown means not verified; it must not be displayed as unsupported.

### SI-0 acceptance criteria

- The audit works without administrator privileges where Windows permits the
  metadata commands.
- Tests use fixtures/mocks only and never execute network discovery.
- SSID and BSSID are not included in the audit report.
- Command failures are reported without crashing the application.
- The audit makes no claim that passive human/object detection is available.

## SI-1 — local Spatial Core

Implemented as local SQLite schema version 3 and the scripts/spatial_core.py module.

- Local floor-plan dimensions in metres.
- Rectangular zones bounded by their parent floor.
- Manually placed access-point, laptop, sensor, and reference anchors.
- Validation for finite coordinates, positive dimensions, floor boundaries, and anchor types.
- Zone lookup returns assigned, unassigned, or ambiguous; overlapping zones are never silently resolved.
- Existing device and observation records are preserved by the additive database migration.

A Streamlit floor-plan editor now creates floors, rectangular zones, and manual anchors locally, then renders them on a metric-scale map. Hardware measurements are not required to use this editor.

## Later implementation phases

### SI-2 — Laptop-observable device positioning

**Initial fingerprint workflow implemented (schema v4).**

- Local SQLite stores manually labelled RSSI fingerprints for floor zones.
- The Streamlit page supports reference survey entry and a new-observation zone estimate.
- A deterministic k-nearest-neighbour matcher compares AP-alias/RSSI vectors.
- Inputs are local aliases such as AP-01; MAC/BSSID values are rejected by the survey API.
- The estimator reports estimated, ambiguous, or insufficient-evidence states.
- Its match-agreement score is not a calibrated probability; it does not output metres or coordinates.
- No automatic Wi-Fi scan is launched. Windows signal percentage is not silently converted to dBm.

Leave-one-out validation is now available in the UI. It excludes each tested sample from its own reference set and reports accuracy separately from prediction coverage; zones with fewer than two samples are skipped. This is an initial internal check, not independent validation.

**Windows RSSI collection (initial read-only implementation):** the app can query the Windows Native WLAN API BSS list and read driver-reported RSSI in dBm. It does not call WlanScan, connect to an AP, or change adapter settings. Raw SSID/BSSID values are used only in memory to derive stable installation-local HMAC aliases; the key is stored under the ignored local data directory. Freshness depends on the Windows WLAN service and adapter driver. The collector distinguishes no Wi-Fi interface, an empty BSS list, access/service/driver errors, and partial results across multiple interfaces.

Linux uses the `iw dev <interface> scan dump` command to read cached BSS results only; the app never issues an active scan. macOS retains the common app functionality, but its native RSSI collector is not implemented yet. Platform capability reports must distinguish an unimplemented backend from unsupported hardware. On Windows, the capability audit reports the RSSI backend as implemented but driver-dependent; it does not claim that every adapter will return BSS measurements.

**Still pending:** repeated surveys across time/orientation, independent held-out validation, a reliable error bound, and native RSSI collectors for Linux/macOS.

Do not infer the position of every other network client from the laptop's own RSSI measurements. Remote-client positioning requires measurements supplied by that client or by compatible AP infrastructure.

### SI-3 — Laptop-only passive sensing feasibility

- Research whether the exact laptop adapter and Windows driver expose CSI or
  another suitable channel measurement stream.
- Validate any proposed source with a reproducible local capture and replay test.
- If the current hardware/driver does not expose the required data, mark this
  capability as unavailable on this setup and document the evidence. Do not
  simulate CSI or claim real passive sensing from ordinary signal percentages.

### SI-4 — Presence and motion experiments

- Only proceed when a real, supported measurement stream is available.
- Start with controlled empty-room versus movement experiments.
- Measure precision, recall, F1, false alarms, missed detections, and latency.
- Avoid identity recognition and unsupported object-type classification.

### SI-5 — Spatial map and event integration

- Combine supported device-position estimates and validated sensing events.
- Show measured, estimated, and unknown states distinctly.
- Keep all measurements and processing local.

## Engineering and privacy rules

- No cloud processing or external telemetry.
- No automatic network scan as part of the capability audit.
- The Windows RSSI query does not call WlanScan; freshness depends on the WLAN service/driver BSS list. Linux reads the kernel's cached BSS list using `iw ... scan dump` and does not trigger a new scan. The result includes a per-interface diagnostic (adapter description, Windows interface state, BSS-list availability, and API error code) so different laptop Wi-Fi adapters can be evaluated independently. Adapter descriptions are shown locally and are not persisted with RSSI fingerprints.
- Never persist or display raw SSID/BSSID from the native BSS list; use installation-local pseudonymous AP aliases.
- No packet injection, deauthentication, or disruption.
- No SSID/BSSID in the capability report.
- Do not represent signal strength as physical distance without calibration.
- Do not represent an inferred location as verified.
- Do not claim through-wall object identification or person identity.
- Keep raw measurements local and provide bounded retention controls before
  long-term sensing data collection is introduced.

## Current status

SI-0 provides a safe capability inventory. SI-2 now has an initial Windows
read-only BSS RSSI collector, but this is not calibrated positioning and does
not prove every adapter/driver will return measurements. Linux/macOS RSSI
collectors, calibrated device coordinates, CSI capture, and passive
human/object sensing remain future phases gated by platform and hardware support.
