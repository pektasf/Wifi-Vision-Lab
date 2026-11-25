import csv

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
