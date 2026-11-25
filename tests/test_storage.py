import csv
import sqlite3

import pytest

from scripts.storage import (
    add_event, add_observation, backup_database, connect, import_legacy_csvs,
    initialize_database, read_dataset, restore_database, upsert_device,
    write_dataset_snapshot, MIGRATIONS,
)


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_initialize_database_is_idempotent_and_versioned(tmp_path):
    db_path = tmp_path / "nested" / "wifi.db"
    initialize_database(db_path)
    initialize_database(db_path)
    with connect(db_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        tables = {
            row["name"] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert {"devices", "observations", "events", "legacy_records",
            "csv_imports", "schema_migrations"} <= tables


def test_device_upsert_and_observation_deduplication(tmp_path):
    db_path = initialize_database(tmp_path / "wifi.db")
    with connect(db_path) as connection:
        upsert_device(
            connection, "AA:BB:CC:DD:EE:FF", mac="AA:BB:CC:DD:EE:FF",
            current_ip="192.168.1.10", first_seen="2026-01-01",
            last_seen="2026-01-01",
        )
        upsert_device(
            connection, "AA:BB:CC:DD:EE:FF",
            current_ip="192.168.1.11", last_seen="2026-01-02",
        )
        first = add_observation(
            connection, identity_key="AA:BB:CC:DD:EE:FF",
            observed_at="2026-01-01", ip="192.168.1.10",
            source_hash="same-observation",
        )
        duplicate = add_observation(
            connection, identity_key="AA:BB:CC:DD:EE:FF",
            observed_at="2026-01-01", ip="192.168.1.10",
            source_hash="same-observation",
        )
    assert first is True
    assert duplicate is False
    with connect(db_path) as connection:
        device = connection.execute(
            "SELECT current_ip FROM devices WHERE identity_key=?",
            ("AA:BB:CC:DD:EE:FF",),
        ).fetchone()
        count = connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert device["current_ip"] == "192.168.1.11"
    assert count == 1


def test_observation_requires_existing_device(tmp_path):
    db_path = initialize_database(tmp_path / "wifi.db")
    with pytest.raises(sqlite3.IntegrityError):
        with connect(db_path) as connection:
            add_observation(
                connection, identity_key="missing-device",
                observed_at="2026-01-01", source_hash="orphan",
            )


def test_event_deduplication(tmp_path):
    db_path = initialize_database(tmp_path / "wifi.db")
    kwargs = {
        "event_time": "2026-01-01", "event_type": "new_device",
        "identity_key": "AA:BB:CC:DD:EE:FF", "source_hash": "event-1",
    }
    with connect(db_path) as connection:
        assert add_event(connection, **kwargs) is True
        assert add_event(connection, **kwargs) is False


def test_csv_import_is_idempotent_and_preserves_source(tmp_path):
    data_dir = tmp_path / "processed"
    data_dir.mkdir()
    inventory = data_dir / "device_inventory.csv"
    write_csv(
        inventory, ["timestamp", "ip", "mac", "hostname", "status"],
        [{
            "timestamp": "2026-01-01T10:00:00+03:00",
            "ip": "192.168.1.20", "mac": "AA:BB:CC:DD:EE:FF",
            "hostname": "test-device", "status": "responding",
        }],
    )
    original = inventory.read_bytes()
    db_path = tmp_path / "wifi.db"
    first = import_legacy_csvs(data_dir, db_path)
    second = import_legacy_csvs(data_dir, db_path)
    assert first["device_inventory.csv"] == 1
    assert second["device_inventory.csv"] == 0
    assert inventory.read_bytes() == original
    with connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM devices").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM legacy_records").fetchone()[0] == 1


def test_changed_csv_adds_only_new_rows(tmp_path):
    data_dir = tmp_path / "processed"
    data_dir.mkdir()
    inventory = data_dir / "device_inventory.csv"
    fields = ["timestamp", "ip", "mac", "hostname", "status"]
    first_row = {
        "timestamp": "2026-01-01", "ip": "192.168.1.20",
        "mac": "AA:BB:CC:DD:EE:FF", "hostname": "device", "status": "up",
    }
    second_row = {
        "timestamp": "2026-01-02", "ip": "192.168.1.21",
        "mac": "AA:BB:CC:DD:EE:FF", "hostname": "device", "status": "up",
    }
    write_csv(inventory, fields, [first_row])
    db_path = tmp_path / "wifi.db"
    import_legacy_csvs(data_dir, db_path)
    write_csv(inventory, fields, [first_row, second_row])
    result = import_legacy_csvs(data_dir, db_path)
    assert result["device_inventory.csv"] == 1
    with connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM legacy_records").fetchone()[0] == 2
    assert read_dataset("device_inventory.csv", db_path) == [first_row, second_row]


def test_dataset_snapshot_round_trip_and_empty_snapshot(tmp_path):
    db_path = tmp_path / "wifi.db"
    rows = [
        {"ip": "192.168.1.2", "hostname": "router"},
        {"ip": "192.168.1.3", "hostname": "laptop"},
    ]

    assert read_dataset("device_inventory.csv", db_path) is None
    assert write_dataset_snapshot("device_inventory.csv", rows, db_path) == 2
    assert read_dataset("device_inventory.csv", db_path) == rows

    assert write_dataset_snapshot("empty.csv", [], db_path) == 0
    assert read_dataset("empty.csv", db_path) == []


def test_legacy_import_populates_runtime_dataset_snapshot(tmp_path):
    data_dir = tmp_path / "processed"
    data_dir.mkdir()
    source = data_dir / "device_inventory.csv"
    rows = [{
        "timestamp": "2026-01-01T10:00:00+03:00",
        "ip": "192.168.1.20",
        "mac": "AA:BB:CC:DD:EE:FF",
        "hostname": "test-device",
        "status": "responding",
    }]
    write_csv(
        source, ["timestamp", "ip", "mac", "hostname", "status"], rows
    )
    db_path = tmp_path / "wifi.db"

    import_legacy_csvs(data_dir, db_path)

    assert read_dataset("device_inventory.csv", db_path) == rows


def test_existing_schema_v1_upgrades_without_losing_rows(tmp_path):
    db_path = tmp_path / "legacy-v1.db"
    with connect(db_path) as connection:
        connection.executescript(MIGRATIONS[1])
        connection.execute("PRAGMA user_version = 1")
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (1, 'test')"
        )
        upsert_device(
            connection, "AA:BB:CC:DD:EE:FF",
            mac="AA:BB:CC:DD:EE:FF", current_ip="192.168.1.5",
        )

    initialize_database(db_path)

    with connect(db_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        row = connection.execute(
            "SELECT current_ip FROM devices WHERE identity_key=?",
            ("AA:BB:CC:DD:EE:FF",),
        ).fetchone()
        tables = {
            item["name"] for item in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert row["current_ip"] == "192.168.1.5"
    assert {"dataset_snapshots", "dataset_rows"} <= tables



def test_common_collector_writes_update_sqlite_and_csv(tmp_path, monkeypatch):
    from scripts import common, storage

    monkeypatch.setattr(common, "DATA", tmp_path)
    monkeypatch.setattr(storage, "DEFAULT_DB_PATH", tmp_path / "wifi.db")
    csv_path = tmp_path / "device_inventory.csv"
    fields = ["ip", "hostname"]

    common.overwrite_rows(
        csv_path, [{"ip": "192.168.1.2", "hostname": "router"}], fields
    )
    common.write_rows(
        csv_path, [{"ip": "192.168.1.3", "hostname": "laptop"}], fields
    )

    expected = [
        {"ip": "192.168.1.2", "hostname": "router"},
        {"ip": "192.168.1.3", "hostname": "laptop"},
    ]
    assert read_dataset("device_inventory.csv") == expected
    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        assert list(csv.DictReader(handle)) == expected



def test_legacy_import_does_not_overwrite_existing_runtime_snapshot(tmp_path):
    data_dir = tmp_path / "processed"
    data_dir.mkdir()
    source = data_dir / "device_inventory.csv"
    write_csv(
        source, ["ip", "hostname"],
        [{"ip": "192.168.1.2", "hostname": "stale-csv"}],
    )
    db_path = tmp_path / "wifi.db"
    current_rows = [{"ip": "192.168.1.9", "hostname": "sqlite-current"}]
    write_dataset_snapshot("device_inventory.csv", current_rows, db_path)

    import_legacy_csvs(data_dir, db_path)

    assert read_dataset("device_inventory.csv", db_path) == current_rows



def test_sqlite_backup_and_restore_preserve_runtime_data(tmp_path):
    source = tmp_path / "source.db"
    backup = tmp_path / "backups" / "wifi-backup.db"
    restored = tmp_path / "restore" / "wifi-restored.db"
    initialize_database(source)
    rows = [{"ip": "192.168.1.8", "hostname": "access-point"}]
    write_dataset_snapshot("device_inventory.csv", rows, source)

    assert backup_database(backup, source) == backup
    assert restore_database(backup, restored) == restored
    assert read_dataset("device_inventory.csv", restored) == rows

    with connect(restored) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2


def test_backup_and_restore_refuse_to_overwrite_existing_files(tmp_path):
    source = initialize_database(tmp_path / "source.db")
    backup = backup_database(tmp_path / "backup.db", source)
    existing = tmp_path / "existing.db"
    existing.write_bytes(b"keep this file")

    with pytest.raises(FileExistsError):
        backup_database(backup, source)
    with pytest.raises(FileExistsError):
        restore_database(backup, existing)

    assert existing.read_bytes() == b"keep this file"


def test_restore_rejects_corrupt_backup_without_creating_destination(tmp_path):
    corrupt = tmp_path / "corrupt.db"
    corrupt.write_bytes(b"not a sqlite database")
    destination = tmp_path / "restored.db"

    with pytest.raises(sqlite3.DatabaseError):
        restore_database(corrupt, destination)

    assert not destination.exists()


def test_backup_rejects_same_source_and_destination(tmp_path):
    source = initialize_database(tmp_path / "same.db")

    with pytest.raises(ValueError):
        backup_database(source, source)
