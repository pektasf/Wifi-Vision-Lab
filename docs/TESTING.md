# Test Strategy

## Scope

The test suite is deliberately offline and deterministic. It must not scan a real network, invoke ping/ARP/netsh, contact access points, or modify a user's existing scan data.

## Run locally

Install the development dependencies into the project's virtual environment:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest
```

## Current coverage

- Discovery profile identity: MAC-based grouping, network-scoped IP fallback, and empty identities.
- Inventory consolidation: one row per resolved profile and preservation of available evidence.
- CSV persistence: append behavior, header handling, field allow-listing, and overwrite behavior.
- Device classification: confidence bands, malformed numeric values, evidence retention, and missing input.
- Background scan jobs: output capture, exit status, failure reporting, cancellation, and exact custom-CIDR confirmation, legacy progress parsing, and structured scan-event encoding/decoding.

## Safety rules for tests

- Use temporary directories for file output.
- Mock operating-system and network boundaries in any future adapter tests.
- Never run a discovery scan as part of CI.
- Do not commit local data folders, logs, secrets, or virtual environments.

## Known limitations

These tests validate current deterministic transformations. They do not prove that a device label is factually correct, that a topology edge is physical, or that a device is reachable on a live network. Atomic CSV replacement, schema versioning, and adapter contract tests remain planned work.


## Scan safety policy tests

`tests/test_scan_policy.py` verifies that discovery accepts only the active
private IPv4 subnet, rejects public/loopback/link-local or mismatched network
details, enforces bounded host/worker/timeout settings, and reports when the
host limit truncates a subnet. These tests are offline and do not send packets.

See [SCAN_SAFETY.md](SCAN_SAFETY.md) for configuration and authorization notes.

See [BACKGROUND_SCANS.md](BACKGROUND_SCANS.md) for job lifecycle and current limitations.

See [SCAN_EVENTS.md](SCAN_EVENTS.md) for the stdout progress-event contract.


## Spatial Intelligence capability audit

- English and Turkish Windows WLAN driver/interface parsing.
- SSID/BSSID exclusion from the capability report.
- Mocked command execution proving the audit does not launch network scans.
- Non-Windows behavior without command execution.

The capability-audit tests are offline and do not inspect the user's live adapter.


## Spatial Intelligence RSSI fingerprint tests

- Validate local AP aliases and RSSI dBm ranges; reject MAC/BSSID-shaped keys.
- Parse survey measurements without network access.
- Verify local SQLite persistence and floor/zone ownership.
- Test zone estimation, insufficient overlap, ambiguous ties, and floor isolation.
- CI does not invoke Wi-Fi scans, packet capture, or live adapter APIs.

- Leave-one-out fingerprint validation excludes each tested reference and separates accuracy from prediction coverage.


## Windows WLAN RSSI collector

- Validate Windows WLAN SDK structure sizes without requiring Windows.
- Test stable HMAC pseudonyms, local key persistence, RSSI range filtering, and duplicate BSSID handling.
- Test the result contract without exposing SSID/BSSID.
- CI never calls the native WLAN API, WlanScan, or a live adapter.


## Windows WLAN diagnostics

- Distinguish no Wi-Fi interface, successful empty BSS list, partial interface errors, and API failures.
- Map common Windows WLAN error codes to actionable, non-identifying explanations.
- Verify the capability audit reports RSSI backend implementation separately from per-adapter support.
- Verify non-Windows reports do not claim the Windows RSSI collector is available.


## Windows target validation

GitHub Actions also runs the Windows WLAN ABI, platform capability, and app
syntax tests on `windows-latest`. These tests validate Windows ctypes structure
layout and the Windows-specific contracts without requiring a physical Wi-Fi
adapter or invoking live WLAN APIs.


## Per-adapter WLAN diagnostics

- Decode Windows fixed-width UTF-16 adapter descriptions independent of host ABI.
- Report each Wi-Fi interface state and whether its BSS list is available, empty, or errored.
- Keep adapter diagnostics ephemeral; do not persist adapter descriptions with RSSI fingerprints.
- Ensure RSSI output continues to exclude raw SSID/BSSID values.


## Linux WLAN collector

- Parse `iw dev` interface listings and cached `iw dev <interface> scan dump` BSS entries.
- Confirm the collector never invokes an active scan command.
- Verify RSSI values are validated and BSSIDs are pseudonymised before returning results.
- Cover missing `iw`, missing interfaces, empty cache, permission errors, and per-interface outcomes.
- Confirm Linux capability reporting does not claim that CSI or passive sensing is available.


## Capability report export

- Verify the local compatibility report serializes as JSON.
- Verify the export does not include SSID, BSSID, or network names.
- Verify adapter/driver and platform capability details remain available.
