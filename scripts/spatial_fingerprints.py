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
    exclude_sample_id: str | None = None,
    reference_sample_ids: set[str] | None = None,
    db_path=None,
) -> dict[str, object]:
    query = validate_measurements(measurements)
    if k < 1 or min_overlap < 1:
        raise ValueError("k and min_overlap must be positive integers.")
    samples = list_fingerprints(floor_id, db_path=db_path)
    candidates = []
    for sample in samples:
        if exclude_sample_id and sample["sample_id"] == exclude_sample_id:
            continue
        if reference_sample_ids is not None and sample["sample_id"] not in reference_sample_ids:
            continue
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



def evaluate_fingerprints(
    floor_id: str,
    *,
    k: int = 3,
    min_overlap: int = 2,
    db_path=None,
) -> dict[str, object]:
    """Leave-one-out validation; only zones with >=2 samples are evaluable."""
    samples = list_fingerprints(floor_id, db_path=db_path)
    zone_counts: dict[str, int] = {}
    for sample in samples:
        zone_counts[sample["zone_id"]] = zone_counts.get(sample["zone_id"], 0) + 1

    eligible = [
        sample for sample in samples if zone_counts[sample["zone_id"]] >= 2
    ]
    skipped_single_sample_zones = len(samples) - len(eligible)
    if not eligible:
        return {
            "status": "insufficient_reference_samples",
            "sample_count": len(samples),
            "evaluated_count": 0,
            "skipped_count": skipped_single_sample_zones,
            "accuracy": None,
            "coverage": None,
            "correct": 0,
            "incorrect": 0,
            "ambiguous": 0,
            "insufficient": 0,
            "per_zone": [],
            "message": "At least two reference samples per zone are required.",
        }

    outcomes = []
    for sample in eligible:
        estimate = estimate_zone(
            floor_id,
            sample["measurements"],
            k=k,
            min_overlap=min_overlap,
            exclude_sample_id=sample["sample_id"],
            db_path=db_path,
        )
        outcomes.append({
            "sample_id": sample["sample_id"],
            "expected_zone_id": sample["zone_id"],
            "predicted_zone_id": estimate.get("zone_id", ""),
            "status": estimate["status"],
            "correct": (
                estimate["status"] == "estimated"
                and estimate.get("zone_id") == sample["zone_id"]
            ),
        })

    correct = sum(item["correct"] for item in outcomes)
    incorrect = sum(
        item["status"] == "estimated" and not item["correct"] for item in outcomes
    )
    ambiguous = sum(item["status"] == "ambiguous" for item in outcomes)
    insufficient = sum(
        item["status"] == "insufficient_evidence" for item in outcomes
    )
    evaluable_predictions = correct + incorrect
    accuracy = correct / evaluable_predictions if evaluable_predictions else None
    coverage = evaluable_predictions / len(eligible)

    per_zone = []
    for zone_id in sorted(zone_counts):
        zone_outcomes = [
            item for item in outcomes if item["expected_zone_id"] == zone_id
        ]
        if not zone_outcomes:
            continue
        zone_correct = sum(item["correct"] for item in zone_outcomes)
        zone_predicted = sum(item["status"] == "estimated" for item in zone_outcomes)
        per_zone.append({
            "zone_id": zone_id,
            "sample_count": len(zone_outcomes),
            "correct": zone_correct,
            "estimated": zone_predicted,
            "accuracy": (
                round(zone_correct / zone_predicted, 3) if zone_predicted else None
            ),
        })

    return {
        "status": "evaluated",
        "sample_count": len(samples),
        "evaluated_count": len(eligible),
        "skipped_count": skipped_single_sample_zones,
        "accuracy": round(accuracy, 3) if accuracy is not None else None,
        "coverage": round(coverage, 3),
        "correct": correct,
        "incorrect": incorrect,
        "ambiguous": ambiguous,
        "insufficient": insufficient,
        "per_zone": per_zone,
        "outcomes": outcomes,
        "message": (
            "Leave-one-out results on this small local survey set; not a guarantee "
            "of future accuracy. Collect independent repeat surveys across times "
            "and device orientations before drawing conclusions."
        ),
    }



