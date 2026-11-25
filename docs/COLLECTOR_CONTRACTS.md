# Collector Result and Error Contract

All scan stages are progressively normalized through `scripts.contracts.run_collector`.

## Result envelope

A `CollectorResult` contains:
- collector name and status (`success`, `no_data`, or `failed`)
- start/end timestamps and elapsed milliseconds
- record count when the return shape supports a safe count
- structured warnings and errors
- non-sensitive execution metadata, including the Python return type

A `CollectorError` contains the source collector, exception class code, bounded message, recoverability flag, and timestamp.

## Compatibility

Existing collector return values and CSV formats are unchanged. The wrapper recognizes list results, discovery tuples whose second item is a list, and dictionaries with a list-valued `records` field. It does not guess counts for other return shapes.

Optional collectors can fail without aborting the overall scan. A required collector failure stops orchestration after the structured failure is logged. A `None` or empty-list result is reported as `no_data`, not as an exception.

## Privacy

The contract is local-only. It does not transmit telemetry or upload observations. Do not add IP, MAC, hostname, SSID, BSSID, or raw observation contents to CI logs or remote telemetry.
