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
clicks its button.

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

- Collect signal observations only from supported Windows APIs/commands.
- Build a local fingerprint survey workflow with manually labelled reference
  zones.
- Estimate zones using deterministic fingerprint matching and report measured
  validation error.
- Do not infer the position of every other network client from the laptop's own
  RSSI measurements. Remote-client positioning requires measurements supplied
  by that client or by compatible AP infrastructure.

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
- No packet injection, deauthentication, or disruption.
- No SSID/BSSID in the capability report.
- Do not represent signal strength as physical distance without calibration.
- Do not represent an inferred location as verified.
- Do not claim through-wall object identification or person identity.
- Keep raw measurements local and provide bounded retention controls before
  long-term sensing data collection is introduced.

## Current status

SI-0 provides a safe capability inventory. It does not yet provide calibrated
device coordinates, CSI capture, or passive human/object sensing. Those remain
future phases gated by verified laptop hardware and driver support.
