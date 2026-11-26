import pytest

from scripts.spatial_core import create_floor, save_zone
from scripts.spatial_fingerprints import (
    estimate_zone,
    evaluate_fingerprints,
    evaluate_holdout_fingerprints,
    save_fingerprint,
)


def _dataset(db_path):
    create_floor("Office", 12, 8, floor_id="floor-1", db_path=db_path)
    save_zone("floor-1", "Room A", 0, 0, 5, 5, zone_id="zone-a", db_path=db_path)
    save_zone("floor-1", "Room B", 5, 0, 5, 5, zone_id="zone-b", db_path=db_path)
    save_fingerprint(
        "floor-1", "zone-a", "A-1",
        {"AP-01": -45, "AP-02": -70, "AP-03": -82},
        sample_id="a-1", db_path=db_path,
    )
    save_fingerprint(
        "floor-1", "zone-a", "A-2",
        {"AP-01": -48, "AP-02": -68, "AP-03": -80},
        sample_id="a-2", db_path=db_path,
    )
    save_fingerprint(
        "floor-1", "zone-b", "B-1",
        {"AP-01": -80, "AP-02": -43, "AP-03": -65},
        sample_id="b-1", db_path=db_path,
    )
    save_fingerprint(
        "floor-1", "zone-b", "B-2",
        {"AP-01": -78, "AP-02": -46, "AP-03": -62},
        sample_id="b-2", db_path=db_path,
    )


def test_leave_one_out_validation_excludes_the_reference_sample(tmp_path):
    db_path = tmp_path / "spatial.db"
    _dataset(db_path)
    report = evaluate_fingerprints("floor-1", k=3, db_path=db_path)

    assert report["status"] == "evaluated"
    assert report["sample_count"] == 4
    assert report["evaluated_count"] == 4
    assert report["correct"] == 4
    assert report["incorrect"] == 0
    assert report["accuracy"] == 1.0
    assert report["coverage"] == 1.0
    assert len(report["per_zone"]) == 2
    assert "not a guarantee" in report["message"]


def test_leave_one_out_skips_zones_with_only_one_reference_sample(tmp_path):
    db_path = tmp_path / "spatial.db"
    create_floor("Office", 10, 5, floor_id="floor-1", db_path=db_path)
    save_zone("floor-1", "Room A", 0, 0, 5, 5, zone_id="zone-a", db_path=db_path)
    save_zone("floor-1", "Room B", 5, 0, 5, 5, zone_id="zone-b", db_path=db_path)
    save_fingerprint(
        "floor-1", "zone-a", "A-1", {"AP-01": -50, "AP-02": -70},
        sample_id="a-1", db_path=db_path,
    )
    report = evaluate_fingerprints("floor-1", db_path=db_path)

    assert report["status"] == "insufficient_reference_samples"
    assert report["sample_count"] == 1
    assert report["evaluated_count"] == 0
    assert report["skipped_count"] == 1
    assert report["accuracy"] is None


def test_leave_one_out_reports_coverage_separately_from_accuracy(tmp_path):
    db_path = tmp_path / "spatial.db"
    _dataset(db_path)
    report = evaluate_fingerprints(
        "floor-1", k=1, min_overlap=4, db_path=db_path,
    )
    assert report["accuracy"] is None
    assert report["coverage"] == 0.0
    assert report["insufficient"] == 4



def _holdout_dataset(db_path):
    create_floor("Office", 12, 8, floor_id="floor-holdout", db_path=db_path)
    save_zone(
        "floor-holdout", "Room A", 0, 0, 5, 5,
        zone_id="zone-a", db_path=db_path,
    )
    save_zone(
        "floor-holdout", "Room B", 5, 0, 5, 5,
        zone_id="zone-b", db_path=db_path,
    )
    for sample_id, zone_id, measurements in [
        ("a-1", "zone-a", {"AP-01": -45, "AP-02": -70, "AP-03": -82}),
        ("a-2", "zone-a", {"AP-01": -47, "AP-02": -68, "AP-03": -80}),
        ("a-3", "zone-a", {"AP-01": -46, "AP-02": -71, "AP-03": -81}),
        ("b-1", "zone-b", {"AP-01": -80, "AP-02": -43, "AP-03": -65}),
        ("b-2", "zone-b", {"AP-01": -78, "AP-02": -46, "AP-03": -62}),
        ("b-3", "zone-b", {"AP-01": -79, "AP-02": -44, "AP-03": -64}),
    ]:
        save_fingerprint(
            "floor-holdout", zone_id, sample_id, measurements,
            sample_id=sample_id, db_path=db_path,
        )


def test_time_ordered_holdout_uses_later_samples_against_earlier_references(tmp_path):
    db_path = tmp_path / "holdout.db"
    _holdout_dataset(db_path)

    report = evaluate_holdout_fingerprints(
        "floor-holdout", k=1, min_overlap=2, db_path=db_path,
    )

    assert report["status"] == "evaluated"
    assert report["sample_count"] == 6
    assert report["training_count"] == 4
    assert report["holdout_count"] == 2
    assert report["eligible_zone_count"] == 2
    assert report["correct"] == 2
    assert report["incorrect"] == 0
    assert report["accuracy"] == 1.0
    assert report["coverage"] == 1.0
    assert {item["sample_id"] for item in report["outcomes"]} == {"a-3", "b-3"}
    assert "Time-ordered holdout" in report["message"]


def test_holdout_validation_skips_zones_with_too_few_samples(tmp_path):
    db_path = tmp_path / "holdout.db"
    _holdout_dataset(db_path)
    save_fingerprint(
        "floor-holdout", "zone-a", "A-4",
        {"AP-01": -46, "AP-02": -69, "AP-03": -80},
        sample_id="a-4", db_path=db_path,
    )
    # Room B has three samples; Room A has four. No zone is skipped here.
    report = evaluate_holdout_fingerprints("floor-holdout", db_path=db_path)
    assert report["skipped_zone_count"] == 0
    assert report["training_count"] == 5
    assert report["holdout_count"] == 3


def test_holdout_validation_requires_three_samples_per_zone(tmp_path):
    db_path = tmp_path / "holdout.db"
    _dataset(db_path)
    report = evaluate_holdout_fingerprints(
        "floor-1", min_samples_per_zone=3, db_path=db_path,
    )
    assert report["status"] == "insufficient_reference_samples"
    assert report["holdout_count"] == 0
    assert report["accuracy"] is None


def test_holdout_validation_rejects_unreasonable_split_parameters(tmp_path):
    db_path = tmp_path / "holdout.db"
    _dataset(db_path)
    with pytest.raises(ValueError, match="holdout_fraction"):
        evaluate_holdout_fingerprints(
            "floor-1", holdout_fraction=0.8, db_path=db_path,
        )
