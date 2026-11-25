import csv

import pytest

from scripts import common
from scripts.common import overwrite_rows, write_rows


def read_rows(path):
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_write_rows_creates_header_and_appends(tmp_path):
    path = tmp_path / "observations.csv"
    fields = ["ip", "status"]

    write_rows(path, [{"ip": "192.0.2.1", "status": "up"}], fields)
    write_rows(path, [{"ip": "192.0.2.2", "status": "arp"}], fields)

    assert read_rows(path) == [
        {"ip": "192.0.2.1", "status": "up"},
        {"ip": "192.0.2.2", "status": "arp"},
    ]


def test_write_rows_ignores_unlisted_fields(tmp_path):
    path = tmp_path / "observations.csv"

    write_rows(
        path,
        [{"ip": "192.0.2.5", "status": "up", "private_extra": "must-not-be-written"}],
        ["ip", "status"],
    )

    assert read_rows(path) == [{"ip": "192.0.2.5", "status": "up"}]
    assert "must-not-be-written" not in path.read_text(encoding="utf-8-sig")


def test_write_rows_rejects_existing_schema_mismatch(tmp_path):
    path = tmp_path / "observations.csv"
    path.write_text("ip,hostname\n192.0.2.1,host-a\n", encoding="utf-8")

    with pytest.raises(ValueError, match="CSV schema mismatch"):
        write_rows(path, [{"ip": "192.0.2.2", "status": "up"}], ["ip", "status"])

    assert "hostname" in path.read_text(encoding="utf-8")


def test_overwrite_rows_replaces_previous_content(tmp_path):
    path = tmp_path / "inventory.csv"
    fields = ["ip", "mac"]

    overwrite_rows(path, [{"ip": "192.0.2.1", "mac": "AA:BB:CC:DD:EE:FF"}], fields)
    overwrite_rows(path, [{"ip": "192.0.2.2", "mac": ""}], fields)

    assert read_rows(path) == [{"ip": "192.0.2.2", "mac": ""}]


def test_overwrite_rows_writes_header_for_empty_dataset(tmp_path):
    path = tmp_path / "empty.csv"

    overwrite_rows(path, [], ["ip", "status"])

    assert read_rows(path) == []
    assert path.read_text(encoding="utf-8-sig").strip() == "ip,status"


def test_failed_atomic_replace_preserves_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "inventory.csv"
    overwrite_rows(path, [{"ip": "192.0.2.1"}], ["ip"])

    def fail_replace(source, destination):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(common.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        overwrite_rows(path, [{"ip": "192.0.2.2"}], ["ip"])

    assert read_rows(path) == [{"ip": "192.0.2.1"}]
    assert list(tmp_path.glob(".inventory.csv.*.tmp")) == []
