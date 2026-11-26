"""Local RSSI fingerprint survey and conservative zone matching.

This module estimates a labelled zone, never a metric coordinate or physical
distance. Access-point keys are user-defined local aliases (for example AP-01),
not SSIDs or BSSIDs.
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime
from uuid import uuid4
from typing import Mapping

from scripts.spatial_core import _required_text
from scripts.storage import connect, initialize_database


_MAC_LIKE = re.compile(r"^(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}$", re.I)


def validate_measurements(measurements: Mapping[str, object]) -> dict[str, int]:
    if not isinstance(measurements, Mapping) or not measurements:
        raise ValueError("At least one access-point measurement is required.")
    result: dict[str, int] = {}
    for raw_key, raw_value in measurements.items():
        key = _required_text(raw_key, "Access-point alias")
        if _MAC_LIKE.match(key):
            raise ValueError("Use local AP aliases, not MAC/BSSID values.")
        if len(key) > 64:
            raise ValueError("Access-point aliases must be 64 characters or fewer.")
        try:
            numeric = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"RSSI for {key} must be a number in dBm.") from exc
        if not math.isfinite(numeric):
            raise ValueError(f"RSSI for {key} must be a finite number.")
        if not -120 <= numeric <= -1:
            raise ValueError(f"RSSI for {key} must be between -120 and -1 dBm.")
        result[key] = int(round(numeric))
    return result


def parse_measurement_lines(value: str) -> dict[str, int]:
    """Parse one local alias and RSSI value per line: AP-01,-62."""
    measurements: dict[str, int] = {}
    for line_number, raw_line in enumerate(str(value or "").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 2 or not parts[0]:
            raise ValueError(f"Line {line_number}: expected AP-ALIAS,-62.")
        if parts[0] in measurements:
            raise ValueError(f"Line {line_number}: duplicate AP alias {parts[0]}.")
        measurements[parts[0]] = parts[1]
    return validate_measurements(measurements)


def save_fingerprint(
    floor_id: str,
    zone_id: str,
    label: str,
    measurements: Mapping[str, object],
    *,
    source: str = "manual",
    notes: str = "",
    sample_id: str | None = None,
    db_path=None,
) -> dict[str, object]:
    floor_key = _required_text(floor_id, "Floor ID")
    zone_key = _required_text(zone_id, "Zone ID")
    clean_label = _required_text(label, "Survey label")
    vector = validate_measurements(measurements)
    identifier = str(sample_id or uuid4().hex).strip()
    if not identifier:
        raise ValueError("Sample ID is required.")
    database = initialize_database(db_path)
    with connect(database) as connection:
        zone = connection.execute(
            "SELECT floor_id FROM spatial_zones WHERE zone_id=?", (zone_key,)
        ).fetchone()
        if zone is None or zone["floor_id"] != floor_key:
            raise ValueError("The selected zone does not belong to the selected floor.")
        observed_at = datetime.now().astimezone().isoformat(timespec="seconds")
        connection.execute(
            """
            INSERT INTO spatial_fingerprints (
                sample_id, floor_id, zone_id, label, measurements_json,
                source, observed_at, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                identifier, floor_key, zone_key, clean_label,
                json.dumps(vector, sort_keys=True), str(source or "manual"),
                observed_at, str(notes or "").strip(),
            ),
        )
        row = connection.execute(
            """
            SELECT sample_id, floor_id, zone_id, label, measurements_json,
                   source, observed_at, notes
            FROM spatial_fingerprints WHERE sample_id=?
            """,
            (identifier,),
        ).fetchone()
    result = dict(row)
    result["measurements"] = json.loads(result.pop("measurements_json"))
    return result


def list_fingerprints(floor_id: str, *, db_path=None) -> list[dict[str, object]]:
    database = initialize_database(db_path)
    with connect(database) as connection:
        rows = connection.execute(
            """
            SELECT sample_id, floor_id, zone_id, label, measurements_json,
                   source, observed_at, notes
            FROM spatial_fingerprints
            WHERE floor_id=? ORDER BY observed_at, sample_id
            """,
            (str(floor_id),),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["measurements"] = json.loads(item.pop("measurements_json"))
        result.append(item)
    return result


def _distance(
    query: Mapping[str, int],
    reference: Mapping[str, int],
    *,
    missing_penalty_db: float,
) -> tuple[float, int]:
    shared = set(query).intersection(reference)
    if not shared:
        return float("inf"), 0
    squared = [(query[key] - reference[key]) ** 2 for key in shared]
    rms = math.sqrt(sum(squared) / len(squared))
    missing_fraction = 1 - (len(shared) / max(len(query), len(reference)))
    return rms + missing_penalty_db * missing_fraction, len(shared)


def estimate_zone(
    floor_id: str,
    measurements: Mapping[str, object],
    *,
    k: int = 3,
    min_overlap: int = 2,
    missing_penalty_db: float = 12.0,
    db_path=None,
) -> dict[str, object]:
    query = validate_measurements(measurements)
    if k < 1 or min_overlap < 1:
        raise ValueError("k and min_overlap must be positive integers.")
    samples = list_fingerprints(floor_id, db_path=db_path)
    candidates = []
    for sample in samples:
        distance, overlap = _distance(
            query, sample["measurements"],
            missing_penalty_db=float(missing_penalty_db),
        )
        if overlap >= min_overlap and math.isfinite(distance):
            candidates.append({
                "sample_id": sample["sample_id"],
                "zone_id": sample["zone_id"],
                "label": sample["label"],
                "distance_db": round(distance, 2),
                "overlap": overlap,
            })
    candidates.sort(key=lambda item: (item["distance_db"], item["sample_id"]))
    if not candidates:
        return {
            "status": "insufficient_evidence",
            "zone_id": "",
            "zone_name": "",
            "confidence": 0.0,
            "nearest_distance_db": None,
            "matched_samples": 0,
            "message": (
                f"No reference sample shares at least {min_overlap} AP aliases "
                "with the observation."
            ),
        }

    nearest = candidates[:k]
    votes: dict[str, float] = {}
    for candidate in nearest:
        weight = 1.0 / max(candidate["distance_db"], 1.0)
        votes[candidate["zone_id"]] = votes.get(candidate["zone_id"], 0.0) + weight
    ordered_votes = sorted(votes.items(), key=lambda item: (-item[1], item[0]))
    total = sum(votes.values())
    winning_zone, winning_weight = ordered_votes[0]
    confidence = winning_weight / total if total else 0.0
    tied = len(ordered_votes) > 1 and math.isclose(
        ordered_votes[0][1], ordered_votes[1][1], rel_tol=1e-9, abs_tol=1e-12
    )
    if tied:
        status = "ambiguous"
        winning_zone = ""
    else:
        status = "estimated"

    zone_name = ""
    if winning_zone:
        database = initialize_database(db_path)
        with connect(database) as connection:
            row = connection.execute(
                "SELECT name FROM spatial_zones WHERE zone_id=?",
                (winning_zone,),
            ).fetchone()
        zone_name = row["name"] if row else ""

    return {
        "status": status,
        "zone_id": winning_zone,
        "zone_name": zone_name,
        "confidence": round(confidence, 3),
        "nearest_distance_db": nearest[0]["distance_db"],
        "matched_samples": len(nearest),
        "nearest_samples": nearest,
        "message": (
            "This is a fingerprint similarity score, not a calibrated probability "
            "or a measured physical distance."
        ),
    }
