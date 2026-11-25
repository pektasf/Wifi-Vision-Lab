# SQLite storage and CSV migration

## Current transition model

Collectors and the Streamlit UI still use CSV in this phase. SQLite is added
alongside them as a local data layer; existing readers and writers are not
switched yet. CSV remains the compatibility source until later phases move
each collector and UI page to repository APIs.

Default database path: data/processed/wifi_vision.db

The processed-data directory is already excluded from Git. The database is
local and must not be committed or uploaded.

## Initialize and import

From the repository root, run:

    python -m scripts.storage

Optional paths for testing or a deliberate alternate location:

    python -m scripts.storage --data-dir .\data\processed --db-path .\data\processed\wifi_vision.db

The importer:
- reads only top-level CSV files in the selected processed-data directory;
- preserves every imported row in legacy_records;
- maps device inventory/history to devices and observations;
- maps device profiles to devices;
- maps device events to events;
- records a SHA-256 digest and row count in csv_imports;
- uses stable row hashes so reruns do not duplicate rows;
- imports changed snapshots additively, retaining prior observations;
- never modifies, renames, or deletes source CSV files.

The OUI reference data under data/reference is deliberately not imported.

## Schema

- devices: stable identity key, MAC, hostname, vendor, classification,
  first/last seen, current IP and JSON metadata.
- observations: time-stamped device sightings, IP/MAC/hostname/status,
  source and raw JSON evidence. Each source row has a unique hash.
- events: device/network events with time, type, old/new values and details.
- legacy_records: JSON copy of rows from all processed CSVs.
- csv_imports: latest file digest, row count and import time per CSV file.
- schema_migrations: applied migration versions.

SQLite uses foreign-key enforcement, a 15-second busy timeout, WAL journaling
and synchronous=FULL. Database schema upgrades are versioned through
PRAGMA user_version. A database newer than the application is rejected
rather than silently downgraded.

## Important limitations in this phase

- Existing collectors and UI pages still use CSV. This is an additive storage
  foundation, not yet a full runtime cutover.
- Import is additive. If a CSV snapshot removes a row, the old SQLite record
  is retained as historical data; deletion/reconciliation policy is separate.
- Do not manually edit the SQLite database while the application is running.
- Keep real network observations, database files, and exports local. Do not
  attach them to issues or pull requests.

## Verification

Run:

    python -m pytest -q
