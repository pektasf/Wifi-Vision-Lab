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
- Background scan jobs: output capture, exit status, failure reporting, cancellation, and exact custom-CIDR confirmation, progress parsing, and structured scan-event encoding/decoding.

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
