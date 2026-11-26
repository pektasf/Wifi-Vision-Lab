import pytest

from scripts.spatial_core import create_floor, save_zone
from scripts.spatial_fingerprints import (
    estimate_zone,
    list_fingerprints,
    parse_measurement_lines,
    save_fingerprint,
    validate_measurements,
)


def _survey(db_path):
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


def test_measurements_validate_dbm_and_alias_privacy():
    assert validate_measurements({"AP-01": -61.4}) == {"AP-01": -61}
    with pytest.raises(ValueError, match="MAC/BSSID"):
        validate_measurements({"AA:BB:CC:DD:EE:FF": -60})
    with pytest.raises(ValueError, match="between -120 and -1"):
        validate_measurements({"AP-01": 0})
    with pytest.raises(ValueError, match="finite"):
        validate_measurements({"AP-01": float("nan")})
    with pytest.raises(ValueError, match="At least one"):
        validate_measurements({})


def test_measurement_text_parser_rejects_duplicate_and_invalid_lines():
    assert parse_measurement_lines("# local survey\nAP-01,-60\nAP-02,-72") == {
        "AP-01": -60, "AP-02": -72,
    }
    with pytest.raises(ValueError, match="duplicate"):
        parse_measurement_lines("AP-01,-60\nAP-01,-61")
    with pytest.raises(ValueError, match="expected"):
        parse_measurement_lines("AP-01,-60,extra")


def test_save_and_list_fingerprints_are_local_and_bound_to_floor_zone(tmp_path):
    db_path = tmp_path / "spatial.db"
    _survey(db_path)
    samples = list_fingerprints("floor-1", db_path=db_path)
    assert len(samples) == 4
    assert samples[0]["measurements"]["AP-01"] in {-45, -48, -80, -78}
    assert "AA:BB:CC:DD:EE:FF" not in str(samples)

    with pytest.raises(ValueError, match="does not belong"):
        save_fingerprint(
            "floor-1", "missing-zone", "bad", {"AP-01": -50, "AP-02": -60},
            db_path=db_path,
        )


def test_knn_estimates_zone_without_claiming_metric_coordinates(tmp_path):
    db_path = tmp_path / "spatial.db"
    _survey(db_path)
    result = estimate_zone(
        "floor-1", {"AP-01": -46, "AP-02": -69, "AP-03": -81},
        k=3, min_overlap=2, db_path=db_path,
    )
    assert result["status"] == "estimated"
    assert result["zone_id"] == "zone-a"
    assert result["zone_name"] == "Room A"
    assert "confidence" in result
    assert "coordinates" not in result
    assert "physical distance" in result["message"]


def test_estimator_refuses_insufficient_overlap(tmp_path):
    db_path = tmp_path / "spatial.db"
    _survey(db_path)
    result = estimate_zone(
        "floor-1", {"AP-01": -46}, min_overlap=2, db_path=db_path,
    )
    assert result["status"] == "insufficient_evidence"
    assert not result["zone_id"]


def test_estimator_reports_tied_zone_votes_as_ambiguous(tmp_path):
    db_path = tmp_path / "spatial.db"
    create_floor("Office", 10, 5, floor_id="floor-1", db_path=db_path)
    save_zone("floor-1", "A", 0, 0, 5, 5, zone_id="zone-a", db_path=db_path)
    save_zone("floor-1", "B", 5, 0, 5, 5, zone_id="zone-b", db_path=db_path)
    save_fingerprint(
        "floor-1", "zone-a", "A", {"AP-01": -60, "AP-02": -60},
        sample_id="a", db_path=db_path,
    )
    save_fingerprint(
        "floor-1", "zone-b", "B", {"AP-01": -60, "AP-02": -60},
        sample_id="b", db_path=db_path,
    )
    result = estimate_zone(
        "floor-1", {"AP-01": -60, "AP-02": -60}, k=2, db_path=db_path,
    )
    assert result["status"] == "ambiguous"
    assert not result["zone_id"]


def test_estimator_is_scoped_to_selected_floor(tmp_path):
    db_path = tmp_path / "spatial.db"
    _survey(db_path)
    create_floor("Other", 5, 5, floor_id="floor-2", db_path=db_path)
    result = estimate_zone(
        "floor-2", {"AP-01": -46, "AP-02": -69}, db_path=db_path,
    )
    assert result["status"] == "insufficient_evidence"
