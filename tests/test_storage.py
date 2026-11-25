import csv
import sqlite3

import pytest

from scripts.storage import (
    add_event, add_observation, connect, import_legacy_csvs,
    initialize_database, read_dataset, upsert_device, write_dataset_snapshot,
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
