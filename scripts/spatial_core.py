"""Validated local spatial floor-plan primitives and SQLite persistence."""
from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Iterable, Mapping
from uuid import uuid4

from scripts.storage import connect, initialize_database


ANCHOR_TYPES = {"access_point", "laptop", "sensor", "manual_reference"}


def _number(value: object, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a finite number.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field} must be a finite number.")
    return number


def _required_text(value: object, field: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{field} is required.")
    return result


def validate_floor(name: str, width_m: object, height_m: object) -> dict[str, object]:
    clean_name = _required_text(name, "Floor name")
    width = _number(width_m, "Floor width")
    height = _number(height_m, "Floor height")
    if not 0 < width <= 10000 or not 0 < height <= 10000:
        raise ValueError("Floor dimensions must be greater than 0 and at most 10000 m.")
    return {"name": clean_name, "width_m": width, "height_m": height, "unit": "m"}


def validate_rectangle(
    x_m: object,
    y_m: object,
    width_m: object,
    height_m: object,
    floor_width_m: object,
    floor_height_m: object,
) -> dict[str, float]:
    x = _number(x_m, "X")
    y = _number(y_m, "Y")
    width = _number(width_m, "Width")
    height = _number(height_m, "Height")
    floor_width = _number(floor_width_m, "Floor width")
    floor_height = _number(floor_height_m, "Floor height")
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise ValueError("Rectangle coordinates must be non-negative and dimensions positive.")
    if x + width > floor_width or y + height > floor_height:
        raise ValueError("Zone rectangle must fit entirely inside the floor plan.")
    return {"x_m": x, "y_m": y, "width_m": width, "height_m": height}


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def create_floor(
    name: str,
    width_m: object,
    height_m: object,
    *,
    floor_id: str | None = None,
    db_path=None,
) -> dict[str, object]:
    values = validate_floor(name, width_m, height_m)
    identifier = str(floor_id or uuid4().hex).strip()
    if not identifier:
        raise ValueError("Floor ID is required.")
    now = _timestamp()
    database = initialize_database(db_path)
    with connect(database) as connection:
        connection.execute(
            """
            INSERT INTO spatial_floors (
                floor_id, name, width_m, height_m, unit, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'm', ?, ?)
            ON CONFLICT(floor_id) DO UPDATE SET
                name=excluded.name, width_m=excluded.width_m,
                height_m=excluded.height_m, updated_at=excluded.updated_at
            """,
            (
                identifier, values["name"], values["width_m"],
                values["height_m"], now, now,
            ),
        )
        row = connection.execute(
            "SELECT * FROM spatial_floors WHERE floor_id=?", (identifier,)
        ).fetchone()
    return dict(row)


def list_floors(*, db_path=None) -> list[dict[str, object]]:
    database = initialize_database(db_path)
    with connect(database) as connection:
        rows = connection.execute(
            "SELECT * FROM spatial_floors ORDER BY name, floor_id"
        ).fetchall()
    return [dict(row) for row in rows]


def save_zone(
    floor_id: str,
    name: str,
    x_m: object,
    y_m: object,
    width_m: object,
    height_m: object,
    *,
    zone_id: str | None = None,
    db_path=None,
) -> dict[str, object]:
    floor_key = _required_text(floor_id, "Floor ID")
    clean_name = _required_text(name, "Zone name")
    identifier = str(zone_id or uuid4().hex).strip()
    if not identifier:
        raise ValueError("Zone ID is required.")
    database = initialize_database(db_path)
    with connect(database) as connection:
        floor = connection.execute(
            "SELECT width_m, height_m FROM spatial_floors WHERE floor_id=?",
            (floor_key,),
        ).fetchone()
        if floor is None:
            raise ValueError("The selected floor does not exist.")
        rect = validate_rectangle(
            x_m, y_m, width_m, height_m, floor["width_m"], floor["height_m"]
        )
        now = _timestamp()
        connection.execute(
            """
            INSERT INTO spatial_zones (
                zone_id, floor_id, name, x_m, y_m, width_m, height_m,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(zone_id) DO UPDATE SET
                floor_id=excluded.floor_id, name=excluded.name,
                x_m=excluded.x_m, y_m=excluded.y_m,
                width_m=excluded.width_m, height_m=excluded.height_m,
                updated_at=excluded.updated_at
            """,
            (
                identifier, floor_key, clean_name, rect["x_m"], rect["y_m"],
                rect["width_m"], rect["height_m"], now, now,
            ),
        )
        row = connection.execute(
            "SELECT * FROM spatial_zones WHERE zone_id=?", (identifier,)
        ).fetchone()
    return dict(row)


def list_zones(floor_id: str, *, db_path=None) -> list[dict[str, object]]:
    database = initialize_database(db_path)
    with connect(database) as connection:
        rows = connection.execute(
            "SELECT * FROM spatial_zones WHERE floor_id=? ORDER BY name, zone_id",
            (str(floor_id),),
        ).fetchall()
    return [dict(row) for row in rows]


def save_anchor(
    floor_id: str,
    name: str,
    anchor_type: str,
    x_m: object,
    y_m: object,
    *,
    source: str = "manual",
    metadata: Mapping[str, object] | None = None,
    anchor_id: str | None = None,
    db_path=None,
) -> dict[str, object]:
    floor_key = _required_text(floor_id, "Floor ID")
    clean_name = _required_text(name, "Anchor name")
    kind = _required_text(anchor_type, "Anchor type").casefold()
    if kind not in ANCHOR_TYPES:
        raise ValueError(f"Anchor type must be one of: {', '.join(sorted(ANCHOR_TYPES))}.")
    identifier = str(anchor_id or uuid4().hex).strip()
    if not identifier:
        raise ValueError("Anchor ID is required.")
    database = initialize_database(db_path)
    with connect(database) as connection:
        floor = connection.execute(
            "SELECT width_m, height_m FROM spatial_floors WHERE floor_id=?",
            (floor_key,),
        ).fetchone()
        if floor is None:
            raise ValueError("The selected floor does not exist.")
        x = _number(x_m, "X")
        y = _number(y_m, "Y")
        if not 0 <= x <= floor["width_m"] or not 0 <= y <= floor["height_m"]:
            raise ValueError("Anchor coordinates must be inside the floor plan.")
        now = _timestamp()
        connection.execute(
            """
            INSERT INTO spatial_anchors (
                anchor_id, floor_id, name, anchor_type, x_m, y_m, source,
                metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(anchor_id) DO UPDATE SET
                floor_id=excluded.floor_id, name=excluded.name,
                anchor_type=excluded.anchor_type, x_m=excluded.x_m,
                y_m=excluded.y_m, source=excluded.source,
                metadata_json=excluded.metadata_json, updated_at=excluded.updated_at
            """,
            (
                identifier, floor_key, clean_name, kind, x, y,
                str(source or "manual"),
                json.dumps(dict(metadata or {}), ensure_ascii=False, sort_keys=True),
                now, now,
            ),
        )
        row = connection.execute(
            "SELECT * FROM spatial_anchors WHERE anchor_id=?", (identifier,)
        ).fetchone()
    result = dict(row)
    result["metadata"] = json.loads(result.pop("metadata_json"))
    return result


def list_anchors(floor_id: str, *, db_path=None) -> list[dict[str, object]]:
    database = initialize_database(db_path)
    with connect(database) as connection:
        rows = connection.execute(
            "SELECT * FROM spatial_anchors WHERE floor_id=? ORDER BY name, anchor_id",
            (str(floor_id),),
        ).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        item["metadata"] = json.loads(item.pop("metadata_json"))
        results.append(item)
    return results


def locate_zone(x_m: object, y_m: object, zones: Iterable[Mapping[str, object]]) -> dict[str, object]:
    """Return a zone only when exactly one rectangle contains the point."""
    x = _number(x_m, "X")
    y = _number(y_m, "Y")
    matches = []
    for zone in zones:
        left = _number(zone.get("x_m"), "Zone X")
        top = _number(zone.get("y_m"), "Zone Y")
        width = _number(zone.get("width_m"), "Zone width")
        height = _number(zone.get("height_m"), "Zone height")
        if left <= x < left + width and top <= y < top + height:
            matches.append(zone)
    if not matches:
        return {"status": "unassigned", "zone_id": "", "zone_name": ""}
    if len(matches) > 1:
        return {
            "status": "ambiguous",
            "zone_id": "",
            "zone_name": "",
            "candidates": [str(zone.get("name", "")) for zone in matches],
        }
    match = matches[0]
    return {
        "status": "assigned",
        "zone_id": str(match.get("zone_id", "")),
        "zone_name": str(match.get("name", "")),
    }
