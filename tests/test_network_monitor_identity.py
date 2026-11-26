import pandas as pd

from scripts.network_monitor import compare_inventories


def test_dhcp_address_change_is_reported_for_same_mac_not_as_new_device():
    previous = pd.DataFrame([{"ip": "192.168.1.20", "mac": "aa:bb:cc:dd:ee:ff"}])
    current = pd.DataFrame([{"ip": "192.168.1.35", "mac": "AA:BB:CC:DD:EE:FF"}])

    events = compare_inventories(previous, current)

    assert len(events) == 1
    assert events[0]["event"] == "IP_CHANGED"
    assert events[0]["ip"] == "192.168.1.35"


def test_new_and_missing_devices_are_compared_by_mac():
    previous = pd.DataFrame([
        {"ip": "192.168.1.10", "mac": "00:00:00:00:00:01"},
        {"ip": "192.168.1.11", "mac": "00:00:00:00:00:02"},
    ])
    current = pd.DataFrame([
        {"ip": "192.168.1.10", "mac": "00:00:00:00:00:01"},
        {"ip": "192.168.1.12", "mac": "00:00:00:00:00:03"},
    ])

    events = compare_inventories(previous, current)

    assert {(event["event"], event["ip"]) for event in events} == {
        ("FIRST_OBSERVED", "192.168.1.12"),
        ("NOT_IN_LATEST_SCAN", "192.168.1.11"),
    }


def test_missing_mac_falls_back_to_ip_identity():
    previous = pd.DataFrame([{"ip": "192.168.1.5", "mac": ""}])
    current = pd.DataFrame([{"ip": "192.168.1.5", "mac": ""}])

    assert compare_inventories(previous, current) == []


def test_empty_inventory_does_not_create_phantom_identity():
    previous = pd.DataFrame([{"ip": "", "mac": ""}])
    current = pd.DataFrame([{"ip": "", "mac": ""}])

    assert compare_inventories(previous, current) == []



def test_ip_change_event_keeps_stable_identity_and_both_addresses():
    previous = pd.DataFrame([{"ip": "192.168.1.20", "mac": "aa:bb:cc:dd:ee:ff"}])
    current = pd.DataFrame([{"ip": "192.168.1.35", "mac": "AA:BB:CC:DD:EE:FF"}])

    event = compare_inventories(previous, current)[0]

    assert event["identity_key"] == "AA:BB:CC:DD:EE:FF"
    assert event["old_value"] == "192.168.1.20"
    assert event["new_value"] == "192.168.1.35"


def test_arrival_and_absence_events_keep_identity_and_address_context():
    previous = pd.DataFrame([{"ip": "192.168.1.10", "mac": "00:00:00:00:00:01"}])
    current = pd.DataFrame([{"ip": "192.168.1.12", "mac": "00:00:00:00:00:02"}])

    events = compare_inventories(previous, current)
    by_type = {event["event"]: event for event in events}

    assert by_type["FIRST_OBSERVED"]["identity_key"] == "00:00:00:00:00:02"
    assert by_type["FIRST_OBSERVED"]["new_value"] == "192.168.1.12"
    assert by_type["NOT_IN_LATEST_SCAN"]["identity_key"] == "00:00:00:00:00:01"
    assert by_type["NOT_IN_LATEST_SCAN"]["old_value"] == "192.168.1.10"


def test_run_migrates_legacy_event_csv_without_losing_rows(tmp_path, monkeypatch):
    import scripts.network_monitor as monitor

    monkeypatch.setattr(monitor, "DATA", tmp_path)
    monkeypatch.setattr(monitor, "stamp", lambda: "2026-11-26T09:00:00+03:00")

    pd.DataFrame([{"ip": "192.168.1.35", "mac": "AA:BB:CC:DD:EE:FF"}]).to_csv(
        tmp_path / "device_inventory.csv", index=False
    )
    pd.DataFrame([{"ip": "192.168.1.20", "mac": "AA:BB:CC:DD:EE:FF"}]).to_csv(
        tmp_path / "last_inventory.csv", index=False
    )
    (tmp_path / "network_events.csv").write_text(
        "timestamp,event,ip\\n2026-11-25T09:00:00+03:00,FIRST_OBSERVED,192.168.1.50\\n",
        encoding="utf-8",
    )

    events = monitor.run()
    saved = pd.read_csv(tmp_path / "network_events.csv", dtype=str).fillna("")

    assert len(events) == 1
    assert len(saved) == 2
    assert saved.loc[0, "event"] == "FIRST_OBSERVED"
    assert saved.loc[0, "identity_key"] == ""
    assert saved.loc[1, "event"] == "IP_CHANGED"
    assert saved.loc[1, "identity_key"] == "AA:BB:CC:DD:EE:FF"
    assert saved.loc[1, "old_value"] == "192.168.1.20"
    assert saved.loc[1, "new_value"] == "192.168.1.35"
