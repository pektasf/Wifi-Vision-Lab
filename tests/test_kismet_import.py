import json

import pytest

from scripts.discovery.kismet_import import normalize_kismet_export


def test_kismet_json_import_extracts_wifi_randomized_mac_and_radio_metadata():
    payload = [{
        "kismet.device.base.phyname": "IEEE802.11",
        "kismet.device.base.type": "Wi-Fi Client",
        "kismet.device.base.key": "fixture-device-key",
        "kismet.device.base.macaddr": "02:11:22:33:44:55",
        "kismet.device.base.name": "Fixture client",
        "kismet.device.base.manuf": "Randomized",
        "kismet.device.base.last_time": 1795687200,
        "kismet.device.base.channel": "6",
        "kismet.device.base.frequency": 2437,
        "kismet.device.base.signal/kismet.common.signal.last_signal": -61,
        "kismet.device.base.packets.total": 42,
        "dot11.device.randomized_mac": 1,
        "dot11.device.last_bssid": "00:AA:BB:CC:DD:EE",
    }]

    rows = normalize_kismet_export(
        json.dumps(payload),
        imported_at="2026-11-26T10:00:00+00:00",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "kismet_import"
    assert row["mac"] == "02:11:22:33:44:55"
    assert row["randomized_mac"] == "true"
    assert row["mac_address_type"] == "locally_administered"
    assert row["evidence_status"] == "kismet_reported_randomized"
    assert row["last_bssid"] == "00:AA:BB:CC:DD:EE"
    assert row["channel"] == "6"
    assert row["frequency_mhz"] == "2437"
    assert row["signal_dbm"] == "-61"
    assert row["packets"] == "42"
    assert row["imported_at"] == "2026-11-26T10:00:00+00:00"


def test_kismet_ekjson_import_accepts_one_record_per_line():
    records = [
        {
            "phy": "IEEE802.11",
            "type": "Wi-Fi AP",
            "mac": "00:11:22:33:44:55",
            "randomized_mac": False,
        },
        {
            "phy": "Bluetooth",
            "type": "Bluetooth LE",
            "mac": "02:11:22:33:44:66",
        },
    ]
    text = "\n".join(json.dumps(record) for record in records)

    rows = normalize_kismet_export(text)

    assert len(rows) == 1
    assert rows[0]["randomized_mac"] == "false"
    assert rows[0]["evidence_status"] == "kismet_imported"


def test_kismet_import_flags_locally_administered_mac_without_claiming_spoofing():
    rows = normalize_kismet_export(json.dumps([{
        "phy": "IEEE802.11",
        "type": "Wi-Fi Client",
        "mac": "06:11:22:33:44:55",
    }]))

    assert rows[0]["randomized_mac"] == "true"
    assert rows[0]["evidence_status"] == "locally_administered_address"


def test_kismet_import_does_not_infer_randomized_for_universal_mac_without_flag():
    rows = normalize_kismet_export(json.dumps([{
        "phy": "IEEE802.11",
        "type": "Wi-Fi Client",
        "mac": "00:11:22:33:44:55",
    }]))

    assert rows[0]["randomized_mac"] == "unknown"
    assert rows[0]["evidence_status"] == "kismet_imported"


def test_kismet_import_ignores_non_wifi_and_invalid_mac_records():
    rows = normalize_kismet_export(json.dumps([
        {"phy": "Bluetooth", "type": "Bluetooth LE", "mac": "02:11:22:33:44:55"},
        {"phy": "IEEE802.11", "type": "Wi-Fi Client", "mac": "invalid"},
    ]))
    assert rows == []


@pytest.mark.parametrize("content", [
    b"\xff",
    "{not-json}",
    '{"phy":"IEEE802.11"}\nnot-json',
])
def test_kismet_import_rejects_invalid_utf8_or_json(content):
    with pytest.raises(ValueError):
        normalize_kismet_export(content)


def test_kismet_import_rejects_files_over_size_limit():
    from scripts.discovery.kismet_import import MAX_KISMET_BYTES

    with pytest.raises(ValueError, match="25 MB"):
        normalize_kismet_export(b" " * (MAX_KISMET_BYTES + 1))
