import sqlite3

import pytest

from scripts.spatial_core import (
    create_floor,
    list_anchors,
    list_floors,
    list_zones,
    locate_zone,
    save_anchor,
    save_zone,
    validate_floor,
    validate_rectangle,
)
from scripts.storage import connect, initialize_database


def test_schema_v2_upgrades_to_spatial_schema_without_losing_data(tmp_path):
    db_path = tmp_path / "legacy-v2.db"
    initialize_database(db_path)
    with connect(db_path) as connection:
        connection.execute(
            "INSERT INTO dataset_snapshots(dataset, row_count, updated_at) VALUES (?, ?, ?)",
            ("keep.csv", 0, "before-migration"),
        )
        connection.execute("PRAGMA user_version = 2")

    initialize_database(db_path)

    with connect(db_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
        assert connection.execute(
            "SELECT updated_at FROM dataset_snapshots WHERE dataset='keep.csv'"
        ).fetchone()["updated_at"] == "before-migration"
        tables = {
            row["name"] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert {"spatial_floors", "spatial_zones", "spatial_anchors"} <= tables


def test_floor_zone_and_anchor_round_trip_are_local_sqlite_records(tmp_path):
    db_path = tmp_path / "spatial.db"
    floor = create_floor("Office", 12, 8, floor_id="floor-1", db_path=db_path)
    zone = save_zone(
        "floor-1", "Meeting room", 2, 1, 4, 3,
        zone_id="zone-1", db_path=db_path,
    )
    anchor = save_anchor(
        "floor-1", "Access point 1", "access_point", 6, 4,
        metadata={"placement": "ceiling"}, anchor_id="ap-1", db_path=db_path,
    )

    assert floor["width_m"] == 12
    assert zone["name"] == "Meeting room"
    assert anchor["metadata"] == {"placement": "ceiling"}
    assert list_floors(db_path=db_path)[0]["floor_id"] == "floor-1"
    assert list_zones("floor-1", db_path=db_path)[0]["zone_id"] == "zone-1"
    assert list_anchors("floor-1", db_path=db_path)[0]["anchor_id"] == "ap-1"


def test_zone_must_fit_inside_selected_floor(tmp_path):
    db_path = tmp_path / "spatial.db"
    create_floor("Office", 10, 6, floor_id="floor-1", db_path=db_path)

    with pytest.raises(ValueError, match="inside the floor"):
        save_zone("floor-1", "Outside", 8, 1, 4, 2, db_path=db_path)


def test_zone_and_floor_dimensions_reject_invalid_values():
    with pytest.raises(ValueError):
        validate_floor("Office", 0, 10)
    with pytest.raises(ValueError):
        validate_floor(" ", 10, 10)
    with pytest.raises(ValueError):
        validate_rectangle(-1, 0, 2, 2, 10, 10)
    with pytest.raises(ValueError):
        validate_rectangle(0, 0, float("nan"), 2, 10, 10)


def test_anchor_must_be_inside_floor_and_use_known_type(tmp_path):
    db_path = tmp_path / "spatial.db"
    create_floor("Office", 10, 6, floor_id="floor-1", db_path=db_path)

    with pytest.raises(ValueError, match="inside the floor"):
        save_anchor("floor-1", "AP", "access_point", 11, 2, db_path=db_path)
    with pytest.raises(ValueError, match="Anchor type"):
        save_anchor("floor-1", "Unknown", "camera", 2, 2, db_path=db_path)


def test_locate_zone_requires_one_unambiguous_match():
    zones = [
        {"zone_id": "a", "name": "Room A", "x_m": 0, "y_m": 0, "width_m": 5, "height_m": 5},
        {"zone_id": "b", "name": "Room B", "x_m": 5, "y_m": 0, "width_m": 5, "height_m": 5},
        {"zone_id": "overlap", "name": "Overlap", "x_m": 2, "y_m": 2, "width_m": 5, "height_m": 5},
    ]

    assert locate_zone(1, 1, zones)["zone_name"] == "Room A"
    assert locate_zone(5, 1, zones)["zone_name"] == "Room B"
    assert locate_zone(3, 3, zones)["status"] == "ambiguous"
    assert locate_zone(20, 20, zones)["status"] == "unassigned"


def test_zone_and_anchor_reject_missing_floor(tmp_path):
    db_path = tmp_path / "spatial.db"
    initialize_database(db_path)

    with pytest.raises(ValueError, match="floor does not exist"):
        save_zone("missing", "Room", 0, 0, 2, 2, db_path=db_path)
    with pytest.raises(ValueError, match="floor does not exist"):
        save_anchor("missing", "AP", "access_point", 1, 1, db_path=db_path)
