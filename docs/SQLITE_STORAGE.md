# SQLite runtime storage

## Active data path

SQLite is now the application's primary read/write source for processed datasets.
The default database is `data/processed/wifi_vision.db`, which is local and
excluded from Git.

- Streamlit's shared `load()` helper initializes the database, imports any
  existing processed CSV files once per app process, and then reads datasets
  from SQLite.
- Collector writes through `scripts.common.write_rows` and
  `overwrite_rows` update the SQLite dataset snapshot first, then atomically
  export the CSV compatibility copy.
- A dataset that has never been imported is distinguishable from an imported
  empty dataset. If SQLite is unavailable, the UI attempts a CSV fallback.
- Existing collector return values and CSV column formats are unchanged.

## Migration and compatibility

Schema version 2 adds `dataset_snapshots` and `dataset_rows`. Schema version 3 adds local `spatial_floors`, `spatial_zones`, and `spatial_anchors` tables for Spatial Intelligence. Both migrations are additive and preserve existing records. Each dataset is
stored as an ordered JSON row snapshot. The migration is additive and retains
the existing devices, observations, events, legacy_records, and csv_imports
tables. Existing schema version 1 databases are upgraded without dropping
their records.

On first app data load, `import_legacy_csvs` imports top-level CSV files from
the processed-data directory. It preserves source CSV files and retains the
existing typed device/observation/event import behavior. Importing the same
CSV repeatedly is idempotent for legacy rows and typed observations.

CSV files remain compatibility exports and a recovery fallback; they are not
the normal application read source after import. A CSV export is written after
the SQLite snapshot commits. If export fails, the committed SQLite data
remains available to the app.

## Local privacy and backup

The database, WAL files, processed CSVs, and network observations must remain
local. Do not commit or upload database files, real IP/MAC/hostname/SSID/BSSID
observations, or backups.

Before manually copying a live database, stop the application or use SQLite's
backup API so the WAL state is included. Do not manually edit the database
while the application is running.

## Verification

Run:

    python -m pytest -q

Tests cover idempotent initialization, schema-v1 and schema-v2 upgrades, spatial floor/zone/anchor validation and persistence, generic dataset
round-trips, empty snapshots, legacy CSV preservation, and deduplication.


## Backup and restore

Use SQLite's online backup API. Do not copy only the `.db` file while the
application is running; committed data may still be in the WAL.

Create a backup from the repository root:

    python -m scripts.storage --backup-to .\backups\wifi-vision-backup.db

Restore to a new database path (the destination must not already exist):

    python -m scripts.storage --restore-from .\backups\wifi-vision-backup.db --db-path .\data\processed\wifi_vision_restored.db

The backup operation refuses to overwrite an existing destination and runs an
integrity check. Restore verifies the backup integrity and schema version,
refuses to overwrite an existing database, and applies any supported schema
upgrade after copying. Keep backups on trusted local storage; they contain
sensitive local network inventory and observations.