def evaluate_holdout_fingerprints(
    floor_id: str,
    *,
    k: int = 3,
    min_overlap: int = 2,
    holdout_fraction: float = 0.25,
    min_samples_per_zone: int = 3,
    db_path=None,
) -> dict[str, object]:
    """Evaluate later, time-ordered samples against earlier references only."""
    if not 0.1 <= float(holdout_fraction) <= 0.5:
        raise ValueError("holdout_fraction must be between 0.1 and 0.5.")
    if min_samples_per_zone < 3:
        raise ValueError("min_samples_per_zone must be at least 3.")
    if k < 1 or min_overlap < 1:
        raise ValueError("k and min_overlap must be positive integers.")

    samples = list_fingerprints(floor_id, db_path=db_path)
    grouped: dict[str, list[dict[str, object]]] = {}
    for sample in samples:
        grouped.setdefault(sample["zone_id"], []).append(sample)

    training_samples = []
    holdout_samples = []
    skipped_zones = 0
    for zone_id, zone_samples in grouped.items():
        ordered = sorted(
            zone_samples,
            key=lambda item: (item["observed_at"], item["sample_id"]),
        )
        if len(ordered) < min_samples_per_zone:
            skipped_zones += 1
            continue
        holdout_count = max(1, math.ceil(len(ordered) * holdout_fraction))
        holdout_count = min(holdout_count, len(ordered) - 2)
        training_samples.extend(ordered[:-holdout_count])
        holdout_samples.extend(ordered[-holdout_count:])

    if not holdout_samples:
        return {
            "status": "insufficient_reference_samples",
            "sample_count": len(samples),
            "training_count": 0,
            "holdout_count": 0,
            "eligible_zone_count": 0,
            "skipped_zone_count": skipped_zones,
            "accuracy": None,
            "coverage": None,
            "correct": 0,
            "incorrect": 0,
            "ambiguous": 0,
            "insufficient": 0,
            "per_zone": [],
            "outcomes": [],
            "message": (
                f"At least {min_samples_per_zone} samples per zone are required "
                "for a time-ordered holdout test."
            ),
        }

    reference_ids = {sample["sample_id"] for sample in training_samples}
    outcomes = []
    for sample in holdout_samples:
        estimate = estimate_zone(
            floor_id,
            sample["measurements"],
            k=k,
            min_overlap=min_overlap,
            reference_sample_ids=reference_ids,
            db_path=db_path,
        )
        outcomes.append({
            "sample_id": sample["sample_id"],
            "expected_zone_id": sample["zone_id"],
            "predicted_zone_id": estimate.get("zone_id", ""),
            "status": estimate["status"],
            "correct": (
                estimate["status"] == "estimated"
                and estimate.get("zone_id") == sample["zone_id"]
            ),
        })

    correct = sum(item["correct"] for item in outcomes)
    incorrect = sum(
        item["status"] == "estimated" and not item["correct"] for item in outcomes
    )
    ambiguous = sum(item["status"] == "ambiguous" for item in outcomes)
    insufficient = sum(
        item["status"] == "insufficient_evidence" for item in outcomes
    )
    predicted = correct + incorrect
    accuracy = correct / predicted if predicted else None
    coverage = predicted / len(holdout_samples)

    per_zone = []
    eligible_zone_ids = sorted({sample["zone_id"] for sample in holdout_samples})
    for zone_id in eligible_zone_ids:
        zone_outcomes = [
            item for item in outcomes if item["expected_zone_id"] == zone_id
        ]
        zone_correct = sum(item["correct"] for item in zone_outcomes)
        zone_predicted = sum(item["status"] == "estimated" for item in zone_outcomes)
        per_zone.append({
            "zone_id": zone_id,
            "training_samples": sum(
                sample["zone_id"] == zone_id for sample in training_samples
            ),
            "holdout_samples": len(zone_outcomes),
            "correct": zone_correct,
            "estimated": zone_predicted,
            "accuracy": (
                round(zone_correct / zone_predicted, 3) if zone_predicted else None
            ),
            "coverage": round(zone_predicted / len(zone_outcomes), 3),
        })

    return {
        "status": "evaluated",
        "sample_count": len(samples),
        "training_count": len(training_samples),
        "holdout_count": len(holdout_samples),
        "eligible_zone_count": len(eligible_zone_ids),
        "skipped_zone_count": skipped_zones,
        "accuracy": round(accuracy, 3) if accuracy is not None else None,
        "coverage": round(coverage, 3),
        "correct": correct,
        "incorrect": incorrect,
        "ambiguous": ambiguous,
        "insufficient": insufficient,
        "per_zone": per_zone,
        "outcomes": outcomes,
        "message": (
            "Time-ordered holdout: later samples were evaluated only against earlier "
            "reference samples. This is more independent than leave-one-out, but it "
            "still reflects this device, environment, survey schedule, and dataset; "
            "it is not a guarantee of future accuracy."
        ),
    }
