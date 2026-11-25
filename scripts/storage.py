"""Local SQLite storage and a non-destructive legacy CSV importer."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping

from scripts.common import DATA, stamp

SCHEMA_VERSION = 1
DEFAULT_DB_PATH = DATA / "wifi_vision.db"

MIGRATIONS = {
    1: """
    CREATE TABLE IF NOT EXISTS devices (
        identity_key TEXT PRIMARY KEY,
        mac TEXT NOT NULL DEFAULT '',
        hostname TEXT NOT NULL DEFAULT '',
        vendor TEXT NOT NULL DEFAULT '',
        classification TEXT NOT NULL DEFAULT '',
        first_seen TEXT NOT NULL DEFAULT '',
        last_seen TEXT NOT NULL DEFAULT '',
        current_ip TEXT NOT NULL DEFAULT '',
        metadata_json TEXT NOT NULL DEFAULT '{}',
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS observations (
        observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        identity_key TEXT NOT NULL,
        observed_at TEXT NOT NULL DEFAULT '',
        ip TEXT NOT NULL DEFAULT '',
        mac TEXT NOT NULL DEFAULT '',
        hostname TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT '',
        source TEXT NOT NULL DEFAULT '',
        raw_json TEXT NOT NULL DEFAULT '{}',
        source_hash TEXT NOT NULL UNIQUE,
        FOREIGN KEY(identity_key) REFERENCES devices(identity_key)
            ON UPDATE CASCADE ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_observations_identity_time
        ON observations(identity_key, observed_at);
    CREATE INDEX IF NOT EXISTS idx_observations_ip ON observations(ip);
    CREATE TABLE IF NOT EXISTS events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        identity_key TEXT NOT NULL DEFAULT '',
        event_time TEXT NOT NULL DEFAULT '',
        event_type TEXT NOT NULL DEFAULT '',
        old_value TEXT NOT NULL DEFAULT '',
        new_value TEXT NOT NULL DEFAULT '',
        details TEXT NOT NULL DEFAULT '',
        source TEXT NOT NULL DEFAULT '',
        source_hash TEXT NOT NULL UNIQUE
    );
    CREATE INDEX IF NOT EXISTS idx_events_identity_time
        ON events(identity_key, event_time);
    CREATE INDEX IF NOT EXISTS idx_events_type_time
        ON events(event_type, event_time);
    CREATE TABLE IF NOT EXISTS legacy_records (
        record_id INTEGER PRIMARY KEY AUTOINCREMENT,
        dataset TEXT NOT NULL,
        row_hash TEXT NOT NULL,
        row_json TEXT NOT NULL,
        imported_at TEXT NOT NULL,
        UNIQUE(dataset, row_hash)
    );
    CREATE TABLE IF NOT EXISTS csv_imports (
        dataset TEXT PRIMARY KEY,
        file_hash TEXT NOT NULL,
        row_count INTEGER NOT NULL,
        imported_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    );
    """,
}


def _json(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), ensure_ascii=False, sort_keys=True, default=str)


def _hash(*parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def identity_for(mac: str, ip: str) -> str:
    normalized_mac = str(mac or "").strip().upper()
    if normalized_mac:
        return normalized_mac
    normalized_ip = str(ip or "").strip()
    return f"IP:{normalized_ip}" if normalized_ip else ""


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a local SQLite connection with conservative durability defaults."""
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 15000")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")
    return connection


def initialize_database(db_path: str | Path | None = None) -> Path:
    """Create or upgrade the database without deleting existing records."""
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    with connect(path) as connection:
        current = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if current > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema {current} is newer than supported schema {SCHEMA_VERSION}."
            )
        for version in range(current + 1, SCHEMA_VERSION + 1):
            script = MIGRATIONS.get(version)
            if script is None:
                raise RuntimeError(f"Missing database migration {version}.")
            connection.executescript(script)
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (version, stamp()),
            )
            connection.execute(f"PRAGMA user_version = {version}")
    return path


def upsert_device(
    connection: sqlite3.Connection,
    identity_key: str,
    *,
    mac: str = "",
    hostname: str = "",
    vendor: str = "",
    classification: str = "",
    first_seen: str = "",
    last_seen: str = "",
    current_ip: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> None:
    if not identity_key:
        raise ValueError("identity_key is required")
    connection.execute(
        """
        INSERT INTO devices (
            identity_key, mac, hostname, vendor, classification,
            first_seen, last_seen, current_ip, metadata_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(identity_key) DO UPDATE SET
            mac = CASE WHEN excluded.mac <> '' THEN excluded.mac ELSE devices.mac END,
            hostname = CASE WHEN excluded.hostname <> '' THEN excluded.hostname ELSE devices.hostname END,
            vendor = CASE WHEN excluded.vendor <> '' THEN excluded.vendor ELSE devices.vendor END,
            classification = CASE WHEN excluded.classification <> '' THEN excluded.classification ELSE devices.classification END,
            first_seen = CASE
                WHEN devices.first_seen = '' THEN excluded.first_seen
                WHEN excluded.first_seen = '' THEN devices.first_seen
                WHEN excluded.first_seen < devices.first_seen THEN excluded.first_seen
                ELSE devices.first_seen END,
            last_seen = CASE
                WHEN excluded.last_seen > devices.last_seen THEN excluded.last_seen
                ELSE devices.last_seen END,
            current_ip = CASE WHEN excluded.last_seen >= devices.last_seen
                AND excluded.current_ip <> '' THEN excluded.current_ip
                ELSE devices.current_ip END,
            metadata_json = CASE WHEN excluded.metadata_json <> '{}'
                THEN excluded.metadata_json ELSE devices.metadata_json END,
            updated_at = excluded.updated_at
        """,
        (
            identity_key, mac or "", hostname or "", vendor or "",
            classification or "", first_seen or "", last_seen or "",
            current_ip or "", _json(metadata or {}), stamp(),
        ),
    )


def add_observation(
    connection: sqlite3.Connection,
    *,
    identity_key: str,
    observed_at: str,
    ip: str = "",
    mac: str = "",
    hostname: str = "",
    status: str = "",
    source: str = "collector",
    raw: Mapping[str, Any] | None = None,
    source_hash: str | None = None,
) -> bool:
    if not identity_key:
        raise ValueError("identity_key is required")
    payload = dict(raw or {})
    row_hash = source_hash or _hash(source, identity_key, observed_at, _json(payload))
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO observations (
            identity_key, observed_at, ip, mac, hostname, status,
            source, raw_json, source_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            identity_key, observed_at or "", ip or "", mac or "",
            hostname or "", status or "", source, _json(payload), row_hash,
        ),
    )
    return cursor.rowcount == 1


def add_event(
    connection: sqlite3.Connection,
    *,
    event_time: str,
    event_type: str,
    identity_key: str = "",
    old_value: str = "",
    new_value: str = "",
    details: str = "",
    source: str = "collector",
    source_hash: str | None = None,
) -> bool:
    row_hash = source_hash or _hash(
        source, identity_key, event_time, event_type, old_value, new_value, details
    )
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO events (
            identity_key, event_time, event_type, old_value,
            new_value, details, source, source_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            identity_key or "", event_time or "", event_type or "",
            old_value or "", new_value or "", details or "", source, row_hash,
        ),
    )
    return cursor.rowcount == 1


def _import_typed_row(
    connection: sqlite3.Connection, dataset: str, row: dict[str, str], row_hash: str
) -> None:
    if dataset == "device_profiles.csv":
        key = row.get("identity_key", "").strip()
        if key:
            upsert_device(
                connection, key, mac=row.get("mac", ""),
                hostname=row.get("hostname", ""), vendor=row.get("vendor", ""),
                classification=row.get("classification", ""),
                first_seen=row.get("first_seen", ""),
                last_seen=row.get("last_seen", ""),
                current_ip=row.get("current_ip", ""), metadata=row,
            )
        return

    if dataset in {"device_inventory.csv", "device_history.csv"}:
        ip, mac = row.get("ip", ""), row.get("mac", "")
        key = row.get("identity_key", "") or identity_for(mac, ip)
        if not key:
            return
        observed_at = row.get("timestamp", "") or row.get("observed_at", "")
        upsert_device(
            connection, key, mac=mac, hostname=row.get("hostname", ""),
            first_seen=observed_at, last_seen=observed_at,
            current_ip=ip, metadata={"legacy_dataset": dataset},
        )
        add_observation(
            connection, identity_key=key, observed_at=observed_at,
            ip=ip, mac=mac, hostname=row.get("hostname", ""),
            status=row.get("status", ""), source=f"legacy:{dataset}",
            raw=row, source_hash=row_hash,
        )
        return

    if dataset == "device_events.csv":
        add_event(
            connection, event_time=row.get("event_time", ""),
            event_type=row.get("event_type", ""),
            identity_key=row.get("identity_key", ""),
            old_value=row.get("old_value", ""),
            new_value=row.get("new_value", ""),
            details=row.get("details", ""), source="legacy:device_events.csv",
            source_hash=row_hash,
        )


def import_legacy_csvs(
    data_dir: str | Path | None = None,
    db_path: str | Path | None = None,
) -> dict[str, int]:
    """Import processed CSV rows additively; never alter or remove source files."""
    source_dir = Path(data_dir) if data_dir is not None else DATA
    database_path = initialize_database(db_path)
    summary: dict[str, int] = {}
    if not source_dir.exists():
        return summary

    for csv_path in sorted(source_dir.glob("*.csv")):
        if not csv_path.is_file():
            continue
        dataset = csv_path.name
        file_digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
        with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            rows: Iterable[dict[str, str]] = (
                [
                    {str(key): str(value or "") for key, value in row.items() if key}
                    for row in reader
                ] if reader.fieldnames else []
            )

        imported_count = 0
        with connect(database_path) as connection:
            for row in rows:
                row_json = _json(row)
                row_hash = _hash(dataset, row_json)
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO legacy_records
                        (dataset, row_hash, row_json, imported_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (dataset, row_hash, row_json, stamp()),
                )
                if cursor.rowcount == 1:
                    imported_count += 1
                _import_typed_row(connection, dataset, row, row_hash)

            connection.execute(
                """
                INSERT INTO csv_imports(dataset, file_hash, row_count, imported_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(dataset) DO UPDATE SET
                    file_hash = excluded.file_hash,
                    row_count = excluded.row_count,
                    imported_at = excluded.imported_at
                """,
                (dataset, file_digest, len(rows), stamp()),
            )
        summary[dataset] = imported_count
    return summary


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize local SQLite storage and import processed CSVs."
    )
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()
    initialize_database(args.db_path)
    summary = import_legacy_csvs(args.data_dir, args.db_path)
    print(f"SQLite database ready: {args.db_path}")
    print(f"New CSV rows imported: {sum(summary.values())}")
    for dataset, count in summary.items():
        print(f"  {dataset}: {count} new rows")


if __name__ == "__main__":
    _main()
